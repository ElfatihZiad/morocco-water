"""Spectral indices.

All of these assume reflectance floats with NaN for nodata -- never raw integer
DNs. See sentinel2.to_reflectance.
"""

from __future__ import annotations

import xarray as xr


def _nd(a: xr.DataArray, b: xr.DataArray) -> xr.DataArray:
    """Normalised difference, guarding the zero-denominator case."""
    denom = a + b
    return (a - b) / denom.where(denom != 0)


def ndwi(green: xr.DataArray, nir: xr.DataArray) -> xr.DataArray:
    """McFeeters (1996). Green/NIR."""
    return _nd(green, nir).rename("ndwi")


def mndwi(green: xr.DataArray, swir1: xr.DataArray) -> xr.DataArray:
    """Xu (2006). Green/SWIR1 -- better at suppressing built-up land than NDWI."""
    return _nd(green, swir1).rename("mndwi")


def ndvi(nir: xr.DataArray, red: xr.DataArray) -> xr.DataArray:
    """Rouse et al. (1973)."""
    return _nd(nir, red).rename("ndvi")


def awei_sh(
    blue: xr.DataArray,
    green: xr.DataArray,
    nir: xr.DataArray,
    swir1: xr.DataArray,
    swir2: xr.DataArray,
) -> xr.DataArray:
    """Feyisa et al. (2014), shadow-suppressing variant.

    This is the form Bounif et al. (2023) used on Al Massira, which is why we
    use it rather than the more common AWEI_nsh -- reproducing their method is
    the point.
    """
    return (blue + 2.5 * green - 1.5 * (nir + swir1) - 0.25 * swir2).rename("awei_sh")
