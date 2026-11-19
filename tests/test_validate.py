"""Validation logic, on synthetic series.

These assert the comparison machinery is right, so that when it runs against
real data a pass or fail means what it says.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from moroccowater import validate


def _monthly(pairs: list[tuple[str, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {"month": pd.to_datetime([p[0] for p in pairs]),
         "area_km2": [p[1] for p in pairs],
         "n_scenes": [2] * len(pairs)}
    )


def test_bounif_comparison_uses_only_aug_sep_and_the_overlap_window():
    m = _monthly([
        ("2016-08-01", 80.0), ("2016-09-01", 78.0),
        ("2016-03-01", 5.0),    # wrong season: must be ignored
        ("2019-08-01", 60.0),
        ("2024-08-01", 1.0),    # outside Bounif's 1999-2021 window: ignored
    ])
    out = validate.compare_dry_season_to_bounif(m)
    assert out["overlap_years"] == [2016, 2019]
    assert out["our_aug_sep_area_km2"] == {2016: 79.0, 2019: 60.0}  # mean of Aug+Sep
    assert out["all_within_range"] is True


def test_bounif_comparison_flags_values_outside_the_published_range():
    m = _monthly([("2017-08-01", 5.0), ("2018-08-01", 80.0)])
    out = validate.compare_dry_season_to_bounif(m)
    assert out["n_within_published_range"] == 1
    assert out["n_years"] == 2
    assert out["all_within_range"] is False


def test_bounif_comparison_handles_no_overlap():
    out = validate.compare_dry_season_to_bounif(_monthly([("2024-08-01", 50.0)]))
    assert out["overlap_years"] == []
    assert out["all_within_range"] is None


def test_volume_comparison_reports_missing_months_rather_than_guessing():
    out = validate.compare_volume_to_reported(_monthly([("2020-01-01", 50.0)]))
    assert all(c["status"] == "no observation" for c in out["comparisons"])


def test_volume_comparison_matches_a_consistent_area():
    """Feed the area that the published curve maps onto the reported volume, and
    the check must pass; feed a wildly different one and it must fail."""
    target = 1094.0
    # Solve 0.1205 a^2 + 5.4883 a + 0.0227 = target for a > 0.
    c2, c1, c0 = validate.volume.BOUNIF_COEFFS
    a = (-c1 + np.sqrt(c1**2 - 4 * c2 * (c0 - target))) / (2 * c2)

    good = validate.compare_volume_to_reported(_monthly([("2026-07-01", float(a))]))
    row = next(c for c in good["comparisons"] if c["date"] == "2026-07-24")
    assert row["within_tolerance"] is True
    assert row["relative_error"] == pytest.approx(0.0, abs=1e-3)

    bad = validate.compare_volume_to_reported(_monthly([("2026-07-01", 20.0)]))
    row = next(c for c in bad["comparisons"] if c["date"] == "2026-07-24")
    assert row["within_tolerance"] is False


def test_volume_comparison_marks_areas_outside_the_curve_support():
    """The 2022-24 minimum went below Bounif's 23 km2 floor, where a quadratic
    fit is least trustworthy -- the output must say so rather than hide it."""
    out = validate.compare_volume_to_reported(_monthly([("2025-07-01", 10.0)]))
    row = next(c for c in out["comparisons"] if c["date"] == "2025-07-31")
    assert row["area_within_curve_support"] is False
    assert row["our_volume_mm3"] is not None  # extrapolated, but flagged


def test_summarise_reports_extremes_and_mask_agreement():
    m = _monthly([("2019-08-01", 60.0), ("2023-09-01", 8.0), ("2026-06-01", 95.0)])
    scenes = pd.DataFrame({
        "time": pd.to_datetime(["2019-08-05", "2023-09-05", "2026-06-05"]),
        "area_combined_km2": [60.0, 8.0, 95.0],
    })
    out = validate.summarise(m, scenes, aoi_area_km2=128.1)

    assert out["series"]["min_area_km2"] == 8.0
    assert out["series"]["min_area_month"] == "2023-09"
    assert out["series"]["max_area_month"] == "2026-06"
    # 128.1 vs a published 128.0 is agreement to well under a percent.
    assert abs(out["aoi_mask"]["relative_difference"]) < 0.01


def test_summarise_survives_an_all_nan_series():
    m = pd.DataFrame({"month": pd.to_datetime(["2020-01-01"]),
                      "area_km2": [np.nan], "n_scenes": [1]})
    scenes = pd.DataFrame({"time": pd.to_datetime(["2020-01-05"]),
                           "area_combined_km2": [np.nan]})
    out = validate.summarise(m, scenes, aoi_area_km2=128.1)
    assert out["series"]["months"] == 0
    assert out["series"]["min_area_km2"] is None
