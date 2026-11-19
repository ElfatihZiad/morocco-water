# MVP plan

Written 2026-11-03, after the novelty assessment. The MVP target is unchanged
from the original brief — **Al Massira reservoir surface area from Sentinel-2
NDWI versus rainfall, 2016–present** — but it is now step one of the cascade
water-budget question in `docs/novelty.md` §6.8, which changes what the code must
be able to grow into.

## What the MVP must produce

1. A **per-scene** time series of Al Massira water-surface area (km²),
   2016–present, each row carrying its own quality metadata.
2. A **monthly** aggregate with an observation count per month, and gaps left as
   gaps.
3. A **volume** series derived from area, via the published Al Massira
   area→volume relationship.
4. A **rainfall** series over the contributing basin, for comparison at lag.
5. A **provenance record** sufficient to reproduce every number.
6. **Sanity checks that fail loudly**, not warnings nobody reads.

## Design decisions, and what I rejected

### Area is measured per scene, never from a monthly pixel composite
A monthly median composite blends shorelines from different dates into a blurred
margin, and the resulting area is not the area on any real day. Al Massira's
shoreline moves fast — Bounif et al. record a 73% area loss over six years, and
the 2025–26 recovery added ~984 Mm³ in under a year. So: measure area on each
usable scene, then aggregate the **areas**, not the pixels. Monthly values carry
`n_scenes`; months with none are gaps.
**Rejected:** monthly compositing (standard, cheaper, and wrong here).

### 20 m grid, not 10 m
NDWI could run at 10 m, but MNDWI needs SWIR (B11, 20 m native) and we want the
indices comparable on one grid. Resampling 20 m SWIR up to 10 m invents detail;
working at 20 m does not. 20 m is also 4× cheaper, which matters over ~10 years.
Shoreline-pixel bias is then a known, quantifiable term rather than a hidden one.
**Rejected:** 10 m (not comparable across indices); 60 m (too coarse at low stage,
where the lake is small and the answer matters most).

### Reproduce the published method as the baseline, then test NDWI against it
Bounif et al. (2023) validated a **combined-index threshold** on *this reservoir*
against in-situ retention at r = 0.97: `MNDWI ≥ 0 AND NDWI ≥ 0 AND NDVI ≤ 0 AND
AWEI ≥ 0`. That is a stronger starting point than an unvalidated NDWI-only rule,
so it becomes the reference. The brief's NDWI-only rule runs alongside it, and the
*difference between them* is a result in itself — it is the low-stage sensitivity
nobody has characterised.
**Rejected:** per-scene Otsu for the MVP. Published evidence shows Otsu returning
implausible thresholds on reservoir scenes, and we have a validated fixed
threshold for this exact dam. Otsu stays as a later comparison, not a default.

### The analysis mask comes from JRC Global Surface Water, not a hand-drawn polygon
`jrc-gsw` is on Planetary Computer and its `extent` band is the maximum observed
water extent, 1984–2021. Using it as the clip mask makes the reservoir boundary
**published, citable and reproducible**, and its own area gives a defensible
ceiling for the sanity checks — which closes the open question in
`docs/decisions.md`. Cross-check: it should land near Bounif's observed 128 km²
maximum.
**Rejected:** hand-digitising from a high-water scene (unreproducible);
HydroLAKES (not on PC, and its polygons are nominal rather than observed).

### The offset is read from metadata, with the date rule only as a logged fallback
Required by `CLAUDE.md`. The code inspects each item's `raster:bands`
scale/offset and `s2:processing_baseline`, applies what it finds, and only falls
back to "≥ 2022-01-25 implies offset −1000" with a warning. The pipeline then
asserts there is no mean-NDWI discontinuity across that boundary over permanent
water.
**Rejected:** hard-coding −1000 by date (silently wrong wherever PC's metadata
disagrees, and it is the exact failure this project exists to avoid).

### Rainfall is basin rainfall, not rainfall over the lake
Rain falling on the reservoir surface is hydrologically irrelevant at this scale;
what fills Al Massira is runoff from upstream. Bounif et al. report 71% of annual
inflow arriving February–June with a May peak, so the comparison must be made at
lag, not contemporaneously.
**Rejected:** correlating storage against rainfall over the reservoir footprint
(a common and meaningless analysis).

### TerraClimate first, CHIRPS second
CHIRPS is **not** on Planetary Computer, so it needs a second data path. Rather
than let that block the MVP, the rainfall comparison starts on `terraclimate`
(monthly precipitation, ~4 km, 1958–, PC-native) and CHIRPS is added behind the
same interface afterwards. TerraClimate is coarser and is **not** the dataset the
Moroccan validation literature used, so it is a development stand-in, not the
final answer.
**Rejected:** blocking the MVP on CHIRPS access; dropping CHIRPS (Moroccan
validation work is built on it, so the final analysis needs it).

### Volume reuses the published curve
Bounif et al.'s second-degree polynomial already maps area→impoundment at
R² = 0.98, RMSE 117.5 Mm³. Re-deriving it would duplicate validated work. The
open question is where it *breaks*: below their 23 km² minimum, at monthly rather
than annual resolution, and under siltation drift. Their coefficients were
scrambled by PDF text extraction, so the module ships the relationship behind a
single function with the coefficients flagged `# ASSUMPTION` until read off
Table 4.
**Rejected:** fitting our own curve (no in-situ series in hand yet).

## Module layout

```
src/moroccowater/
  config.py       constants: endpoints, collections, Al Massira AOI, thresholds
  provenance.py   RunLog — records every source, writes a JSON sidecar
  aoi.py          max-extent mask from JRC GSW; area ceiling
  sentinel2.py    STAC search, offset correction, cloud mask, float casting
  indices.py      ndwi / mndwi / ndvi / awei
  water.py        threshold -> water mask -> per-scene area
  checks.py       sanity assertions that raise
  volume.py       area -> volume via the published curve
  rainfall.py     basin-mean monthly precipitation
  pipeline.py     orchestration
```

Everything above the STAC layer takes arrays, not items, so it is testable
offline on synthetic data. The reservoir is a parameter, not a constant, because
the cascade framing needs the same pipeline pointed at Bin El Ouidane and Ahmed
El Hansali next.

## Validation plan

Four independent checks, each exercising a different part of the pipeline:

| Check | Against | Tests |
|---|---|---|
| Annual Aug–Sep area, 2016–2021 | Bounif et al. (6 overlapping years) | the whole optical chain |
| Derived volume at known dates | 105 Mm³ (Jul 2025), ~1,089 Mm³ (Jul 2026) | area→volume curve |
| No step at 2022-01-25 | our own series | offset correction |
| Max-extent area | Bounif's 128 km² maximum | the AOI mask |

## Sequencing

1. **Now:** AOI mask, STAC search, offset handling, cloud mask, indices, area,
   checks, tests. Produce the per-scene and monthly area series.
2. **Next:** volume series; rainfall at lag; the 2022-01-25 discontinuity figure.
3. **Then:** extend to Landsat for 1984–2015; add Sentinel-1 for low-stage
   cross-validation.
4. **Then:** generalise to the upstream cascade and close the basin water budget.

## Explicitly out of MVP scope

GRACE, NDVI, InSAR, additional basins, and the generic datacube abstraction. The
abstraction gets written once the pipeline has run on three reservoirs and the
real seams are visible, not before.
