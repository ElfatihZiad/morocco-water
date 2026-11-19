"""Validation of the derived area series against independent published values.

Four checks, each exercising a different part of the pipeline (docs/mvp-plan.md):

  1. Annual Aug-Sep area vs Bounif et al. (2023)   -> the whole optical chain
  2. Derived volume at dates with reported storage -> the area->volume curve
  3. No step at 2022-01-25                         -> the offset correction
  4. Max-extent area vs the published maximum      -> the AOI mask

These are comparisons against *other people's numbers*, which is the only kind
that can catch a mistake shared by every part of our own pipeline.
"""

from __future__ import annotations

import logging

import pandas as pd

from . import volume

logger = logging.getLogger("moroccowater.validate")

# Bounif et al. (2023), Landsat, one Aug-Sep image per year, 1999-2021.
# Only the summary statistics are published, not the per-year series, so the
# overlap test is against the distribution rather than year by year.
BOUNIF = {
    "period": (1999, 2021),
    "mean_area_km2": 72.0,
    "min_area_km2": 23.0,
    "max_area_km2": 128.0,
    "area_cv": 0.42,
    "area_change_2015_2021": -0.73,
    "volume_range_mm3": (264.0, 2616.0),
}

# Reported storage at specific dates, from Moroccan media citing the ministry.
# Treated as approximate reference points, not ground truth: outlets disagree
# with each other (see docs/literature.md).
REPORTED_STORAGE = [
    {"date": "2025-07-31", "volume_mm3": 105.0, "fill_pct": 4.0, "source": "Le Brief"},
    {"date": "2026-07-24", "volume_mm3": 1094.0, "fill_pct": 41.3, "source": "le360"},
    {"date": "2026-07-31", "volume_mm3": 1089.0, "fill_pct": 41.1, "source": "Le Brief"},
]


def compare_dry_season_to_bounif(monthly: pd.DataFrame) -> dict:
    """Our Aug-Sep areas against Bounif's published range, over the overlap.

    Their window ends in 2021 and ours starts in 2016, so the overlap is
    2016-2021 -- six dry seasons.
    """
    m = monthly.copy()
    m["year"] = m["month"].dt.year
    dry = m[m["month"].dt.month.isin((8, 9))]

    lo, hi = BOUNIF["period"]
    overlap = dry[(dry["year"] >= lo) & (dry["year"] <= hi)]
    ours = overlap.groupby("year")["area_km2"].mean()

    within = ours.between(BOUNIF["min_area_km2"], BOUNIF["max_area_km2"])
    return {
        "check": "dry-season area vs Bounif et al. (2023)",
        "overlap_years": ours.index.tolist(),
        "our_aug_sep_area_km2": {int(k): round(float(v), 1) for k, v in ours.items()},
        "bounif_range_km2": (BOUNIF["min_area_km2"], BOUNIF["max_area_km2"]),
        "n_within_published_range": int(within.sum()),
        "n_years": int(len(ours)),
        "all_within_range": bool(within.all()) if len(ours) else None,
    }


def compare_volume_to_reported(monthly: pd.DataFrame, tolerance: float = 0.35) -> dict:
    """Derived volume against reported storage at specific dates.

    Tolerance is deliberately loose. Bounif's own curve carries RMSE 117.5 Mm3,
    our coefficient ORDER is inferred rather than read, a monthly median is
    compared against a single reported date, and the reported figures disagree
    between outlets. A 35% band tests "same order, right direction", which is
    the most this comparison can honestly support.
    """
    rows = []
    for ref in REPORTED_STORAGE:
        month = pd.Timestamp(ref["date"]).to_period("M").to_timestamp()
        hit = monthly.loc[monthly["month"] == month]
        if hit.empty:
            rows.append({**ref, "our_volume_mm3": None, "status": "no observation"})
            continue
        area = float(hit["area_km2"].iloc[0])
        ours = float(volume.area_to_volume(area, extrapolate=True))
        rel = (ours - ref["volume_mm3"]) / ref["volume_mm3"]
        in_range = BOUNIF["min_area_km2"] <= area <= BOUNIF["max_area_km2"]
        rows.append({
            **ref,
            "our_area_km2": round(area, 1),
            "our_volume_mm3": round(ours, 1),
            "relative_error": round(rel, 3),
            "within_tolerance": bool(abs(rel) <= tolerance),
            "area_within_curve_support": in_range,
        })
    return {
        "check": "derived volume vs reported storage",
        "tolerance": tolerance,
        "comparisons": rows,
    }


def summarise(monthly: pd.DataFrame, scenes: pd.DataFrame, aoi_area_km2: float) -> dict:
    """All validation checks, plus the headline series statistics."""
    from . import checks  # local import keeps the module import-light

    m = monthly.dropna(subset=["area_km2"])
    trough = m.loc[m["area_km2"].idxmin()] if len(m) else None
    peak = m.loc[m["area_km2"].idxmax()] if len(m) else None

    return {
        "series": {
            "months": len(m),
            "covered": f"{m['month'].min():%Y-%m}..{m['month'].max():%Y-%m}" if len(m) else None,
            "scenes_measured": len(scenes),
            "min_area_km2": round(float(m["area_km2"].min()), 1) if len(m) else None,
            "min_area_month": f"{trough['month']:%Y-%m}" if trough is not None else None,
            "max_area_km2": round(float(m["area_km2"].max()), 1) if len(m) else None,
            "max_area_month": f"{peak['month']:%Y-%m}" if peak is not None else None,
        },
        "aoi_mask": {
            "check": "max-extent mask vs published maximum",
            "our_mask_km2": round(aoi_area_km2, 1),
            "published_max_km2": BOUNIF["max_area_km2"],
            "relative_difference": round(
                (aoi_area_km2 - BOUNIF["max_area_km2"]) / BOUNIF["max_area_km2"], 4
            ),
        },
        "bounif": compare_dry_season_to_bounif(monthly),
        "reported_volume": compare_volume_to_reported(monthly),
        "offset_discontinuity": checks.check_offset_discontinuity(
            scenes, "area_combined_km2"
        ),
    }
