"""Area to storage volume for Al Massira.

Reuses the published relationship rather than fitting a new one -- Bounif et al.
(2023) validated it against in-situ retention at r = 0.97, R² = 0.98,
RMSE 117.5 Mm³. See docs/decisions.md.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger("moroccowater.volume")

# ASSUMPTION (unresolved): Bounif et al. report a second-degree polynomial
# mapping lake area (km²) to impoundment (Mm³) with R² = 0.98, RMSE = 117.52,
# ME = 2.86. Their three coefficients -- 0.1205, 5.4883, 0.0227 -- came out of
# the PDF in an ambiguous order. The ordering below is INFERRED, not read: it is
# the only arrangement that reproduces their reported volume range (264-2616
# Mm³) over their reported area range (23-128 km²). Verify against Table 4 /
# Figure 8 before relying on any absolute volume.
#   V(A) = 0.1205 A² + 5.4883 A + 0.0227
BOUNIF_COEFFS = (0.1205, 5.4883, 0.0227)
BOUNIF_AREA_RANGE_KM2 = (23.0, 128.0)
BOUNIF_VOLUME_RANGE_MM3 = (264.0, 2616.0)
BOUNIF_RMSE_MM3 = 117.52
COEFFICIENTS_VERIFIED = False


def area_to_volume(area_km2, extrapolate: bool = False):
    """Storage volume (Mm³) from water-surface area (km²).

    Outside the range Bounif et al. observed, returns NaN unless `extrapolate`.
    That matters here: the 2022-24 minimum took the reservoir below their 23 km²
    floor, which is precisely where a quadratic fit is least trustworthy.
    """
    a = np.asarray(area_km2, dtype="float64")
    c2, c1, c0 = BOUNIF_COEFFS
    v = c2 * a**2 + c1 * a + c0

    lo, hi = BOUNIF_AREA_RANGE_KM2
    if not extrapolate:
        v = np.where((a >= lo) & (a <= hi), v, np.nan)
    return np.maximum(v, 0.0)


def describe() -> dict:
    """Provenance for the relationship, for the run log."""
    return {
        "source": "Bounif et al. 2023, J. Ecol. Eng. 24(2) 340-349",
        "form": "V(A) = c2*A^2 + c1*A + c0",
        "coefficients": BOUNIF_COEFFS,
        "coefficients_verified": COEFFICIENTS_VERIFIED,
        "r_squared": 0.98,
        "rmse_mm3": BOUNIF_RMSE_MM3,
        "valid_area_km2": BOUNIF_AREA_RANGE_KM2,
        "caveat": (
            "Coefficient ORDER is inferred from the paper's reported ranges, not "
            "read from its table. Siltation also makes the true relationship "
            "non-stationary across decades."
        ),
    }
