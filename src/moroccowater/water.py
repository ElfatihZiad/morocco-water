"""Water classification and per-scene area measurement."""

from __future__ import annotations

import logging

import pandas as pd
import xarray as xr

from .indices import awei_sh, mndwi, ndvi, ndwi

logger = logging.getLogger("moroccowater.water")


def compute_indices(ds: xr.Dataset) -> xr.Dataset:
    """All four indices from a reflectance dataset."""
    return xr.Dataset(
        {
            "ndwi": ndwi(ds["B03"], ds["B08"]),
            "mndwi": mndwi(ds["B03"], ds["B11"]),
            "ndvi": ndvi(ds["B08"], ds["B04"]),
            "awei_sh": awei_sh(ds["B02"], ds["B03"], ds["B08"], ds["B11"], ds["B12"]),
        }
    )


def water_mask_ndwi(idx: xr.Dataset, threshold: float = 0.0) -> xr.DataArray:
    """NDWI above a fixed threshold.

    # ASSUMPTION: threshold 0.0, McFeeters' conventional value. It is scene
    # dependent and unvalidated on this reservoir -- which is why the combined
    # rule below, validated on Al Massira, is the reference.
    """
    return (idx["ndwi"] >= threshold).rename("water_ndwi")


def water_mask_combined(idx: xr.Dataset) -> xr.DataArray:
    """The rule Bounif et al. (2023) validated on Al Massira at r = 0.97.

    MNDWI >= 0 AND NDWI >= 0 AND NDVI <= 0 AND AWEI >= 0. Reproducing a method
    validated on this exact reservoir beats inventing one.
    """
    return (
        (idx["mndwi"] >= 0) & (idx["ndwi"] >= 0) & (idx["ndvi"] <= 0) & (idx["awei_sh"] >= 0)
    ).rename("water_combined")


def scene_table(
    water: dict[str, xr.DataArray],
    valid: xr.DataArray,
    aoi: xr.DataArray,
    resolution: float,
) -> pd.DataFrame:
    """Per-scene areas for each water definition, plus quality columns.

    Areas are measured per scene and aggregated later -- never from a monthly
    pixel composite, which would blend shorelines from different dates into a
    margin that existed on no real day.
    """
    px_km2 = (resolution**2) / 1e6
    aoi_px = float(aoi.sum())
    if aoi_px == 0:
        raise ValueError("empty AOI mask: nothing to measure")

    in_aoi = valid & aoi
    valid_px = in_aoi.sum(dim=("y", "x"))

    out = {
        "valid_frac": (valid_px / aoi_px).astype("float32"),
        "invalid_frac": (1.0 - valid_px / aoi_px).astype("float32"),
    }
    for label, mask in water.items():
        wet = (mask & in_aoi).sum(dim=("y", "x"))
        out[f"area_{label}_km2"] = (wet * px_km2).astype("float32")
        # Area if every unobserved AOI pixel were water: an upper bound that
        # makes cloud-driven underestimation visible instead of invisible.
        out[f"area_{label}_upper_km2"] = (
            (wet + (aoi.sum() - valid_px)) * px_km2
        ).astype("float32")

    df = xr.Dataset(out).to_dataframe().reset_index()
    df["aoi_area_km2"] = aoi_px * px_km2
    return df.sort_values("time").reset_index(drop=True)


def monthly(df: pd.DataFrame, area_col: str, min_valid_frac: float) -> pd.DataFrame:
    """Aggregate per-scene areas to monthly, keeping gaps as gaps.

    Months with no usable scene are absent, not interpolated. `n_scenes` travels
    with every value so a one-observation month is never mistaken for a
    well-sampled one.
    """
    usable = df.loc[df["valid_frac"] >= min_valid_frac].copy()
    usable["month"] = pd.PeriodIndex(usable["time"], freq="M").to_timestamp()
    g = usable.groupby("month")[area_col]
    out = pd.DataFrame(
        {
            "area_km2": g.median(),      # median, not mean: robust to one bad scene
            "area_min_km2": g.min(),
            "area_max_km2": g.max(),
            "n_scenes": g.size(),
        }
    ).reset_index()
    return out
