"""Topology helpers, on a synthetic grid.

The expensive part (DEM conditioning and D8 routing) is validated at runtime by
comparing the delineated catchment against Al Massira's published ~35,000 km2.
What is tested here is the coordinate and indexing logic around it, which is
where an off-by-one or a lat/lon swap would quietly produce a confident wrong
answer.
"""

from __future__ import annotations

import numpy as np
from affine import Affine

from moroccowater import topology
from moroccowater.config import AL_MASSIRA, BIN_EL_OUIDANE


class FakeGrid:
    """Only `.affine` is used by membership()."""

    def __init__(self, affine: Affine):
        self.affine = affine


def test_numpy2_shim_is_in_place_and_equivalent():
    """pysheds calls np.in1d on already-flattened arrays, so np.isin is exact."""
    assert hasattr(np, "in1d")
    fdir = np.array([[1, 2], [64, 99]])
    dirmap = (64, 128, 1, 2, 4, 8, 16, 32)
    shimmed = ~np.in1d(fdir.ravel(), dirmap).reshape(fdir.shape)
    expected = ~np.isin(fdir.ravel(), dirmap).reshape(fdir.shape)
    assert np.array_equal(shimmed, expected)
    assert shimmed.tolist() == [[False, False], [False, True]]  # 99 is invalid


def test_to_grid_crs_puts_al_massira_in_utm29n_range():
    x, y = topology._to_grid_crs(*AL_MASSIRA.dam_lonlat)
    # UTM easting is 500 km at the zone's central meridian (-9 for zone 29).
    # Al Massira sits east of it, so easting must exceed 500000.
    assert 500_000 < x < 800_000, x
    # Northing for ~32.5 deg N is roughly 3.6 million metres.
    assert 3_500_000 < y < 3_700_000, y


def test_to_grid_crs_is_not_lat_lon_swapped():
    """always_xy=True means (lon, lat) in, (easting, northing) out. A swap here
    would move the reservoir thousands of km and still return plausible floats."""
    x_am, y_am = topology._to_grid_crs(*AL_MASSIRA.dam_lonlat)
    x_bo, y_bo = topology._to_grid_crs(*BIN_EL_OUIDANE.dam_lonlat)
    # Bin el Ouidane is EAST of and SOUTH of Al Massira.
    assert BIN_EL_OUIDANE.dam_lonlat[0] > AL_MASSIRA.dam_lonlat[0]
    assert BIN_EL_OUIDANE.dam_lonlat[1] < AL_MASSIRA.dam_lonlat[1]
    assert x_bo > x_am, "easting must increase with longitude"
    assert y_bo < y_am, "northing must decrease with latitude"


def _grid_around(lon: float, lat: float, size: int = 11, res: float = 90.0):
    """A small projected grid centred on a lon/lat, with its affine."""
    cx, cy = topology._to_grid_crs(lon, lat)
    half = size // 2
    # Affine maps (col, row) -> (x, y); north-up, so the y step is negative.
    affine = Affine(res, 0, cx - half * res, 0, -res, cy + half * res)
    return FakeGrid(affine), (half, half)


def test_membership_true_when_the_dam_cell_is_in_the_catchment():
    grid, (r, c) = _grid_around(*AL_MASSIRA.dam_lonlat)
    mask = np.zeros((11, 11), dtype=bool)
    mask[r, c] = True
    out = topology.membership(grid, mask, AL_MASSIRA)
    assert out["row_col"] == (r, c)
    assert out["within_grid"] is True
    assert out["in_catchment"] is True


def test_membership_false_when_the_dam_cell_is_outside():
    grid, _ = _grid_around(*AL_MASSIRA.dam_lonlat)
    out = topology.membership(grid, np.zeros((11, 11), dtype=bool), AL_MASSIRA)
    assert out["in_catchment"] is False


def test_membership_reports_none_rather_than_guessing_off_grid():
    """A reservoir outside the DEM box must come back as unknown, not False --
    'not in the catchment' and 'not in the data' are different claims."""
    grid, _ = _grid_around(*AL_MASSIRA.dam_lonlat, size=3)
    out = topology.membership(grid, np.zeros((3, 3), dtype=bool), BIN_EL_OUIDANE)
    assert out["within_grid"] is False
    assert out["in_catchment"] is None


def test_validation_tolerance_brackets_the_published_catchment():
    lo = topology.AL_MASSIRA_CATCHMENT_KM2 * (1 - topology.CATCHMENT_TOLERANCE)
    hi = topology.AL_MASSIRA_CATCHMENT_KM2 * (1 + topology.CATCHMENT_TOLERANCE)
    assert lo < 30_000 < hi      # a plausible delineation passes
    assert not (lo < 5_000 < hi)  # an unsnapped pour point fails
    assert not (lo < 90_000 < hi)  # leaking into a neighbouring basin fails
