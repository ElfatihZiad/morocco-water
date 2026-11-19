"""Constants and per-reservoir configuration.

Reservoirs are configuration, not constants in code: the cascade framing in
docs/novelty.md needs this same pipeline pointed at the upstream dams next.
"""

from __future__ import annotations

from dataclasses import dataclass, field

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

COLLECTION_S2 = "sentinel-2-l2a"
COLLECTION_GSW = "jrc-gsw"
COLLECTION_TERRACLIMATE = "terraclimate"

# Sentinel-2 L2A bands we need. B11/B12 are 20 m native, which is why the whole
# analysis runs on a 20 m grid (see docs/mvp-plan.md).
S2_BANDS = ("B02", "B03", "B04", "B08", "B11", "B12", "SCL")

# ESA processing baseline 04.00 (from 2022-01-25) added a radiometric offset to
# L2A products. These are the documented defaults, used ONLY as a fallback when
# the STAC metadata does not carry scale/offset per band.
S2_BASELINE_OFFSET_DATE = "2022-01-25"
S2_FALLBACK_OFFSET = -1000.0
S2_FALLBACK_SCALE = 10000.0

# Scene Classification Layer values treated as unusable.
#   0 nodata, 1 saturated/defective, 3 cloud shadow,
#   8 cloud medium prob, 9 cloud high prob, 10 thin cirrus, 11 snow/ice
# SCL 2 (dark area) is deliberately KEPT: deep still water is often classified
# dark, and dropping it would bias area low exactly at low stage.
SCL_INVALID = (0, 1, 3, 8, 9, 10, 11)


@dataclass(frozen=True)
class Reservoir:
    """A reservoir to analyse."""

    name: str
    slug: str
    bbox: tuple[float, float, float, float]  # lon_min, lat_min, lon_max, lat_max
    dam_lonlat: tuple[float, float]  # (lon, lat) of the dam wall
    # Approximate contributing catchment UPSTREAM of the dam, for basin rainfall.
    # Rain on the lake surface is hydrologically irrelevant at this scale.
    catchment_bbox: tuple[float, float, float, float]
    epsg: int  # projected CRS for area measurement
    resolution: float = 20.0  # metres
    # Published reference values used by the sanity checks. None = unknown.
    max_area_km2: float | None = None
    capacity_mm3: float | None = None
    notes: str = ""
    sources: tuple[str, ...] = field(default_factory=tuple)


AL_MASSIRA = Reservoir(
    name="Al Massira",
    slug="al_massira",
    # Dam at 32.47528 N, 7.63750 W (Wikipedia); the reservoir extends upstream
    # to the east/south-east, so the box is asymmetric about the dam.
    bbox=(-7.80, 32.20, -7.00, 32.65),
    dam_lonlat=(-7.63750, 32.47528),  # Wikipedia: 32 deg 28'31"N 7 deg 38'15"W
    # ASSUMPTION: a bbox stand-in for the Oum Er-Rbia catchment upstream of the
    # dam, spanning the Middle/High Atlas headwaters eastward. ABHOER gives the
    # whole basin as ~35,000 km2 and most of it lies upstream of Al Massira. A
    # proper HydroBASINS or DEM-derived watershed is the follow-up; a bbox
    # includes some non-contributing area, which damps the rainfall signal
    # rather than inventing one.
    catchment_bbox=(-7.65, 31.40, -5.00, 33.40),
    epsg=32629,  # UTM 29N
    resolution=20.0,
    max_area_km2=128.0,
    capacity_mm3=2760.0,
    notes=(
        "Only surface-water source for the Doukkala irrigated perimeter. "
        "Receives intra-basin transfers from upstream Oum Er-Rbia works and "
        "feeds a ~7 m3/s pipeline to Marrakech, so storage change is NOT a "
        "closed basin balance. See docs/novelty.md section 6.1."
    ),
    sources=(
        "Bounif et al. 2023, J. Ecol. Eng. 24(2) 340-349 "
        "(area mean 72, min 23, max 128 km2; volume 264-2616 Mm3)",
        "Wikipedia: capacity 2760 Mm3, dam opened 1979",
    ),
)

RESERVOIRS = {r.slug: r for r in (AL_MASSIRA,)}

# Quality gates, with rationale.
MAX_SCENE_CLOUD_COVER = 60.0   # tile-level prefilter; AOI-level check is stricter
MAX_AOI_INVALID_FRAC = 0.20    # drop a scene if >20% of the AOI is unusable
AREA_CEILING_TOLERANCE = 0.10  # allow 10% above the published max before failing
MAX_MONTHLY_AREA_JUMP = 0.30   # flag >30% month-over-month change for review
