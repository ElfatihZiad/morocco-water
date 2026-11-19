"""CHIRPS v3.0 monthly precipitation, read directly from the Climate Hazards Center.

CHIRPS is not on Planetary Computer, and TerraClimate there stops at 2021-12
(see docs/decisions.md), so this is the only route to rainfall over the period
the project is about. v3.0 is used rather than v2.0 because the v3 dataset paper
(Funk et al., Sci. Data 2026) reports v3 capturing observed Moroccan rainfall
variability better than v2, using a Tensift basin case study.

Reads are windowed over the catchment via GDAL's /vsicurl, so each month costs a
range request rather than a global download, and monthly means are cached.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds

from .config import Reservoir
from .provenance import RunLog
from .rainfall import CoverageError

logger = logging.getLogger("moroccowater.chirps")

BASE_URL = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/tifs"
FILE_TEMPLATE = "chirps-v3.0.{year}.{month:02d}.tif"
CHIRPS_NODATA = -9999.0

# The CHC server rate-limits; it returned 429 to rapid HEAD requests during
# development. Be a polite client: one request at a time, with a pause.
REQUEST_PAUSE_S = 1.5  # 0.5 s still drew frequent 429s during development
MAX_RETRIES = 3

GDAL_ENV = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",   # don't probe for sidecars
    CPL_VSIL_CURL_USE_HEAD="NO",                # the server throttles HEAD
    GDAL_HTTP_MAX_RETRY="3",
    GDAL_HTTP_RETRY_DELAY="2",
    GDAL_HTTP_USERAGENT="moroccowater-research/0.1",
)


def month_url(year: int, month: int) -> str:
    return f"{BASE_URL}/{FILE_TEMPLATE.format(year=year, month=month)}"


def _catchment_mean(url: str, bbox: tuple[float, float, float, float]) -> float:
    """Spatial mean of one CHIRPS month over the catchment bbox."""
    lon0, lat0, lon1, lat1 = bbox
    with rasterio.open(f"/vsicurl/{url}") as src:
        window = from_bounds(lon0, lat0, lon1, lat1, transform=src.transform)
        arr = src.read(1, window=window, masked=False).astype("float64")
        nodata = src.nodata if src.nodata is not None else CHIRPS_NODATA
    arr = np.where(arr == nodata, np.nan, arr)
    if arr.size == 0:
        raise ValueError(f"empty window for bbox {bbox} in {url}")
    if np.isnan(arr).all():
        raise ValueError(f"all-nodata window for bbox {bbox} in {url}")
    return float(np.nanmean(arr))


def basin_precipitation(
    reservoir: Reservoir,
    start: str,
    end: str,
    runlog: RunLog,
    cache_path: Path | None = None,
) -> pd.DataFrame:
    """Monthly catchment-mean CHIRPS precipitation (mm) upstream of the dam.

    Months already in the cache are not re-fetched, so extending the series
    costs only the new months.
    """
    months = pd.period_range(start=start, end=end, freq="M")

    cached = pd.DataFrame(columns=["month", "precip_mm"])
    if cache_path and Path(cache_path).exists():
        cached = pd.read_parquet(cache_path)
        cached["month"] = pd.to_datetime(cached["month"])
        logger.info("loaded %d cached CHIRPS months from %s", len(cached), cache_path)

    have = set(pd.PeriodIndex(cached["month"], freq="M")) if len(cached) else set()
    todo = [m for m in months if m not in have]

    rows, failures = [], []
    with rasterio.Env(**GDAL_ENV):
        for i, m in enumerate(todo):
            url = month_url(m.year, m.month)
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    rows.append({"month": m.to_timestamp(),
                                 "precip_mm": _catchment_mean(url, reservoir.catchment_bbox)})
                    break
                except Exception as exc:  # noqa: BLE001 - network/raster errors vary
                    if attempt == MAX_RETRIES:
                        failures.append({"month": str(m), "url": url, "error": str(exc)[:160]})
                        logger.warning("CHIRPS %s failed after %d attempts: %s",
                                       m, MAX_RETRIES, str(exc)[:160])
                    else:
                        time.sleep(2 ** attempt)
            time.sleep(REQUEST_PAUSE_S)
            if i and i % 24 == 0:
                logger.info("CHIRPS: %d/%d months fetched", i, len(todo))

    df = pd.concat([cached, pd.DataFrame(rows)], ignore_index=True) if rows else cached
    df = df.dropna(subset=["month"]).drop_duplicates("month").sort_values("month")
    df = df[pd.PeriodIndex(df["month"], freq="M").isin(months)].reset_index(drop=True)

    if cache_path and rows:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cache_path, index=False)

    runlog.source(
        collection="CHIRPS-v3.0-monthly",
        endpoint=BASE_URL,
        version="v3.0",
        bbox=reservoir.catchment_bbox,
        datetime=f"{start}/{end}",
        n_months=len(df),
        n_fetched=len(rows),
        n_from_cache=len(cached),
        failures=failures,
        note="catchment-mean monthly precipitation, windowed /vsicurl reads",
    )
    runlog.assume(
        "Rainfall is CHIRPS v3.0 averaged over a BBOX approximation of the "
        "catchment upstream of the dam. A real watershed delineation "
        "(HydroBASINS or DEM-derived) would sharpen the signal; a bbox includes "
        "non-contributing area, which damps it rather than inventing one."
    )

    # Same guard that caught the TerraClimate truncation.
    missing = months.difference(pd.PeriodIndex(df["month"], freq="M"))
    if len(missing):
        raise CoverageError(
            f"CHIRPS is missing {len(missing)} month(s) of {start}..{end} "
            f"(first {missing.min()}, last {missing.max()}); "
            f"{len(failures)} fetch failure(s). CHIRPS v3 monthly currently "
            "ends at 2026-09."
        )
    return df
