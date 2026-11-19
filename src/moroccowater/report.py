"""Turn the pipeline outputs into a validation report and a figure.

Run after the pipeline:
    uv run python -m moroccowater.report --reservoir al_massira
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")  # headless: this writes files, it never opens a window
import matplotlib.pyplot as plt  # noqa: E402

from . import validate  # noqa: E402
from .chirps import basin_precipitation  # noqa: E402
from .config import RESERVOIRS, Reservoir  # noqa: E402
from .provenance import RunLog  # noqa: E402

logger = logging.getLogger("moroccowater.report")

DATA = Path(__file__).resolve().parents[2] / "data"
BASELINE_BOUNDARY = pd.Timestamp("2022-01-25")


def load_outputs(reservoir: Reservoir, outdir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    scenes = pd.read_parquet(outdir / f"{reservoir.slug}_scene_area.parquet")
    monthly = pd.read_parquet(outdir / f"{reservoir.slug}_monthly_area.parquet")
    monthly["month"] = pd.to_datetime(monthly["month"])
    scenes["time"] = pd.to_datetime(scenes["time"])
    return scenes, monthly


def figure(
    reservoir: Reservoir,
    monthly: pd.DataFrame,
    precip: pd.DataFrame | None,
    path: Path,
) -> Path:
    """Area over rainfall, with the published reference values marked."""
    fig, (ax, ax2) = plt.subplots(
        2, 1, figsize=(12, 7), sharex=True, height_ratios=[2, 1],
        gridspec_kw={"hspace": 0.08},
    )

    m = monthly.sort_values("month")
    ax.plot(m["month"], m["area_km2"], lw=1.4, color="#1f6f8b", zorder=3,
            label="Sentinel-2 monthly median")
    ax.fill_between(m["month"], m["area_min_km2"], m["area_max_km2"],
                    alpha=0.20, color="#1f6f8b", lw=0, zorder=2,
                    label="within-month scene range")

    # Published reference values from Bounif et al. (2023), 1999-2021 Landsat.
    for value, label, style in (
        (validate.BOUNIF["max_area_km2"], "published max (128)", "--"),
        (validate.BOUNIF["mean_area_km2"], "published mean (72)", ":"),
        (validate.BOUNIF["min_area_km2"], "published min (23)", "--"),
    ):
        ax.axhline(value, color="#b4654a", ls=style, lw=1.0, zorder=1)
        ax.annotate(label, (m["month"].min(), value), fontsize=8, va="bottom",
                    color="#b4654a")

    # The processing-baseline boundary: if the offset correction had failed, a
    # step would appear exactly here.
    for a in (ax, ax2):
        a.axvline(BASELINE_BOUNDARY, color="#555", lw=1.0, ls="-.", alpha=0.7)
    ax.annotate("S2 baseline 04.00\n(offset applied)", (BASELINE_BOUNDARY, ax.get_ylim()[1]),
                fontsize=8, ha="left", va="top", color="#555")

    ax.set_ylabel("water-surface area (km²)")
    ax.set_title(
        f"{reservoir.name} reservoir — Sentinel-2 surface area vs catchment rainfall\n"
        f"{reservoir.resolution:.0f} m grid, combined-index water rule (Bounif et al. 2023)",
        fontsize=11, loc="left",
    )
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(alpha=0.25)

    if precip is not None and len(precip):
        p = precip.sort_values("month")
        ax2.bar(p["month"], p["precip_mm"], width=24, color="#4a7fb4", alpha=0.85)
        ax2.set_ylabel("catchment rainfall\n(mm/month, CHIRPS v3)")
    else:
        ax2.text(0.5, 0.5, "rainfall unavailable", ha="center", transform=ax2.transAxes)
    ax2.set_xlabel("")
    ax2.grid(alpha=0.25)

    # Observation count is part of the result, not decoration: a month resting
    # on one scene is not the same claim as one resting on six.
    ax3 = ax2.twinx()
    ax3.step(m["month"], m["n_scenes"], where="mid", color="#999", lw=0.8)
    ax3.set_ylabel("scenes/month", color="#999", fontsize=8)
    ax3.tick_params(axis="y", labelcolor="#999", labelsize=8)

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("figure written to %s", path)
    return path


def run(reservoir: Reservoir, outdir: Path, with_rainfall: bool = True) -> dict:
    scenes, monthly = load_outputs(reservoir, outdir)

    prov = json.loads((outdir / f"{reservoir.slug}_provenance.json").read_text())
    aoi_km2 = next(
        (e["area_km2"] for e in prov["events"] if e["kind"] == "aoi"), float("nan")
    )

    precip = None
    if with_rainfall:
        try:
            precip = basin_precipitation(
                reservoir,
                f"{monthly['month'].min():%Y-%m-01}",
                f"{monthly['month'].max():%Y-%m-28}",
                RunLog(f"{reservoir.slug}_report_rainfall"),
                cache_path=DATA / "interim" / f"chirps_{reservoir.slug}.parquet",
            )
        except Exception as exc:  # noqa: BLE001 - rainfall is optional here
            logger.warning("rainfall unavailable: %s", str(exc)[:200])

    report = validate.summarise(monthly, scenes, aoi_area_km2=aoi_km2)
    if precip is not None:
        from .analysis import join_monthly, lagged_correlations

        joined = join_monthly(monthly, precip)
        try:
            lags = lagged_correlations(joined)
            report["rainfall_lag"] = {
                "best": lags.head(5).to_dict("records"),
                "note": "pearson_r on rolling rainfall sums, ranked by |r|",
            }
        except ValueError as exc:
            report["rainfall_lag"] = {"error": str(exc)}

    fig_path = figure(reservoir, monthly, precip, outdir / f"{reservoir.slug}_area.png")
    report["figure"] = str(fig_path)

    out = outdir / f"{reservoir.slug}_validation.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    logger.info("validation written to %s", out)
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reservoir", default="al_massira", choices=sorted(RESERVOIRS))
    p.add_argument("--outdir", type=Path, default=DATA / "processed")
    p.add_argument("--no-rainfall", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    print(json.dumps(run(RESERVOIRS[a.reservoir], a.outdir,
                         with_rainfall=not a.no_rainfall), indent=2, default=str))


if __name__ == "__main__":
    main()
