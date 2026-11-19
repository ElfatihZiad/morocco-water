"""Sentinel-2 L2A access: STAC search, the 2022 offset, cloud masking, floats.

The three rules from CLAUDE.md that this module exists to enforce:
  1. cast to float and NaN the nodata before any arithmetic;
  2. convert to true reflectance, reading the offset from metadata;
  3. log every source.
"""

from __future__ import annotations

import datetime as dt
import logging

import pandas as pd
import planetary_computer as pc
import xarray as xr
from odc.stac import load as odc_load
from pystac.item import Item
from pystac_client import Client

from .config import (
    COLLECTION_S2,
    MAX_SCENE_CLOUD_COVER,
    S2_BANDS,
    S2_BASELINE_OFFSET_DATE,
    S2_FALLBACK_OFFSET,
    S2_FALLBACK_SCALE,
    SCL_INVALID,
    STAC_URL,
    Reservoir,
)
from .provenance import RunLog

logger = logging.getLogger("moroccowater.sentinel2")

_BASELINE_DATE = dt.date.fromisoformat(S2_BASELINE_OFFSET_DATE)


def open_catalog(sign: bool = False) -> Client:
    """Planetary Computer STAC client.

    Signing is OFF by default and deliberately so. `pc.sign_inplace` rewrites
    asset hrefs with a SAS token at SEARCH time, but odc-stac builds a lazy dask
    graph that may not read those hrefs for an hour or more. PC's tokens expire
    in well under that, and the failure is ugly and late: reads return zero
    bytes and GDAL raises "TIFFFillTile: got 0 bytes" / "Chunk and warp failed"
    partway through a long run.

    Instead the hrefs stay unsigned here and `patch_url=pc.sign` signs them when
    each load is constructed -- so freshness is tied to the batch, not to the
    search. Keep batches comfortably shorter than the token lifetime.
    """
    return Client.open(STAC_URL, modifier=pc.sign_inplace if sign else None)


def search_items(
    reservoir: Reservoir,
    start: str,
    end: str,
    runlog: RunLog,
    max_cloud_cover: float = MAX_SCENE_CLOUD_COVER,
) -> list[Item]:
    """Find Sentinel-2 L2A scenes over the reservoir.

    The cloud filter here is a cheap tile-level prefilter only; the decision that
    actually matters is the AOI-level invalid fraction computed after masking.
    """
    cat = open_catalog()
    search = cat.search(
        collections=[COLLECTION_S2],
        bbox=list(reservoir.bbox),
        datetime=f"{start}/{end}",
        query={"eo:cloud_cover": {"lt": max_cloud_cover}},
    )
    items = list(search.items())
    items.sort(key=lambda i: i.datetime)

    runlog.source(
        collection=COLLECTION_S2,
        endpoint=STAC_URL,
        bbox=reservoir.bbox,
        datetime=f"{start}/{end}",
        filter=f"eo:cloud_cover < {max_cloud_cover}",
        assets=list(S2_BANDS),
        item_ids=[i.id for i in items],
        n_items=len(items),
        mgrs_tiles=sorted({i.properties.get("s2:mgrs_tile") for i in items}),
    )
    return items


def _baseline_to_float(baseline: str | None) -> float | None:
    """'04.00' -> 4.0. Returns None if unparseable."""
    if not baseline:
        return None
    try:
        return float(str(baseline).strip())
    except ValueError:
        return None


def resolve_offset(item: Item, band: str = "B03") -> tuple[float, float, str]:
    """Return (scale, offset, provenance) for converting DN to reflectance.

    Three tiers, best first:

    1. `raster:bands` scale/offset on the asset -- the authoritative STAC route.
    2. `s2:processing_baseline` -- baseline >= 04.00 carries BOA_ADD_OFFSET
       -1000. Still reading the offset from per-item metadata, just indirectly.
    3. The acquisition-date rule (>= 2022-01-25), with a warning.

    Tier 1 is unavailable on Planetary Computer: verified 2026-11-03 that
    `sentinel-2-l2a` publishes no raster:bands scale/offset on items or in
    collection item_assets, for either pre- or post-baseline-04.00 scenes. Tier 2
    is therefore the normal path here, which is why it is not logged as a
    fallback. See docs/decisions.md.
    """
    asset = item.assets.get(band)
    if asset is not None:
        rb = asset.extra_fields.get("raster:bands")
        if isinstance(rb, list) and rb:
            entry = rb[0] or {}
            scale, offset = entry.get("scale"), entry.get("offset")
            if scale is not None and offset is not None:
                # STAC convention: value = DN * scale + offset
                return float(1.0 / scale), float(offset / scale), "raster:bands"

    raw_baseline = item.properties.get("s2:processing_baseline")
    baseline = _baseline_to_float(raw_baseline)
    if baseline is not None:
        offset = S2_FALLBACK_OFFSET if baseline >= 4.0 else 0.0
        return S2_FALLBACK_SCALE, offset, f"s2:processing_baseline={raw_baseline}"

    acquired = item.datetime.date()
    offset = S2_FALLBACK_OFFSET if acquired >= _BASELINE_DATE else 0.0
    logger.warning(
        "%s has neither raster:bands nor a parseable s2:processing_baseline "
        "(%r); falling back to the acquisition-date rule: offset=%s",
        item.id,
        raw_baseline,
        offset,
    )
    return S2_FALLBACK_SCALE, offset, f"fallback-date-rule(baseline={raw_baseline!r})"


def dedupe_items(items: list[Item], runlog: RunLog) -> list[Item]:
    """Drop superseded reprocessings of the same acquisition.

    Planetary Computer's sentinel-2-l2a archive holds the SAME acquisition more
    than once when ESA has reprocessed it: identical tile and sensing time, two
    STAC items, different `s2:processing_baseline`. Over Al Massira, the
    2021-12-12 and 2021-12-27 acquisitions each appear as both baseline 03.00
    (processed the next day) and baseline 04.00 (reprocessed in Jan 2023).

    This matters twice over. The duplicates straddle the 04.00 boundary, so the
    two copies carry DIFFERENT radiometric offsets -- mosaicking them into one
    solar day would mix corrected and uncorrected reflectance in a single image.
    And an acquisition-date rule would get the reprocessed copies wrong, because
    their sensing date is 2021 while their radiometry is post-04.00.

    We keep the highest baseline per (tile, sensing time): a reprocessing
    supersedes the original.
    """
    rows = [
        {
            "i": i,
            "tile": it.properties.get("s2:mgrs_tile"),
            "sensed": it.datetime,
            "baseline": _baseline_to_float(it.properties.get("s2:processing_baseline")) or -1.0,
            "raw_baseline": it.properties.get("s2:processing_baseline"),
            "id": it.id,
        }
        for i, it in enumerate(items)
    ]
    df = pd.DataFrame(rows)
    # Sort so the winner of each group is last, then keep the last.
    df = df.sort_values(["tile", "sensed", "baseline", "id"])
    keep = df.groupby(["tile", "sensed"], dropna=False).tail(1)
    dropped = df.loc[~df.index.isin(keep.index)]

    if len(dropped):
        runlog.event(
            "superseded_items_dropped",
            n_dropped=len(dropped),
            n_kept=len(keep),
            examples=[
                {"dropped": r.id, "dropped_baseline": r.raw_baseline}
                for r in dropped.head(6).itertuples()
            ],
        )
        logger.warning(
            "dropped %d superseded reprocessing(s) of %d acquisitions "
            "(same tile + sensing time, lower processing baseline)",
            len(dropped), len(keep),
        )
    return [items[i] for i in sorted(keep["i"].tolist(), key=lambda i: items[i].datetime)]


def offsets_by_solar_day(items: list[Item], runlog: RunLog) -> pd.DataFrame:
    """One (scale, offset) per solar day, since odc-stac groups scenes that way.

    Asserts the items sharing a solar day agree, rather than silently taking the
    first -- a disagreement would mean mixed baselines inside one time step.
    """
    rows = []
    for it in items:
        scale, offset, how = resolve_offset(it)
        rows.append(
            {
                "solar_day": pd.Timestamp(it.datetime.date()),
                "scale": scale,
                "offset": offset,
                "how": how,
                "baseline": it.properties.get("s2:processing_baseline"),
                "item_id": it.id,
            }
        )
    df = pd.DataFrame(rows)

    inconsistent = (
        df.groupby("solar_day")[["scale", "offset"]].nunique().gt(1).any(axis=1)
    )
    if inconsistent.any():
        bad = inconsistent[inconsistent].index.tolist()
        raise ValueError(
            f"mixed scale/offset within a solar day for {bad!r}: refusing to "
            "collapse scenes with different radiometric calibration into one "
            "mosaic. Usually this means superseded reprocessings were not "
            "removed -- call dedupe_items() before this."
        )

    per_day = df.groupby("solar_day").first().reset_index()
    tier = per_day["how"].str.split("=").str[0].str.replace(
        "fallback-date-rule", "date-rule", regex=False
    )
    runlog.event(
        "offsets_resolved",
        n_days=len(per_day),
        by_source=tier.value_counts().to_dict(),
        baselines=sorted({b for b in per_day["baseline"].dropna().unique()}),
        offsets=sorted(per_day["offset"].unique().tolist()),
        n_days_offset_applied=int((per_day["offset"] != 0).sum()),
    )
    n_date_rule = int(tier.eq("date-rule").sum())
    if n_date_rule:
        runlog.assume(
            f"{n_date_rule} solar day(s) had neither raster:bands nor a parseable "
            f"processing baseline; the >= {S2_BASELINE_OFFSET_DATE} acquisition-date "
            f"rule was used instead (offset {S2_FALLBACK_OFFSET})."
        )
    runlog.assume(
        "Planetary Computer publishes no raster:bands scale/offset for "
        "sentinel-2-l2a (verified 2026-11-03), so the radiometric offset is "
        "derived from s2:processing_baseline (>= 04.00 implies BOA_ADD_OFFSET "
        "-1000) rather than read directly per band."
    )
    return per_day


def load_scenes(
    items: list[Item],
    reservoir: Reservoir,
    runlog: RunLog,
    geobox=None,
    chunks: dict[str, int] | None = None,
) -> xr.Dataset:
    """Load the bands as a lazy, reflectance-scaled time stack.

    Pass `geobox` (from the cropped AOI mask) to load scenes directly onto the
    AOI's grid. That both shrinks the read to the area we actually measure and
    removes any alignment step between scenes and mask -- they are the same grid
    by construction, so no resampling can creep in between them.
    """
    # One spatial chunk per scene: the AOI is small (~780x1613 px), so splitting
    # it only multiplies the number of range requests, and requests are the
    # bottleneck -- a full-year run sat at 4% CPU waiting on the network.
    chunks = chunks or {"time": 1, "x": 4096, "y": 4096}
    common = dict(
        bands=S2_BANDS,
        groupby="solar_day",
        # SCL is categorical: averaging class codes would be meaningless.
        resampling={"SCL": "nearest", "*": "bilinear"},
        chunks=chunks,
        patch_url=pc.sign,
    )
    if geobox is not None:
        ds = odc_load(items, geobox=geobox, **common)
    else:
        ds = odc_load(
            items,
            crs=f"EPSG:{reservoir.epsg}",
            resolution=reservoir.resolution,
            bbox=reservoir.bbox,
            **common,
        )
    runlog.event(
        "loaded",
        crs=f"EPSG:{reservoir.epsg}",
        resolution=reservoir.resolution,
        on_aoi_geobox=geobox is not None,
        shape={str(k): int(v) for k, v in ds.sizes.items()},
        bands=list(ds.data_vars),
    )
    return ds


def to_reflectance(ds: xr.Dataset, offsets: pd.DataFrame, runlog: RunLog) -> xr.Dataset:
    """Convert integer DNs to float reflectance, applying the per-day offset.

    Why this matters, in one line: a normalised difference is invariant to a
    multiplicative scale but NOT to an additive offset, so mixing corrected and
    uncorrected scenes puts a step change in the time series at 2022-01-25 --
    the exact moment we are trying to measure a trend.
    """
    spectral = [b for b in ds.data_vars if b != "SCL"]

    idx = offsets.set_index("solar_day")
    times = pd.DatetimeIndex(ds.time.values).normalize()
    missing = times.difference(idx.index)
    if len(missing):
        raise KeyError(f"no resolved offset for solar day(s): {list(missing)[:5]}")

    # float32 throughout: these arrays are large, and float64 would double the
    # memory for no gain at Sentinel-2's radiometric precision.
    scale = xr.DataArray(
        idx.loc[times, "scale"].to_numpy(dtype="float32"),
        dims="time", coords={"time": ds.time},
    )
    offset = xr.DataArray(
        idx.loc[times, "offset"].to_numpy(dtype="float32"),
        dims="time", coords={"time": ds.time},
    )

    out = ds.copy()
    for band in spectral:
        # Cast to float and NaN the nodata BEFORE arithmetic: these arrive as
        # uint16 where 0 is nodata, and `green - nir` on unsigned ints wraps
        # around instead of going negative.
        dn = out[band].where(out[band] != 0).astype("float32")
        out[band] = ((dn + offset) / scale).astype("float32")
        out[band].attrs["units"] = "reflectance"

    runlog.event("reflectance_applied", bands=spectral)
    return out


def valid_mask(ds: xr.Dataset) -> xr.DataArray:
    """True where the pixel is usable, from the Scene Classification Layer."""
    scl = ds["SCL"]
    invalid = xr.zeros_like(scl, dtype=bool)
    for code in SCL_INVALID:
        invalid = invalid | (scl == code)
    return (~invalid).rename("valid")
