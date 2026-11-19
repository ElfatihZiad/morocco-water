"""Flow topology from the Copernicus DEM.

Answers one question that gates the whole cascade budget: which reservoirs
actually drain into Al Massira? A reservoir downstream of it cannot contribute to
its inflow, so assuming the wrong direction would invert the attribution.

The method is D8 flow routing over `cop-dem-glo-90`, delineating Al Massira's
upstream catchment from its dam as a pour point, then testing each other dam for
membership. It carries its own correctness check: the delineated catchment area
must come out near the published ~35,000 km² for Al Massira. If it does not, the
routing is wrong and no membership test from it should be trusted.

90 m rather than 30 m is deliberate: this asks "does this dam drain to that
dam?", not "where exactly is the channel", and 30 m over the whole basin is ~100M
cells for no gain in the answer.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import planetary_computer as pc
import rioxarray  # noqa: F401 - registers the .rio accessor
from odc.stac import load as odc_load
from pyproj import Transformer

# pysheds 0.5 calls np.in1d, which NumPy 2.0 removed. Every call site is the
# identical pattern `np.in1d(fdir.ravel(), dirmap).reshape(fdir.shape)` (verified
# across all 9 occurrences in pysheds/sgrid.py), so the input is already 1-D and
# np.isin is an exact drop-in rather than an approximation. Shimming is preferable
# to pinning NumPy below 2, which the rest of the stack (xarray, odc-stac) needs.
if not hasattr(np, "in1d"):  # pragma: no cover - environment shim
    np.in1d = np.isin  # type: ignore[attr-defined]

from pysheds.grid import Grid  # noqa: E402 - must follow the NumPy 2 shim

from .config import RESERVOIRS, STAC_URL, Reservoir
from .provenance import RunLog
from .sentinel2 import open_catalog

logger = logging.getLogger("moroccowater.topology")

COLLECTION_DEM = "cop-dem-glo-90"

# Generous box around the whole Oum Er-Rbia. A catchment delineation is only
# valid if the box CONTAINS the entire catchment -- otherwise the area comes out
# truncated, which is exactly what the 35,000 km² check would catch.
OER_BBOX = (-8.20, 30.80, -4.50, 33.80)
OER_EPSG = 32629
DEM_RESOLUTION = 90.0

# Al Massira's published catchment area, for validation.
AL_MASSIRA_CATCHMENT_KM2 = 35000.0
CATCHMENT_TOLERANCE = 0.25  # accept +/-25%: basin figures themselves vary


def fetch_dem(
    runlog: RunLog,
    bbox: tuple[float, float, float, float] = OER_BBOX,
    out_path: Path | None = None,
) -> Path:
    """Download and cache the basin DEM as a GeoTIFF on a projected grid.

    Written to disk because pysheds reads rasters rather than xarray objects,
    and a projected grid means cell area is constant, so catchment area is a
    cell count rather than a cosine-weighted integral.
    """
    out_path = out_path or (
        Path(__file__).resolve().parents[2] / "data" / "interim" / "oer_dem_90m.tif"
    )
    if out_path.exists():
        logger.info("reusing cached DEM at %s", out_path)
        return out_path

    items = list(
        open_catalog().search(collections=[COLLECTION_DEM], bbox=list(bbox)).items()
    )
    if not items:
        raise RuntimeError(f"no {COLLECTION_DEM} items for bbox {bbox}")

    ds = odc_load(
        items,
        bands=["data"],
        crs=f"EPSG:{OER_EPSG}",
        resolution=DEM_RESOLUTION,
        bbox=bbox,
        resampling="bilinear",
        chunks={"x": 2048, "y": 2048},
        patch_url=pc.sign,
    )
    dem = ds["data"]
    if "time" in dem.dims:
        dem = dem.max("time")  # tiles, not a time series

    out_path.parent.mkdir(parents=True, exist_ok=True)
    dem.rio.write_nodata(-32768, inplace=True)
    dem.rio.to_raster(out_path, compress="deflate")

    runlog.source(
        collection=COLLECTION_DEM,
        endpoint=STAC_URL,
        bbox=bbox,
        assets=["data"],
        item_ids=[i.id for i in items],
        crs=f"EPSG:{OER_EPSG}",
        resolution=DEM_RESOLUTION,
        note="basin DEM for D8 flow routing",
    )
    logger.info("DEM written to %s (%s)", out_path, dict(dem.sizes))
    return out_path


def condition_and_route(dem_path: Path) -> tuple[Grid, object, object]:
    """Fill pits and depressions, resolve flats, then D8 direction and accumulation."""
    grid = Grid.from_raster(str(dem_path))
    dem = grid.read_raster(str(dem_path))

    logger.info("conditioning DEM %s", dem.shape)
    filled = grid.fill_pits(dem)
    flooded = grid.fill_depressions(filled)
    inflated = grid.resolve_flats(flooded)

    fdir = grid.flowdir(inflated)
    acc = grid.accumulation(fdir)
    logger.info("flow accumulation computed; max = %d cells", int(np.nanmax(acc)))
    return grid, fdir, acc


def _to_grid_crs(lon: float, lat: float) -> tuple[float, float]:
    tx = Transformer.from_crs("EPSG:4326", f"EPSG:{OER_EPSG}", always_xy=True)
    return tx.transform(lon, lat)


def accumulation_at(grid: Grid, acc: np.ndarray, reservoir: Reservoir) -> int | None:
    """Upstream cell count at a reservoir's dam cell, un-snapped.

    Useful on its own: a main-stem dam has an accumulation orders of magnitude
    larger than a headwater tributary dam.
    """
    x, y = _to_grid_crs(*reservoir.dam_lonlat)
    col, row = (~grid.affine) * (x, y)
    row, col = int(row), int(col)
    if not (0 <= row < acc.shape[0] and 0 <= col < acc.shape[1]):
        return None
    return int(acc[row, col])


def snap_to_main_stem(
    grid: Grid, acc: np.ndarray, reservoir: Reservoir, radius_m: float = 5000.0
) -> tuple[float, float, int, float]:
    """Snap a dam coordinate to the highest-accumulation cell within a radius.

    Snapping to "any cell above a threshold" is what produced a 623 km²
    catchment for a basin whose published area is 35,000 km²: a 20,000-cell
    threshold is only ~162 km² of upstream area at 90 m, so the pour point landed
    on a minor side stream. Taking the LOCAL MAXIMUM of accumulation needs no
    threshold to be guessed and lands on the trunk channel by construction.
    """
    x, y = _to_grid_crs(*reservoir.dam_lonlat)
    col, row = (~grid.affine) * (x, y)
    row, col = int(row), int(col)
    rad = int(round(radius_m / DEM_RESOLUTION))

    r0, r1 = max(row - rad, 0), min(row + rad + 1, acc.shape[0])
    c0, c1 = max(col - rad, 0), min(col + rad + 1, acc.shape[1])
    window = np.asarray(acc[r0:r1, c0:c1])
    if window.size == 0:
        raise ValueError(f"{reservoir.slug}: dam falls outside the DEM grid")

    dr, dc = np.unravel_index(int(np.nanargmax(window)), window.shape)
    best_row, best_col = r0 + int(dr), c0 + int(dc)
    bx, by = grid.affine * (best_col + 0.5, best_row + 0.5)
    shift = float(np.hypot(bx - x, by - y))
    return float(bx), float(by), int(window[dr, dc]), shift


def delineate(
    grid: Grid, fdir, acc, reservoir: Reservoir, radius_m: float = 5000.0
) -> dict:
    """Delineate the upstream catchment of a reservoir's dam."""
    acc_arr = np.asarray(acc)
    x_snap, y_snap, acc_cells, shift = snap_to_main_stem(
        grid, acc_arr, reservoir, radius_m=radius_m
    )

    catch = grid.catchment(x=x_snap, y=y_snap, fdir=fdir, xytype="coordinate")
    mask = np.asarray(catch, dtype=bool)
    area_km2 = float(mask.sum()) * (DEM_RESOLUTION**2) / 1e6
    cell_km2 = (DEM_RESOLUTION**2) / 1e6

    return {
        "reservoir": reservoir.slug,
        "dam_lonlat": reservoir.dam_lonlat,
        "snap_shift_m": round(shift, 1),
        "snapped_accumulation_cells": acc_cells,
        # These two should agree closely; a mismatch means the catchment mask and
        # the accumulation grid disagree, which would indicate a routing problem.
        "snapped_accumulation_km2": round(acc_cells * cell_km2, 1),
        "catchment_area_km2": round(area_km2, 1),
        "mask": mask,
        "pour_point": (float(x_snap), float(y_snap)),
    }


def membership(grid: Grid, catchment_mask: np.ndarray, reservoir: Reservoir) -> dict:
    """Is this reservoir's dam inside the given catchment?"""
    x, y = _to_grid_crs(*reservoir.dam_lonlat)
    col, row = (~grid.affine) * (x, y)
    row, col = int(row), int(col)
    inside_grid = 0 <= row < catchment_mask.shape[0] and 0 <= col < catchment_mask.shape[1]
    return {
        "reservoir": reservoir.slug,
        "name": reservoir.name,
        "row_col": (row, col),
        "within_grid": inside_grid,
        "in_catchment": bool(catchment_mask[row, col]) if inside_grid else None,
    }


def resolve(runlog: RunLog, target_slug: str = "al_massira") -> dict:
    """Full topology resolution, with the validation check applied first."""
    dem_path = fetch_dem(runlog)
    grid, fdir, acc = condition_and_route(dem_path)

    target = RESERVOIRS[target_slug]
    main = delineate(grid, fdir, acc, target)
    area = main["catchment_area_km2"]

    expected = AL_MASSIRA_CATCHMENT_KM2
    rel = (area - expected) / expected
    validated = abs(rel) <= CATCHMENT_TOLERANCE
    logger.info(
        "%s catchment: %.0f km² vs published %.0f km² (%+.1f%%) -> %s",
        target.name, area, expected, rel * 100,
        "VALIDATED" if validated else "FAILED VALIDATION",
    )

    result = {
        "target": target_slug,
        "catchment_area_km2": area,
        "published_catchment_km2": expected,
        "relative_difference": round(rel, 3),
        "routing_validated": validated,
        "snap_shift_m": main["snap_shift_m"],
        "dem": {"collection": COLLECTION_DEM, "resolution_m": DEM_RESOLUTION,
                "bbox": OER_BBOX, "epsg": OER_EPSG},
        "members": [],
    }
    acc_arr = np.asarray(acc)
    result["snapped_accumulation_km2"] = main["snapped_accumulation_km2"]
    for slug, r in RESERVOIRS.items():
        if slug == target_slug:
            continue
        m = membership(grid, main["mask"], r)
        m["dam_accumulation_cells"] = accumulation_at(grid, acc_arr, r)
        result["members"].append(m)

    runlog.event("topology_resolved", **{k: v for k, v in result.items() if k != "members"})
    for m in result["members"]:
        runlog.event("topology_member", **m)
    if not validated:
        runlog.assume(
            f"Flow routing did NOT validate: {target.name}'s delineated catchment "
            f"is {area:.0f} km² against a published {expected:.0f} km². "
            "Membership results from this run must not be trusted."
        )
    return result
