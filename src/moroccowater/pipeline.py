"""MVP pipeline: Al Massira water-surface area from Sentinel-2.

Run with:
    uv run python -m moroccowater.pipeline --start 2016-01-01 --end 2026-11-05

Scenes are processed in yearly batches and each batch is written as it finishes.
A single dask graph over all ~660 solar days exhausted memory on a 24 GB machine
(it stalled in swap without progressing), so batching is not an optimisation
here -- it is what makes the run complete at all. It also makes the run
resumable and lets progress be seen while it happens.
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import replace
from pathlib import Path

import dask
import pandas as pd
import rasterio

from . import checks, volume, water
from .aoi import crop_to_extent, mask_area_km2, max_extent_mask
from .config import MAX_AOI_INVALID_FRAC, RESERVOIRS, Reservoir
from .provenance import RunLog
from .sentinel2 import (
    dedupe_items,
    load_scenes,
    offsets_by_solar_day,
    search_items,
    to_reflectance,
    valid_mask,
)

logger = logging.getLogger("moroccowater.pipeline")

# These reads are dominated by per-request latency against blob storage, so the
# useful knob is concurrency, not cores. A full-year batch previously ran at 4%
# CPU for 90 minutes before its signed URLs expired mid-graph.
IO_THREADS = 32
GDAL_ENV = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",  # don't probe for sidecar files
    GDAL_HTTP_MULTIPLEX="YES",
    GDAL_HTTP_VERSION="2",
    GDAL_HTTP_MAX_RETRY="5",
    GDAL_HTTP_RETRY_DELAY="1",
    VSI_CACHE=True,
    # rasterio passes these straight to GDALSetCacheMax64 / the VSI cache, which
    # require integers -- strings raise "an integer is required".
    VSI_CACHE_SIZE=33554432,  # 32 MB
    GDAL_CACHEMAX=512,        # MB
)

DATA = Path(__file__).resolve().parents[2] / "data"
WATER_RULES = ("combined", "ndwi")
AREA_COLS = tuple(f"area_{r}_km2" for r in WATER_RULES)
PRIMARY_AREA_COL = "area_combined_km2"


def _measure_batch(items, reservoir, aoi, offsets, runlog, chunks) -> pd.DataFrame:
    """Load, correct, classify and measure one batch of scenes.

    Everything happens inside one `rasterio.Env` and one dask config so the
    signed URLs built here are read here, within the token's lifetime.
    """
    ds = load_scenes(items, reservoir, runlog, geobox=aoi.odc.geobox, chunks=chunks)
    ds = to_reflectance(ds, offsets, runlog)
    with rasterio.Env(**GDAL_ENV), dask.config.set(
        scheduler="threads", num_workers=IO_THREADS
    ):
        checks.check_reflectance_range(ds, ["B03", "B08", "B11"], sample=1)

    valid = valid_mask(ds)
    idx = water.compute_indices(ds)
    masks = {
        "combined": water.water_mask_combined(idx),  # Bounif et al., validated here
        "ndwi": water.water_mask_ndwi(idx),          # the brief's rule, for comparison
    }
    with rasterio.Env(**GDAL_ENV), dask.config.set(
        scheduler="threads", num_workers=IO_THREADS
    ):
        return water.scene_table(masks, valid, aoi, reservoir.resolution)


def run(
    reservoir: Reservoir,
    start: str,
    end: str,
    outdir: Path | None = None,
    batchdir: Path | None = None,
    limit: int | None = None,
    resume: bool = True,
    chunks: dict[str, int] | None = None,
) -> dict:
    outdir = outdir or (DATA / "processed")
    # Resolution is part of the cache key: 20 m and 60 m batches are not
    # interchangeable, and silently reusing one for the other would be a
    # confusing way to get wrong areas.
    batchdir = batchdir or (
        DATA / "interim" / f"{reservoir.slug}_batches_{int(reservoir.resolution)}m"
    )
    outdir.mkdir(parents=True, exist_ok=True)
    batchdir.mkdir(parents=True, exist_ok=True)
    # Small chunks keep each batch's working set bounded; see the module docstring.
    chunks = chunks or {"time": 1, "x": 512, "y": 512}

    runlog = RunLog(f"{reservoir.slug}_area_{start}_{end}")
    runlog.event("reservoir", name=reservoir.name, bbox=reservoir.bbox,
                 notes=reservoir.notes)

    # 1. Analysis mask: published maximum extent, not a hand-drawn polygon.
    aoi = crop_to_extent(max_extent_mask(reservoir, runlog))
    aoi_km2 = mask_area_km2(aoi, reservoir.resolution)
    runlog.event("aoi", area_km2=round(aoi_km2, 2),
                 published_max_km2=reservoir.max_area_km2)
    logger.info("AOI max-extent area: %.1f km² (published max %s km²)",
                aoi_km2, reservoir.max_area_km2)

    # 2. Scenes, with superseded reprocessings removed.
    items = dedupe_items(search_items(reservoir, start, end, runlog), runlog)
    if limit:
        items = items[:limit]
        runlog.assume(f"Development run limited to the first {limit} scenes.")
    if not items:
        raise RuntimeError("no Sentinel-2 scenes found")

    # 3. Radiometry: one offset per solar day, read from per-item metadata.
    offsets = offsets_by_solar_day(items, runlog)

    # 4. Measure, one year at a time.
    # Monthly batches. A year's worth of reads takes longer than a PC SAS token
    # lives, so the batch is sized to finish well inside it.
    buckets: dict[str, list] = {}
    for it in items:
        buckets.setdefault(f"{it.datetime:%Y-%m}", []).append(it)

    frames, failed = [], []
    for n, key in enumerate(sorted(buckets), start=1):
        path = batchdir / f"{key}.parquet"
        if resume and path.exists():
            frames.append(pd.read_parquet(path))
            continue
        batch = buckets[key]
        try:
            df = _measure_batch(batch, reservoir, aoi, offsets, runlog, chunks)
        except Exception as exc:  # noqa: BLE001 - raster/network failures vary
            failed.append({"batch": key, "n_items": len(batch), "error": str(exc)[:200]})
            logger.error("[%d/%d] %s FAILED: %s", n, len(buckets), key, str(exc)[:200])
            continue
        df.to_parquet(path, index=False)
        frames.append(df)
        logger.info(
            "[%d/%d] %s: %d scene(s), %s %.1f-%.1f km²",
            n, len(buckets), key, len(df), PRIMARY_AREA_COL,
            df[PRIMARY_AREA_COL].min(), df[PRIMARY_AREA_COL].max(),
        )

    if failed:
        runlog.event("batches_failed", n=len(failed), detail=failed[:20])
        logger.warning("%d of %d monthly batches failed; rerun to retry them",
                       len(failed), len(buckets))
    if not frames:
        raise RuntimeError("every batch failed")

    df = pd.concat(frames, ignore_index=True).sort_values("time").reset_index(drop=True)
    runlog.event("scenes_measured", n=len(df), n_batches=len(buckets),
                 n_batches_failed=len(failed))

    # 5. Checks.
    for col in AREA_COLS:
        checks.check_area_bounds(df, reservoir, col)
    disc = checks.check_offset_discontinuity(df, PRIMARY_AREA_COL)
    runlog.event("offset_discontinuity", **disc)

    # 6. Monthly aggregate, gaps left as gaps.
    min_valid = 1.0 - MAX_AOI_INVALID_FRAC
    mon = water.monthly(df, PRIMARY_AREA_COL, min_valid_frac=min_valid)
    checks.check_monthly_coverage(mon)
    mon = checks.flag_area_jumps(mon)

    # 7. Volume, from the published curve.
    mon["volume_mm3"] = volume.area_to_volume(mon["area_km2"])
    runlog.event("volume_relationship", **volume.describe())
    runlog.assume(
        "Volume uses Bounif et al.'s published area-volume polynomial with an "
        "INFERRED coefficient order; absolute volumes are provisional."
    )

    # 8. Write.
    scenes_path = outdir / f"{reservoir.slug}_scene_area.parquet"
    monthly_path = outdir / f"{reservoir.slug}_monthly_area.parquet"
    df.to_parquet(scenes_path, index=False)
    mon.to_parquet(monthly_path, index=False)
    prov_path = runlog.write(outdir / f"{reservoir.slug}_provenance.json")

    usable = df[PRIMARY_AREA_COL].where(df["valid_frac"] >= min_valid).dropna()
    summary = {
        "reservoir": reservoir.name,
        "aoi_area_km2": round(aoi_km2, 2),
        "published_max_area_km2": reservoir.max_area_km2,
        "n_scenes_measured": len(df),
        "n_batches_failed": len(failed),
        "n_scenes_usable": int(len(usable)),
        "n_months": len(mon),
        "months_covered": f"{mon['month'].min():%Y-%m}..{mon['month'].max():%Y-%m}",
        "area_km2_min": round(float(mon["area_km2"].min()), 2),
        "area_km2_max": round(float(mon["area_km2"].max()), 2),
        "n_suspicious_jumps": int(mon["suspicious_jump"].sum()),
        "offset_discontinuity": disc,
        "outputs": {"scenes": str(scenes_path), "monthly": str(monthly_path),
                    "provenance": str(prov_path)},
    }
    logger.info("summary: %s", json.dumps(summary, indent=2, default=str))
    return summary


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reservoir", default="al_massira", choices=sorted(RESERVOIRS))
    p.add_argument("--start", default="2016-01-01")
    p.add_argument("--end", default="2026-11-05")
    p.add_argument("--limit", type=int, default=None,
                   help="use only the first N scenes (development)")
    p.add_argument("--resolution", type=float, default=None,
                   help="metres; overrides the reservoir default (20). 60 reads "
                        "from the COGs' internal overviews and is far cheaper, "
                        "at the cost of shoreline precision.")
    p.add_argument("--no-resume", action="store_true",
                   help="recompute yearly batches even if they exist")
    p.add_argument("--outdir", type=Path, default=None)
    p.add_argument("-v", "--verbose", action="store_true")
    a = p.parse_args()

    logging.basicConfig(
        level=logging.INFO if a.verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    # GDAL/rasterio chatter about transient 503s from blob storage is noise;
    # the reads retry and succeed.
    logging.getLogger("rasterio._err").setLevel(logging.ERROR)

    reservoir = RESERVOIRS[a.reservoir]
    if a.resolution:
        reservoir = replace(reservoir, resolution=a.resolution)
    summary = run(reservoir, a.start, a.end, outdir=a.outdir,
                  limit=a.limit, resume=not a.no_resume)
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
