"""Reservoir analysis mask, derived from JRC Global Surface Water.

Using JRC GSW's maximum-extent layer rather than a hand-drawn polygon makes the
reservoir boundary published, citable and reproducible, and its area gives a
defensible ceiling for the sanity checks. See docs/mvp-plan.md.
"""

from __future__ import annotations

import logging

import numpy as np
import planetary_computer as pc
import xarray as xr
from odc.stac import load as odc_load
from pyproj import Transformer
from scipy import ndimage

from .config import COLLECTION_GSW, STAC_URL, Reservoir
from .provenance import RunLog
from .sentinel2 import open_catalog

logger = logging.getLogger("moroccowater.aoi")


def max_extent_mask(
    reservoir: Reservoir, runlog: RunLog, occurrence_min: float = 5.0
) -> xr.DataArray:
    """Maximum observed water extent over the reservoir, as a boolean mask.

    JRC GSW `occurrence` is the percentage of valid observations in which a pixel
    was water, 1984-2021. A low threshold (default 5%) is deliberate: we want the
    *envelope* the reservoir has ever filled, so the mask does not clip the high-
    water shoreline. Raising it would shrink the mask toward permanent water and
    bias every area measurement low.
    """
    cat = open_catalog()
    items = list(cat.search(collections=[COLLECTION_GSW], bbox=list(reservoir.bbox)).items())
    if not items:
        raise RuntimeError(f"no {COLLECTION_GSW} items for bbox {reservoir.bbox}")

    ds = odc_load(
        items,
        bands=["occurrence"],
        crs=f"EPSG:{reservoir.epsg}",
        resolution=reservoir.resolution,
        bbox=reservoir.bbox,
        resampling="nearest",
        chunks={"x": 2048, "y": 2048},
        patch_url=pc.sign,
    )
    occ = ds["occurrence"]
    if "time" in occ.dims:
        occ = occ.max("time")

    # GSW uses 255 for nodata; treat it as not-water rather than as 255%.
    occ = occ.where(occ != 255)
    mask = (occ >= occurrence_min).fillna(False).rename("aoi")
    mask = isolate_reservoir(mask, reservoir, runlog)

    runlog.source(
        collection=COLLECTION_GSW,
        endpoint=STAC_URL,
        bbox=reservoir.bbox,
        assets=["occurrence"],
        item_ids=[i.id for i in items],
        crs=f"EPSG:{reservoir.epsg}",
        resolution=reservoir.resolution,
        note=f"max-extent mask at occurrence >= {occurrence_min}%",
    )
    runlog.assume(
        f"The analysis mask is JRC GSW occurrence >= {occurrence_min}% (1984-2021). "
        "Pixels the reservoir flooded only after 2021 are outside it."
    )
    return mask


def isolate_reservoir(
    mask: xr.DataArray, reservoir: Reservoir, runlog: RunLog
) -> xr.DataArray:
    """Keep only the connected water body containing the dam.

    JRC GSW flags every surface water pixel in the box -- the Oum Er-Rbia
    upstream and downstream of the dam, irrigation canals, farm ponds. Counting
    those as reservoir would inflate every area measurement and, because canals
    and ponds respond to rainfall on a different timescale than storage, would
    smear the signal we are trying to measure. Selecting the component that
    contains the dam is more defensible than taking the largest, since it is
    anchored to a known coordinate rather than to whatever happens to be biggest.
    """
    labels, n = ndimage.label(mask.values)
    if n == 0:
        raise ValueError("no water pixels in the GSW mask")

    lon, lat = reservoir.dam_lonlat
    tx = Transformer.from_crs("EPSG:4326", f"EPSG:{reservoir.epsg}", always_xy=True)
    dam_x, dam_y = tx.transform(lon, lat)
    col = int(np.abs(mask.x.values - dam_x).argmin())
    row = int(np.abs(mask.y.values - dam_y).argmin())

    # The dam wall itself is not water, so search a small neighbourhood for the
    # impounded body rather than requiring a hit on the exact pixel.
    radius = 25  # px @ 20 m = 500 m
    window = labels[
        max(row - radius, 0) : row + radius + 1,
        max(col - radius, 0) : col + radius + 1,
    ]
    candidates = window[window > 0]
    if candidates.size == 0:
        raise ValueError(
            f"no water within {radius} px of the dam at {reservoir.dam_lonlat}; "
            "check dam_lonlat and the GSW occurrence threshold"
        )
    sizes = np.bincount(candidates.ravel())
    chosen = int(sizes.argmax())

    out = xr.zeros_like(mask, dtype=bool)
    out.values = labels == chosen
    runlog.event(
        "reservoir_isolated",
        n_components=int(n),
        chosen_label=chosen,
        kept_px=int(out.sum()),
        dropped_px=int(mask.sum()) - int(out.sum()),
    )
    logger.info(
        "isolated reservoir: kept %d of %d water px across %d components",
        int(out.sum()), int(mask.sum()), n,
    )
    return out.rename("aoi")


def crop_to_extent(mask: xr.DataArray, buffer_px: int = 50) -> xr.DataArray:
    """Crop a boolean mask to its own bounding box, plus a buffer.

    The reservoir config bbox is deliberately generous, which makes it ~5x larger
    than the water body and the scene loads correspondingly wasteful. Cropping to
    the max-extent envelope keeps every pixel we could ever measure and discards
    the rest. The buffer leaves room for water beyond the 1984-2021 GSW envelope
    -- without it, a post-2021 high-water year would be silently clipped.
    """
    ys, xs = np.nonzero(mask.values)
    if ys.size == 0:
        raise ValueError("mask is empty; nothing to crop to")
    y0 = max(int(ys.min()) - buffer_px, 0)
    y1 = min(int(ys.max()) + buffer_px + 1, mask.sizes["y"])
    x0 = max(int(xs.min()) - buffer_px, 0)
    x1 = min(int(xs.max()) + buffer_px + 1, mask.sizes["x"])
    out = mask.isel(y=slice(y0, y1), x=slice(x0, x1))
    logger.info(
        "cropped AOI from %sx%s to %sx%s px",
        mask.sizes["y"], mask.sizes["x"], out.sizes["y"], out.sizes["x"],
    )
    return out


def mask_area_km2(mask: xr.DataArray, resolution: float) -> float:
    """Area of a boolean mask, in km²."""
    return float(mask.sum()) * (resolution**2) / 1e6
