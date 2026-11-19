"""Relating storage to rainfall.

The comparison has to be made at lag. Bounif et al. report 71% of Al Massira's
annual inflow arriving February-June with a May peak, so a contemporaneous
correlation between monthly rainfall and monthly storage measures almost nothing.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger("moroccowater.analysis")


def join_monthly(area: pd.DataFrame, precip: pd.DataFrame) -> pd.DataFrame:
    """Left-join rainfall onto the monthly area series, keeping area's gaps."""
    return area.merge(precip, on="month", how="left")


def lagged_correlations(
    df: pd.DataFrame,
    target: str = "area_km2",
    driver: str = "precip_mm",
    max_lag: int = 12,
    min_overlap: int = 24,
) -> pd.DataFrame:
    """Correlate `target` against `driver` shifted back 0..max_lag months.

    Reindexes onto a complete monthly axis first so a `shift(k)` really means k
    months rather than k observations -- with gaps in the series those are not
    the same thing, and conflating them is a quiet way to get a wrong lag.

    Also correlates against rolling rainfall sums, since a reservoir integrates
    runoff over a wet season rather than responding to one month.
    """
    if df.empty:
        raise ValueError("empty frame")
    full = pd.DataFrame(
        {"month": pd.date_range(df["month"].min(), df["month"].max(), freq="MS")}
    ).merge(df, on="month", how="left")

    rows = []
    for lag in range(max_lag + 1):
        for window in (1, 3, 6):
            d = full[driver].rolling(window, min_periods=window).sum().shift(lag)
            pair = pd.concat([full[target], d], axis=1).dropna()
            if len(pair) < min_overlap:
                continue
            rows.append(
                {
                    "lag_months": lag,
                    "accum_window_months": window,
                    "n": len(pair),
                    "pearson_r": float(pair.iloc[:, 0].corr(pair.iloc[:, 1])),
                    "spearman_r": float(
                        pair.iloc[:, 0].corr(pair.iloc[:, 1], method="spearman")
                    ),
                }
            )
    if not rows:
        raise ValueError(f"no lag had >= {min_overlap} overlapping months")
    out = pd.DataFrame(rows)
    return out.sort_values("pearson_r", key=np.abs, ascending=False).reset_index(drop=True)


def recovery_fractions(
    df: pd.DataFrame,
    column: str,
    baseline: tuple[str, str],
    trough: tuple[str, str],
    recovery: tuple[str, str],
) -> dict:
    """How much of a drawdown was recovered, as a fraction of the baseline.

    This is the arithmetic behind the recovery-asymmetry question in
    docs/novelty.md: run it on reservoir area, then on groundwater and NDVI, and
    compare the fractions. Divergence between compartments is the finding.
    """
    def window_median(lo: str, hi: str) -> float:
        m = df.loc[df["month"].between(pd.Timestamp(lo), pd.Timestamp(hi)), column]
        return float(m.median()) if len(m) else float("nan")

    b, t, r = (window_median(*w) for w in (baseline, trough, recovery))
    drawdown = b - t
    return {
        "column": column,
        "baseline_median": b,
        "trough_median": t,
        "recovery_median": r,
        "drawdown": drawdown,
        "recovered_fraction": (r - t) / drawdown if drawdown else float("nan"),
        "remaining_deficit_fraction": (b - r) / b if b else float("nan"),
    }
