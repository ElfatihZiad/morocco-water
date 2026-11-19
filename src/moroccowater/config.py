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
    # Flow topology: the slug of the reservoir this one drains into, or None when
    # the relationship has not been established. None is NOT "it drains nowhere";
    # it means unverified, and the cascade budget must refuse to run on it. A
    # reservoir that actually sits downstream of Al Massira cannot contribute to
    # its inflow, and assuming otherwise would silently invert the attribution.
    drains_to: str | None = None
    topology_verified: bool = False


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

# --- Upstream Oum Er-Rbia cascade -------------------------------------------
#
# These exist to answer the attribution question in docs/novelty.md: ~690 Mm3 was
# reportedly transferred into Al Massira from "ouvrages en amont" between Sep 2025
# and Jul 2026, against a total storage gain of ~984 Mm3. Measuring Al Massira
# alone cannot distinguish rainfall from redistribution.
#
# Coordinates are cross-validated: each dam's published coordinate matches a
# GloLakes/HydroLAKES centroid, which is independent corroboration that we are
# pointing at the right water body. GloLakes also publishes storage series for
# these upstream dams but NOT for Al Massira, so they double as free validation.

BIN_EL_OUIDANE = Reservoir(
    name="Bin el Ouidane",
    slug="bin_el_ouidane",
    bbox=(-6.75, 31.90, -6.20, 32.30),
    dam_lonlat=(-6.46361, 32.10667),  # en.wikipedia 32deg06'24"N 06deg27'49"W
    # ASSUMPTION: bbox stand-in for the El Abid headwaters in the High Atlas.
    catchment_bbox=(-6.60, 31.60, -5.90, 32.20),
    epsg=32629,
    resolution=60.0,
    max_area_km2=None,  # no published observed maximum found
    capacity_mm3=1500.0,
    notes=(
        "On the El Abid, a left-bank Oum Er-Rbia tributary. Completed 1953. "
        "Capacity figures CONFLICT across sources: 1500 (en.wikipedia), 1253, "
        "and 1215.5 Mm3. Resolve before using capacity in any budget."
    ),
    sources=(
        "en.wikipedia Bin el Ouidane Dam: 32.10667N 6.46361W, 1500 Mm3, 1953",
        "structurae.net: 32.10670N 6.46389W (~30 m from the Wikipedia value)",
        "GloLakes/HydroLAKES hylak_id=15136 centroid 32.1057N 6.4627W (match)",
    ),
)

HASSAN_I = Reservoir(
    name="Hassan I",
    slug="hassan_i",
    bbox=(-7.05, 31.65, -6.60, 31.98),
    dam_lonlat=(-6.82278, 31.81444),  # en.wikipedia 31deg48'52"N 06deg49'22"W
    # ASSUMPTION: bbox stand-in for the Lakhdar headwaters.
    catchment_bbox=(-7.10, 31.30, -6.60, 31.85),
    epsg=32629,
    resolution=60.0,
    max_area_km2=None,
    capacity_mm3=273.0,
    notes=(
        "On the Lakhdar, a left-bank Oum Er-Rbia tributary, ~19 km NE of "
        "Demnate. Completed 1986. fr.wikipedia gives a latitude 2 arcsec "
        "(~60 m) south of the English value; immaterial at 60 m pixels."
    ),
    sources=(
        "en.wikipedia Hassan I Dam: 31.81444N 6.82278W, 273 Mm3, 1986",
        "GloLakes/HydroLAKES hylak_id=175448 centroid 31.8153N 6.8217W (match)",
    ),
)

AIT_AADEL = Reservoir(
    name="Ait Aadel",
    slug="ait_aadel",
    bbox=(-7.45, 31.50, -7.05, 31.80),
    # This is a GloLakes lake CENTROID, not a dam wall -- which is actually the
    # better anchor for isolate_reservoir, since a centroid is certainly water
    # whereas a dam wall is not.
    dam_lonlat=(-7.2607, 31.6431),
    # ASSUMPTION: bbox stand-in for the Tessaout headwaters.
    catchment_bbox=(-7.50, 31.20, -7.00, 31.70),
    epsg=32629,
    resolution=60.0,
    max_area_km2=None,
    capacity_mm3=None,  # not found in any source consulted
    notes=(
        "On the Tessaout, a left-bank Oum Er-Rbia tributary. No Wikipedia "
        "article found in English or French; capacity and completion year "
        "unknown. Named 'Lac des Ait-Aadel' in HydroLAKES, which is how it was "
        "identified at all."
    ),
    sources=("GloLakes/HydroLAKES hylak_id=175486 'Lac des Ait-Aadel', "
             "centroid 31.6431N 7.2607W",),
)

# NOT YET CONFIGURED: Ahmed El Hansali, on the Oum Er-Rbia MAIN STEM near Zaouiat
# Ech Cheikh (~50 km from Kasba Tadla), 740 Mm3 gross / ~473 Mm3 regulated,
# commissioned 2003. It is the single most important dam for the cascade budget,
# being the main-stem reservoir immediately upstream of Al Massira -- and it has
# no Wikipedia article in either language, so no coordinate could be verified.
# Until one is, configuring it would mean guessing, and a mislabelled reservoir
# in a published dataset is worse than an absent one. See docs/decisions.md.

RESERVOIRS = {
    r.slug: r for r in (AL_MASSIRA, BIN_EL_OUIDANE, HASSAN_I, AIT_AADEL)
}

# Quality gates, with rationale.
MAX_SCENE_CLOUD_COVER = 60.0   # tile-level prefilter; AOI-level check is stricter
MAX_AOI_INVALID_FRAC = 0.20    # drop a scene if >20% of the AOI is unusable
AREA_CEILING_TOLERANCE = 0.10  # allow 10% above the published max before failing
MAX_MONTHLY_AREA_JUMP = 0.30   # flag >30% month-over-month change for review
