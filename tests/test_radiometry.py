"""The offset and float-casting rules are the project's main correctness risk,
so they are tested on synthetic arrays rather than on the network."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from moroccowater.indices import mndwi, ndwi
from moroccowater.provenance import RunLog
from moroccowater.sentinel2 import to_reflectance


def _ds(dn_by_time: dict[str, dict[str, int]]) -> xr.Dataset:
    """Tiny 1x1-pixel dataset of raw uint16 DNs per solar day."""
    times = pd.to_datetime(list(dn_by_time))
    bands = ("B02", "B03", "B04", "B08", "B11", "B12")
    data = {
        b: (("time", "y", "x"),
            np.array([[[dn_by_time[str(t.date())][b]]] for t in times], dtype="uint16"))
        for b in bands
    }
    data["SCL"] = (("time", "y", "x"),
                   np.full((len(times), 1, 1), 6, dtype="uint8"))
    return xr.Dataset(data, coords={"time": times, "y": [0], "x": [0]})


def _offsets(days: list[str], offset: float) -> pd.DataFrame:
    return pd.DataFrame({
        "solar_day": pd.to_datetime(days),
        "scale": 10000.0,
        "offset": offset,
        "how": "raster:bands",
        "baseline": "04.00",
        "item_id": ["x"] * len(days),
    })


def test_integer_underflow_would_corrupt_ndwi_without_float_cast():
    """green - nir on uint16 wraps instead of going negative.

    This is the failure CLAUDE.md's float rule exists to prevent; the test pins
    the raw behaviour so nobody 'optimises' the cast away.
    """
    green = np.uint16(1000)
    nir = np.uint16(3000)
    with np.errstate(over="ignore"):
        assert green - nir > 60000  # wraps around, not -2000
    assert float(green) - float(nir) == -2000.0


def test_to_reflectance_casts_to_float_and_nans_nodata():
    ds = _ds({"2023-03-01": dict(B02=0, B03=0, B04=0, B08=0, B11=0, B12=0)})
    out = to_reflectance(ds, _offsets(["2023-03-01"], -1000.0), RunLog("t"))
    assert out["B03"].dtype == np.float32
    assert np.isnan(out["B03"].values).all()  # DN 0 is nodata, not reflectance


def test_offset_is_applied_and_shifts_ndwi():
    """The point of the rule: an additive offset does NOT cancel out of NDWI."""
    dn = dict(B02=900, B03=1400, B04=1100, B08=1200, B11=1300, B12=1250)
    ds = _ds({"2023-03-01": dn})
    log = RunLog("t")

    corrected = to_reflectance(ds, _offsets(["2023-03-01"], -1000.0), log)
    uncorrected = to_reflectance(ds, _offsets(["2023-03-01"], 0.0), log)

    n_corr = float(ndwi(corrected["B03"], corrected["B08"]).values[0, 0, 0])
    n_unco = float(ndwi(uncorrected["B03"], uncorrected["B08"]).values[0, 0, 0])

    # (1400-1000)/(1200-1000) vs 1400/1200 -- same bands, very different NDWI.
    assert n_corr == pytest.approx((0.04 - 0.02) / (0.04 + 0.02), rel=1e-5)
    assert n_unco == pytest.approx((0.14 - 0.12) / (0.14 + 0.12), rel=1e-5)
    assert abs(n_corr - n_unco) > 0.25, "offset must change NDWI materially"


def test_offset_error_can_flip_the_water_classification():
    """Not academic: a missed offset moves a pixel across the NDWI >= 0 line.

    A common additive offset leaves the NUMERATOR (green - nir) untouched, so the
    sign only flips when the offset drives the DENOMINATOR negative -- i.e. for
    very dark pixels, which is exactly what deep water looks like in the NIR.
    That is the regime this whole analysis lives in.
    """
    dn = dict(B02=900, B03=900, B04=850, B08=800, B11=820, B12=810)
    ds = _ds({"2023-03-01": dn})
    log = RunLog("t")
    corr = to_reflectance(ds, _offsets(["2023-03-01"], -1000.0), log)
    unco = to_reflectance(ds, _offsets(["2023-03-01"], 0.0), log)
    wet_corr = float(ndwi(corr["B03"], corr["B08"]).values[0, 0, 0]) >= 0
    wet_unco = float(ndwi(unco["B03"], unco["B08"]).values[0, 0, 0]) >= 0
    assert wet_corr != wet_unco


def test_multiplicative_scale_does_cancel_but_offset_does_not():
    dn = dict(B02=900, B03=1400, B04=1100, B08=1200, B11=1300, B12=1250)
    ds = _ds({"2023-03-01": dn})
    log = RunLog("t")
    a = to_reflectance(ds, _offsets(["2023-03-01"], 0.0), log)
    off = _offsets(["2023-03-01"], 0.0)
    off["scale"] = 1000.0  # different scale, same offset
    b = to_reflectance(ds, off, log)
    na = float(ndwi(a["B03"], a["B08"]).values[0, 0, 0])
    nb = float(ndwi(b["B03"], b["B08"]).values[0, 0, 0])
    assert na == pytest.approx(nb, rel=1e-6)


def test_missing_offset_for_a_day_raises():
    ds = _ds({"2023-03-01": dict(B02=1, B03=1, B04=1, B08=1, B11=1, B12=1)})
    with pytest.raises(KeyError):
        to_reflectance(ds, _offsets(["2021-05-05"], 0.0), RunLog("t"))


def test_mndwi_uses_swir_not_nir():
    ds = _ds({"2023-03-01": dict(B02=900, B03=1400, B04=1100, B08=1200,
                                 B11=1300, B12=1250)})
    out = to_reflectance(ds, _offsets(["2023-03-01"], 0.0), RunLog("t"))
    assert float(mndwi(out["B03"], out["B11"]).values[0, 0, 0]) != pytest.approx(
        float(ndwi(out["B03"], out["B08"]).values[0, 0, 0])
    )
