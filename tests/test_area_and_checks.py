"""Area measurement, sanity checks and the volume curve, on synthetic data."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from moroccowater import checks, volume, water
from moroccowater.aoi import mask_area_km2
from moroccowater.config import AL_MASSIRA


def _grid(n_time: int, size: int = 10) -> dict:
    coords = {"time": pd.date_range("2023-01-01", periods=n_time, freq="10D"),
              "y": np.arange(size), "x": np.arange(size)}
    return coords


def test_mask_area_km2_scales_with_resolution():
    mask = xr.DataArray(np.ones((10, 10), dtype=bool), dims=("y", "x"))
    assert mask_area_km2(mask, 20.0) == pytest.approx(100 * 400 / 1e6)
    assert mask_area_km2(mask, 10.0) == pytest.approx(100 * 100 / 1e6)


def test_scene_table_counts_only_water_inside_aoi_and_valid():
    coords = _grid(1)
    size = 10
    # AOI is the left half; water covers the left 7 columns; the top 2 rows are cloudy.
    aoi = xr.DataArray(
        np.array([[c < 5 for c in range(size)] for _ in range(size)]),
        dims=("y", "x"), coords={"y": coords["y"], "x": coords["x"]},
    )
    wet = xr.DataArray(
        np.array([[[c < 7 for c in range(size)] for _ in range(size)]]),
        dims=("time", "y", "x"), coords=coords,
    )
    valid = xr.DataArray(
        np.array([[[r >= 2 for _ in range(size)] for r in range(size)]]),
        dims=("time", "y", "x"), coords=coords,
    )
    df = water.scene_table({"t": wet}, valid, aoi, resolution=20.0)
    # 8 valid rows x 5 AOI columns all wet = 40 pixels
    assert df.loc[0, "area_t_km2"] == pytest.approx(40 * 400 / 1e6)
    assert df.loc[0, "valid_frac"] == pytest.approx(0.8)
    # Upper bound adds the 10 unobserved AOI pixels.
    assert df.loc[0, "area_t_upper_km2"] == pytest.approx(50 * 400 / 1e6)


def test_scene_table_rejects_empty_aoi():
    coords = _grid(1)
    z = xr.DataArray(np.zeros((1, 10, 10), dtype=bool), dims=("time", "y", "x"),
                     coords=coords)
    aoi = xr.DataArray(np.zeros((10, 10), dtype=bool), dims=("y", "x"),
                       coords={"y": coords["y"], "x": coords["x"]})
    with pytest.raises(ValueError, match="empty AOI"):
        water.scene_table({"t": z}, z, aoi, resolution=20.0)


def test_combined_rule_is_stricter_than_ndwi_alone():
    """A vegetated pixel with positive NDWI is water by NDWI, not by the
    combined rule -- which is the whole reason Bounif et al. used four indices."""
    coords = _grid(1)

    def da(v):
        return xr.DataArray(np.full((1, 1, 1), v, dtype="float32"),
                            dims=("time", "y", "x"),
                            coords={"time": coords["time"][:1], "y": [0], "x": [0]})

    idx = xr.Dataset({"ndwi": da(0.1), "mndwi": da(0.1),
                      "ndvi": da(0.4), "awei_sh": da(0.1)})
    assert bool(water.water_mask_ndwi(idx).values[0, 0, 0]) is True
    assert bool(water.water_mask_combined(idx).values[0, 0, 0]) is False


def test_area_ceiling_check_rejects_impossible_area():
    df = pd.DataFrame({"area_combined_km2": [50.0, 200.0]})
    with pytest.raises(checks.SanityError, match="ceiling"):
        checks.check_area_bounds(df, AL_MASSIRA, "area_combined_km2")


def test_area_check_rejects_negative_area():
    df = pd.DataFrame({"area_combined_km2": [-1.0]})
    with pytest.raises(checks.SanityError, match="negative"):
        checks.check_area_bounds(df, AL_MASSIRA, "area_combined_km2")


def test_area_check_accepts_published_range():
    df = pd.DataFrame({"area_combined_km2": [23.0, 72.0, 128.0]})
    checks.check_area_bounds(df, AL_MASSIRA, "area_combined_km2")


def test_index_range_check_catches_out_of_bounds():
    bad = xr.Dataset({"ndwi": xr.DataArray([1.5]), "mndwi": xr.DataArray([0.0]),
                      "ndvi": xr.DataArray([0.0])})
    with pytest.raises(checks.SanityError, match=r"ndwi outside"):
        checks.check_index_range(bad)


def test_reflectance_range_check_catches_unapplied_offset():
    """An un-offset post-2022 scene reads ~0.1 too high; a double-applied one
    goes far negative. Both must trip the range check."""
    ds = xr.Dataset({
        "B03": xr.DataArray(np.full((1, 2, 2), -0.5, dtype="float32"),
                            dims=("time", "y", "x")),
    })
    with pytest.raises(checks.SanityError, match="outside"):
        checks.check_reflectance_range(ds, ["B03"])


def test_monthly_leaves_gaps_as_gaps():
    df = pd.DataFrame({
        "time": pd.to_datetime(["2023-01-05", "2023-01-20", "2023-04-10"]),
        "area_a_km2": [50.0, 54.0, 30.0],
        "valid_frac": [1.0, 1.0, 1.0],
    })
    mon = water.monthly(df, "area_a_km2", min_valid_frac=0.8)
    assert list(mon["month"].dt.strftime("%Y-%m")) == ["2023-01", "2023-04"]
    assert mon.loc[0, "n_scenes"] == 2
    assert mon.loc[0, "area_km2"] == pytest.approx(52.0)  # median of the month


def test_monthly_drops_cloudy_scenes():
    df = pd.DataFrame({
        "time": pd.to_datetime(["2023-01-05", "2023-01-20"]),
        "area_a_km2": [50.0, 5.0],
        "valid_frac": [1.0, 0.3],  # second scene mostly cloud
    })
    mon = water.monthly(df, "area_a_km2", min_valid_frac=0.8)
    assert mon.loc[0, "n_scenes"] == 1
    assert mon.loc[0, "area_km2"] == pytest.approx(50.0)


def test_coverage_check_rejects_zero_scene_month():
    with pytest.raises(checks.SanityError):
        checks.check_monthly_coverage(pd.DataFrame({"n_scenes": [0]}))


def test_jump_flag_ignores_gaps_but_flags_real_jumps():
    mon = pd.DataFrame({
        "month": pd.to_datetime(["2023-01-01", "2023-02-01", "2023-06-01"]),
        "area_km2": [50.0, 90.0, 20.0],
    })
    out = checks.flag_area_jumps(mon, limit=0.30)
    assert bool(out.loc[1, "suspicious_jump"]) is True   # consecutive, +80%
    assert bool(out.loc[2, "suspicious_jump"]) is False  # 4-month gap, not a jump


def test_volume_curve_reproduces_published_range():
    """The inferred coefficient order must land on Bounif's reported volumes at
    their reported area extremes -- this is the check that justified the
    inference in volume.py."""
    lo_a, hi_a = volume.BOUNIF_AREA_RANGE_KM2
    lo_v, hi_v = volume.BOUNIF_VOLUME_RANGE_MM3
    assert volume.area_to_volume(hi_a) == pytest.approx(hi_v, rel=0.05)
    # The low end is weaker: a quadratic through a reservoir's dead storage is
    # poorly constrained, so only order-of-magnitude agreement is asserted.
    assert 0.5 * lo_v < volume.area_to_volume(lo_a) < 1.5 * lo_v


def test_volume_is_nan_outside_the_validated_range():
    assert np.isnan(volume.area_to_volume(5.0))     # below Bounif's 23 km² floor
    assert np.isnan(volume.area_to_volume(200.0))
    assert not np.isnan(volume.area_to_volume(5.0, extrapolate=True))


def test_volume_is_monotonic_and_nonnegative():
    a = np.linspace(23, 128, 50)
    v = volume.area_to_volume(a)
    assert np.all(np.diff(v) > 0)
    assert np.all(v >= 0)


def test_volume_describe_flags_unverified_coefficients():
    d = volume.describe()
    assert d["coefficients_verified"] is False
    assert "inferred" in d["caveat"].lower()


def test_reflectance_check_tolerates_a_single_empty_scene():
    """An edge-of-orbit or fully-clouded scene carries no valid pixel over the
    AOI. That is normal and must not abort the batch -- it cost 11% of the
    Al Massira series when it did."""
    good = np.full((1, 2, 2), 0.05, dtype="float32")
    empty = np.full((1, 2, 2), np.nan, dtype="float32")
    ds = xr.Dataset({
        "B03": xr.DataArray(np.concatenate([empty, good]), dims=("time", "y", "x")),
    })
    checks.check_reflectance_range(ds, ["B03"], sample=2)  # must not raise


def test_reflectance_check_still_fails_when_every_scene_is_empty():
    ds = xr.Dataset({
        "B03": xr.DataArray(np.full((2, 2, 2), np.nan, dtype="float32"),
                            dims=("time", "y", "x")),
    })
    with pytest.raises(checks.SanityError, match="every one of"):
        checks.check_reflectance_range(ds, ["B03"], sample=2)


def test_reflectance_check_still_catches_a_bad_offset_past_an_empty_scene():
    """The out-of-range test must survive being preceded by an empty scene."""
    empty = np.full((1, 2, 2), np.nan, dtype="float32")
    bad = np.full((1, 2, 2), -0.5, dtype="float32")
    ds = xr.Dataset({
        "B03": xr.DataArray(np.concatenate([empty, bad]), dims=("time", "y", "x")),
    })
    with pytest.raises(checks.SanityError, match="outside"):
        checks.check_reflectance_range(ds, ["B03"], sample=2)
