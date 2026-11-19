"""Does the 2022 processing-baseline offset bias the time series, and does our
correction remove it?

The pipeline's discontinuity check reported a -39.6% step in reservoir area
across 2022-01-25. That is ambiguous: the drought genuinely collapsed through
that window, so a real step is expected. This experiment separates the two.

Method: measure a quantity that CANNOT change hydrologically -- the median NDWI
over stable land just outside the reservoir's maximum extent -- for scenes either
side of the boundary, computed twice:

  * with the offset resolved from each item's processing baseline (our pipeline);
  * with the offset forced to zero (what a naive pipeline does).

Land NDWI has no reason to step at an arbitrary processing date. So a step in the
uncorrected series is pure artefact, and its absence in the corrected series is
evidence the correction works. Running it with the offset forced on for every
scene gives the third arm: over-correction.

Run with:
    uv run python -m moroccowater.offset_demo
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

from .aoi import crop_to_extent, max_extent_mask
from .config import RESERVOIRS, Reservoir
from .indices import ndwi
from .pipeline import GDAL_ENV, IO_THREADS
from .provenance import RunLog
from .sentinel2 import (
    dedupe_items,
    load_scenes,
    offsets_by_solar_day,
    search_items,
    to_reflectance,
    valid_mask,
)

logger = logging.getLogger("moroccowater.offset_demo")

BOUNDARY = pd.Timestamp("2022-01-25")
DATA = Path(__file__).resolve().parents[2] / "data"


def _land_ndwi(ds, land, runlog: RunLog) -> pd.Series:
    """Median NDWI over stable land, per scene."""
    nd = ndwi(ds["B03"], ds["B08"])
    masked = nd.where(land)
    with rasterio.Env(**GDAL_ENV), dask.config.set(
        scheduler="threads", num_workers=IO_THREADS
    ):
        med = masked.median(dim=("y", "x")).compute()
    return pd.Series(med.values, index=pd.DatetimeIndex(med.time.values), name="land_ndwi")


def run(
    reservoir: Reservoir,
    months: int = 9,
    resolution: float = 60.0,
    outdir: Path | None = None,
) -> dict:
    outdir = outdir or (DATA / "processed")
    outdir.mkdir(parents=True, exist_ok=True)
    reservoir = replace(reservoir, resolution=resolution)
    runlog = RunLog(f"{reservoir.slug}_offset_demo")

    start = (BOUNDARY - pd.DateOffset(months=months)).strftime("%Y-%m-%d")
    end = (BOUNDARY + pd.DateOffset(months=months)).strftime("%Y-%m-%d")

    aoi = crop_to_extent(max_extent_mask(reservoir, runlog))
    items = dedupe_items(search_items(reservoir, start, end, runlog), runlog)
    offsets = offsets_by_solar_day(items, runlog)

    raw = load_scenes(items, reservoir, runlog, geobox=aoi.odc.geobox)

    # Stable land: inside the analysis box, outside the reservoir's maximum
    # extent, and classified usable. Nothing hydrological happens here, so any
    # step in its NDWI is an artefact of processing, not of the drought.
    valid = valid_mask(raw)
    land = (~aoi) & valid

    arms = {
        "corrected": offsets,                                   # our pipeline
        "uncorrected": offsets.assign(offset=0.0),              # naive
        "over_corrected": offsets.assign(offset=-1000.0),       # offset applied to all
    }
    series = {}
    for label, off in arms.items():
        ds = to_reflectance(raw, off, runlog)
        series[label] = _land_ndwi(ds, land, runlog)
        logger.info("%s: %d scenes", label, series[label].notna().sum())

    df = pd.DataFrame(series)
    df.index.name = "time"
    df = df.reset_index()
    df["post_boundary"] = df["time"] >= BOUNDARY

    result = {
        "reservoir": reservoir.name,
        "window": f"{start}..{end}",
        "boundary": str(BOUNDARY.date()),
        "resolution_m": resolution,
        "n_scenes": int(len(df)),
        "n_before": int((~df["post_boundary"]).sum()),
        "n_after": int(df["post_boundary"].sum()),
        "baselines": sorted(offsets["baseline"].dropna().unique().tolist()),
        "arms": {},
    }
    for label in arms:
        before = df.loc[~df["post_boundary"], label].dropna()
        after = df.loc[df["post_boundary"], label].dropna()
        if len(before) < 3 or len(after) < 3:
            result["arms"][label] = {"verdict": "insufficient data"}
            continue
        step = float(after.median() - before.median())
        result["arms"][label] = {
            "median_before": round(float(before.median()), 4),
            "median_after": round(float(after.median()), 4),
            "absolute_step": round(step, 4),
            "n_before": len(before),
            "n_after": len(after),
        }

    # The headline: how much of the apparent step the correction removes.
    corr = result["arms"].get("corrected", {}).get("absolute_step")
    unco = result["arms"].get("uncorrected", {}).get("absolute_step")
    if corr is not None and unco is not None:
        result["artefact_removed"] = round(abs(unco) - abs(corr), 4)
        result["verdict"] = (
            "correction removes the step" if abs(corr) < abs(unco)
            else "correction does NOT reduce the step - investigate"
        )

    df.to_parquet(outdir / f"{reservoir.slug}_offset_demo.parquet", index=False)
    (outdir / f"{reservoir.slug}_offset_demo.json").write_text(
        json.dumps(result, indent=2, default=str)
    )
    runlog.event("offset_demo", **{k: v for k, v in result.items() if k != "arms"})
    runlog.write(outdir / f"{reservoir.slug}_offset_demo_provenance.json")
    return result


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reservoir", default="al_massira", choices=sorted(RESERVOIRS))
    p.add_argument("--months", type=int, default=9)
    p.add_argument("--resolution", type=float, default=60.0)
    p.add_argument("-v", "--verbose", action="store_true")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    logging.getLogger("rasterio._err").setLevel(logging.ERROR)
    print(json.dumps(run(RESERVOIRS[a.reservoir], months=a.months,
                         resolution=a.resolution), indent=2, default=str))


if __name__ == "__main__":
    main()
