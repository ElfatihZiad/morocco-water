"""Sanity checks that raise.

CLAUDE.md: assertions that "would fail loudly on a bad pipeline, not quietly
produce a plot". Everything here raises SanityError rather than warning, except
the explicitly advisory `flag_*` functions.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import xarray as xr

from .config import AREA_CEILING_TOLERANCE, MAX_MONTHLY_AREA_JUMP, Reservoir

logger = logging.getLogger("moroccowater.checks")


class SanityError(AssertionError):
    """A derived quantity is physically impossible or inconsistent."""


def check_reflectance_range(
    ds: xr.Dataset,
    bands: list[str],
    valid: xr.DataArray | None = None,
    sample: int = 3,
) -> None:
    """Reflectance must land in a plausible physical range on USABLE pixels.

    `valid` is the SCL-derived mask. Passing it is important rather than
    cosmetic: cloud tops legitimately exceed 1.0 reflectance, so a fully-clouded
    scene has a perfectly valid median above 1.0 and a maximum near 1.7. Judging
    the offset on all pixels therefore rejects good data for being cloudy -- it
    cost four months of the Al Massira series before `valid` was threaded in.
    Restricting to unmasked pixels also makes the check *more* sensitive, because
    a misapplied offset is no longer hidden among cloud outliers.

    Bounds are checked on percentiles, not the extremes: a handful of saturated
    pixels says nothing about whether the radiometry is right. The signature of a
    wrongly applied offset is the dark end going negative; the signature of a
    scale error is everything inflating together.

    A scene with no usable pixels is not an error (see the module note on empty
    scenes); only a batch where every sampled scene is unusable is.
    """
    for band in bands:
        da = ds[band].isel(time=slice(0, max(sample, 1)))
        if valid is not None:
            da = da.where(valid.isel(time=slice(0, max(sample, 1))))
        n_time = da.sizes.get("time", 1)
        n_empty, seen = 0, False

        for i in range(n_time):
            slab = da.isel(time=i) if "time" in da.dims else da
            arr = slab.values.ravel()
            arr = arr[np.isfinite(arr)]
            if arr.size == 0:
                n_empty += 1
                continue
            seen = True
            lo, hi = (float(x) for x in np.percentile(arr, [0.1, 99.9]))
            amin, amax = float(arr.min()), float(arr.max())
            if lo < -0.1 or hi > 1.6:
                raise SanityError(
                    f"{band}: usable-pixel reflectance outside [-0.1, 1.6] "
                    f"(p0.1={lo:.3f}, p99.9={hi:.3f}, min={amin:.3f}, "
                    f"max={amax:.3f}) -- offset/scale almost certainly misapplied"
                )
            if amin < -0.5 or amax > 3.0:
                raise SanityError(
                    f"{band}: absolute reflectance {amin:.3f}..{amax:.3f} is "
                    "implausible -- check the scale factor"
                )
            logger.info("%s scene %d usable reflectance p0.1..p99.9 = %.3f..%.3f",
                        band, i, lo, hi)

        if not seen:
            raise SanityError(
                f"{band}: none of the {n_time} sampled scene(s) has a usable "
                "pixel over the AOI -- check the geobox, the AOI mask, the SCL "
                "classes treated as invalid, and the offset"
            )
        if n_empty:
            logger.info("%s: %d of %d sampled scene(s) unusable over the AOI "
                        "(kept; the valid_frac gate drops them)",
                        band, n_empty, n_time)


def check_index_range(idx: xr.Dataset, names=("ndwi", "mndwi", "ndvi")) -> None:
    """Normalised differences are bounded by [-1, 1] by construction."""
    for name in names:
        da = idx[name]
        lo, hi = (float(v) for v in (da.min(), da.max()))
        if lo < -1.0001 or hi > 1.0001:
            raise SanityError(f"{name} outside [-1, 1]: {lo:.4f}..{hi:.4f}")


def check_area_bounds(df: pd.DataFrame, reservoir: Reservoir, area_col: str) -> None:
    """Area is non-negative and within the published maximum plus tolerance."""
    a = df[area_col].dropna()
    if a.empty:
        raise SanityError(f"{area_col}: no values at all")
    if (a < 0).any():
        raise SanityError(f"{area_col}: negative area")
    if reservoir.max_area_km2 is not None:
        ceiling = reservoir.max_area_km2 * (1 + AREA_CEILING_TOLERANCE)
        over = a[a > ceiling]
        if len(over):
            raise SanityError(
                f"{area_col}: {len(over)} value(s) above the {ceiling:.1f} km² "
                f"ceiling (max {over.max():.1f} km²). Published maximum is "
                f"{reservoir.max_area_km2} km² (Bounif et al. 2023). This is a "
                "bug, not a wet year."
            )
    logger.info("%s within bounds: %.1f..%.1f km²", area_col, a.min(), a.max())


def check_monthly_coverage(monthly_df: pd.DataFrame) -> None:
    """Every reported month must rest on at least one scene."""
    if (monthly_df["n_scenes"] < 1).any():
        raise SanityError("a monthly value was reported with zero scenes behind it")


def flag_area_jumps(
    monthly_df: pd.DataFrame, limit: float = MAX_MONTHLY_AREA_JUMP
) -> pd.DataFrame:
    """Flag implausible month-over-month changes -- investigate, don't smooth.

    Advisory by design: a real reservoir CAN move fast (Al Massira gained
    ~984 Mm³ in under a year), so this marks rows for review rather than
    rejecting them.
    """
    out = monthly_df.sort_values("month").copy()
    out["pct_change"] = out["area_km2"].pct_change()
    # Only consecutive months are comparable; a gap is not a jump.
    gap = out["month"].diff().dt.days > 45
    out["suspicious_jump"] = (out["pct_change"].abs() > limit) & ~gap
    n = int(out["suspicious_jump"].sum())
    if n:
        logger.warning(
            "%d month(s) change by more than %.0f%%: %s",
            n, limit * 100,
            out.loc[out["suspicious_jump"], "month"].dt.strftime("%Y-%m").tolist(),
        )
    return out


def check_offset_discontinuity(
    df: pd.DataFrame,
    area_col: str,
    boundary: str = "2022-01-25",
    window_days: int = 365,
    max_rel_step: float = 0.25,
) -> dict:
    """Test for a step change in area across the processing-baseline boundary.

    If the offset correction failed, the index shifts at exactly 2022-01-25 and
    a spurious step appears here. Returns the comparison either way so it can be
    reported rather than merely asserted.
    """
    b = pd.Timestamp(boundary)
    t = pd.to_datetime(df["time"])
    before = df.loc[(t < b) & (t >= b - pd.Timedelta(days=window_days)), area_col].dropna()
    after = df.loc[(t >= b) & (t < b + pd.Timedelta(days=window_days)), area_col].dropna()

    result = {
        "boundary": boundary,
        "n_before": len(before),
        "n_after": len(after),
        "median_before_km2": float(before.median()) if len(before) else None,
        "median_after_km2": float(after.median()) if len(after) else None,
    }
    if len(before) < 3 or len(after) < 3:
        result["verdict"] = "insufficient data"
        return result

    step = (after.median() - before.median()) / before.median()
    result["relative_step"] = float(step)
    result["verdict"] = "step detected" if abs(step) > max_rel_step else "no step"
    # Deliberately not raising: at this reservoir a genuine hydrological change
    # straddles the boundary, so a step here is a prompt to investigate, not
    # proof of a bug. The unit tests are what guard the offset arithmetic.
    logger.info("offset discontinuity check: %s", result)
    return result
