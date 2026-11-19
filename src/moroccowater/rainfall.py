"""Basin rainfall.

TerraClimate first because it is Planetary-Computer-native and unblocks the
comparison; CHIRPS is the one the Moroccan validation literature actually used
and goes behind the same interface next. See docs/mvp-plan.md.
"""

from __future__ import annotations

import logging

import pandas as pd
import planetary_computer as pc
import xarray as xr

from .config import COLLECTION_TERRACLIMATE, STAC_URL, Reservoir
from .provenance import RunLog
from .sentinel2 import open_catalog

logger = logging.getLogger("moroccowater.rainfall")


class CoverageError(RuntimeError):
    """The requested period is not fully covered by the dataset."""


def _open_terraclimate() -> tuple[xr.Dataset, str]:
    """Open the TerraClimate zarr store.

    Uses the `zarr-abfs` asset rather than `zarr-https`: the https href carries
    its SAS token as a query string, and fsspec appends store paths AFTER it
    ("...terraclimate.zarr?<sas>/.zmetadata"), which the service rejects with a
    403. The abfs asset passes the credential through storage_options instead,
    so paths are joined correctly.
    """
    col = open_catalog().get_collection(COLLECTION_TERRACLIMATE)
    asset = pc.sign(col.assets["zarr-abfs"])
    kwargs = dict(asset.extra_fields.get("xarray:open_kwargs") or {})
    kwargs.setdefault("engine", "zarr")
    kwargs.setdefault("consolidated", True)
    kwargs.setdefault("chunks", {})
    return xr.open_dataset(asset.href, **kwargs), asset.href


def basin_precipitation(
    reservoir: Reservoir,
    start: str,
    end: str,
    runlog: RunLog,
    variable: str = "ppt",
) -> pd.DataFrame:
    """Monthly catchment-mean precipitation (mm) upstream of the dam.

    Spatial mean over the contributing catchment, not over the reservoir: what
    fills Al Massira is runoff from the Atlas headwaters, not rain landing on
    the lake.
    """
    ds, href = _open_terraclimate()
    lon0, lat0, lon1, lat1 = reservoir.catchment_bbox

    # TerraClimate's lat descends, so slice in the stored order.
    lat_slice = slice(lat1, lat0) if ds.lat[0] > ds.lat[-1] else slice(lat0, lat1)
    sub = ds[variable].sel(lon=slice(lon0, lon1), lat=lat_slice,
                           time=slice(start, end))
    if sub.sizes.get("lon", 0) == 0 or sub.sizes.get("lat", 0) == 0:
        raise ValueError(f"empty catchment selection for bbox {reservoir.catchment_bbox}")

    # Coverage check BEFORE averaging. TerraClimate on PC ends 2021-12-01, so a
    # naive request for 2016-2026 silently returns only the first six years --
    # and a .sum() over the result would read as a catastrophic drought that
    # never happened. Catch the truncation instead of propagating it.
    requested = pd.period_range(start=start, end=end, freq="M")
    available = pd.PeriodIndex(pd.to_datetime(sub.time.values), freq="M")
    missing = requested.difference(available)
    if len(missing):
        raise CoverageError(
            f"{variable} covers {available.min()}..{available.max()} but "
            f"{start}..{end} was requested; {len(missing)} month(s) missing "
            f"(first {missing.min()}, last {missing.max()}). TerraClimate on "
            "Planetary Computer stops at 2021-12; use CHIRPS for anything later."
        )

    series = sub.mean(dim=("lat", "lon")).compute()
    if bool(series.isnull().any()):
        n = int(series.isnull().sum())
        raise CoverageError(f"{n} month(s) of {variable} are NaN over the catchment")
    df = pd.DataFrame(
        {"month": pd.to_datetime(series.time.values).to_period("M").to_timestamp(),
         "precip_mm": series.values.astype("float32")}
    )

    runlog.source(
        collection=COLLECTION_TERRACLIMATE,
        endpoint=STAC_URL,
        store=href,
        variable=variable,
        bbox=reservoir.catchment_bbox,
        datetime=f"{start}/{end}",
        n_months=len(df),
        grid={"lat": int(sub.sizes["lat"]), "lon": int(sub.sizes["lon"])},
        note="catchment-mean monthly precipitation upstream of the dam",
    )
    runlog.assume(
        "Rainfall is TerraClimate (~4 km monthly), a PC-native stand-in for "
        "CHIRPS, averaged over a BBOX approximation of the upstream catchment. "
        "Both choices are provisional: CHIRPS is the dataset Moroccan validation "
        "work used, and a real watershed delineation would sharpen the signal."
    )
    return df
