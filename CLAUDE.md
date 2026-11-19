# CLAUDE.md — Morocco Drought & Water Security

## Project

Quantify how Morocco's water system responded to the recent multi-year drought,
basin by basin, using satellite data. The guiding question:

> How did reservoirs, groundwater and farmland respond to the recent multi-year
> drought, basin by basin?

**MVP (current scope):** Al Massira reservoir surface area from Sentinel-2 NDWI
versus CHIRPS rainfall, 2016–present.

**Later (not yet in scope):** GRACE/GRACE-FO terrestrial water storage, NDVI for
farmland response, additional basins (Oum Er-Rbia, Sebou, Tensift, Moulouya,
Souss-Massa), InSAR subsidence as a groundwater-depletion proxy, and a reusable
datacube tool that generalises the pipeline across basins and variables.

## Data & stack

- **Access:** Microsoft Planetary Computer STAC API (`https://planetarycomputer.microsoft.com/api/stac/v1`).
  Asset hrefs need signing — `planetary_computer.sign_inplace` as the odc-stac patch_url.
- **Stack:** `pystac-client` (search), `odc-stac` (STAC items -> xarray), `xarray`
  (labelled arrays), `dask` (lazy/chunked compute), `geopandas`/`shapely` (basin
  and reservoir geometries), `rioxarray` (CRS/reprojection).
- **Collections in use:** `sentinel-2-l2a`.
- **Collections planned:** `chirps` is *not* on Planetary Computer — CHIRPS comes
  from the Climate Hazards Center (UCSB) directly or via another STAC. Resolve
  and record this before writing rainfall code.

## Working agreement

The user is a data engineer using this project for interview prep. **They make the
design decisions.** So:

1. **Write the pipeline code; don't wait for sign-off on it.** (Revised
   2026-11-03 — the original rule was "propose a plan and wait". Momentum matters
   more than approval gates now: we are chasing genuine novelty, and the open
   questions are empirical, so running the pipeline is how they get answered.)
   Still write the plan down first for anything substantial, in `docs/`, and keep
   going rather than blocking.
2. **Stop and ask only for decisions that are expensive to reverse** — the
   research framing, which basins and reservoirs are in scope, what counts as a
   result, anything that changes what we claim. Implementation choices are yours
   to make and explain.
3. **Explain choices, don't just make them.** Every non-obvious parameter (NDWI
   threshold, cloud-cover cut-off, resampling method, chunk size) gets a one-line
   rationale in the code or in `docs/decisions.md`.
4. **Prefer legible code over clever code.** This is read by an interviewer.

## Engineering rules

### Cast bands to float before arithmetic
Sentinel-2 L2A bands arrive as `uint16`, with 0 as nodata. Integer arithmetic
silently truncates and underflows (`B03 - B08` wraps around on unsigned ints), so
**cast to `float32` and convert 0 to `NaN` before computing any index.** Never
compute NDWI on raw integer DNs.

```python
green = ds.B03.where(ds.B03 != 0).astype("float32")
nir   = ds.B08.where(ds.B08 != 0).astype("float32")
ndwi  = (green - nir) / (green + nir)
```

### Handle the Sentinel-2 January 2022 processing-baseline offset
From **2022-01-25**, ESA processing baseline 04.00 added a radiometric offset to
L2A products: `BOA_ADD_OFFSET = -1000` for all bands. Reflectance is

```
reflectance = (DN + BOA_ADD_OFFSET) / BOA_QUANTIFICATION_VALUE   # = (DN - 1000) / 10000
```

while pre-baseline-04.00 products are simply `DN / 10000`.

**This does not cancel out of NDWI.** A normalised difference is invariant to a
multiplicative scale factor but *not* to an additive offset, so mixing corrected
and uncorrected scenes puts a step change in the time series at exactly the
moment we are trying to measure a trend. Always:

- Read the offset per item from the STAC metadata where available, rather than
  hard-coding `-1000`.
- Fall back to the `>= 2022-01-25` date rule only with a logged warning.
- Convert every scene to true reflectance **before** computing NDWI.
- Assert that reflectance lands in a plausible range (roughly -0.1 to 1.6) and
  that the mean NDWI over permanent water has no discontinuity across the
  2022-01-25 boundary.

### Log every data source
Any function that fetches data records, to the run log and to the output's
attrs/metadata sidecar: collection id, STAC endpoint, item ids (or a count plus a
hash when there are many), asset keys, bbox/geometry, date range, CRS, resolution,
processing baseline, and the retrieval timestamp. A result that cannot be traced
back to its exact inputs is not a result.

### Add sanity checks
Every derived quantity gets cheap assertions that would fail loudly on a bad
pipeline, not quietly produce a plot. At minimum:

- Reflectance within physical range; NDWI within [-1, 1].
- Reservoir area is never negative, and never exceeds the maximum-extent polygon
  it was clipped to. For Al Massira the ceiling is **128 km² + 10% tolerance** —
  128 km² is the observed 1999–2021 Landsat maximum (Bounif et al. 2023; mean
  72 km², min 23 km²). Wikipedia's 80 km² is a nominal figure, not a maximum, and
  must not be used as a bound. Anything above ~141 km² is a bug, not a wet year.
- Derived volume is cross-checked against the in-situ range Bounif et al. report,
  264–2,616 Mm³, and against their area→volume polynomial (R² = 0.98,
  RMSE = 117.5 Mm³). A monthly value outside that envelope needs explaining.
- Scene count per month > 0 before reporting a monthly value; report the count
  alongside the value.
- Cloud/shadow-masked fraction logged per scene; drop scenes over a stated
  threshold instead of letting clouds drive the water mask.
- Area time series checked for physically implausible jumps (e.g. >30% month over
  month) — flag, investigate, don't smooth away.
- Area-derived volume must account for siltation: Al Massira's capacity is **not
  stationary** over a multi-decade window, so one fixed area-volume curve cannot
  be used across 40 years of Landsat. Flag the curve's vintage.
- CHIRPS totals compared against a published figure for a known year.

### Flag assumptions explicitly
When a choice is not derivable from the data, say so in the code with an
`# ASSUMPTION:` comment and add a dated entry to `docs/decisions.md`. Examples
that must be flagged, not buried: the NDWI water threshold (0 is conventional but
scene-dependent — Otsu is an alternative), the maximum acceptable cloud cover,
whether to use B08 (10 m NIR) or B8A (20 m, narrower), using NDWI
(McFeeters, green/NIR) versus MNDWI (Xu, green/SWIR), the reservoir boundary
polygon's provenance, and how months with no usable scene are handled (gap vs
interpolation — default to a gap).

## Conventions

- Source lives in `src/moroccowater/`, installed editable; notebooks import from
  it and contain no pipeline logic worth keeping.
- `data/` is git-ignored. Raw downloads go to `data/raw/` and are never edited in
  place.
- Decisions go in `docs/decisions.md`, newest last, each with a date, the options,
  the choice and the reason.
- Run `uv run pytest` and `uv run ruff check` before saying something works.
