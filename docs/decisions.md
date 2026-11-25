# Decision log

Newest last. Each entry: date, the decision, the options considered, the reason,
and how to revisit it.

---

## 2026-11-03 — Repository layout and tooling

**Decision:** `src/` layout with an installable `moroccowater` package, `uv` for
environment and dependency management, notebooks importing from `src`.

**Options:** flat scripts at the repo root; a notebooks-first project; `src/`
layout with `uv`.

**Reason:** the `src/` layout prevents accidental imports from the working
directory and makes the package testable the same way it will be used. Notebooks
rot; keeping pipeline logic in `src/` means tests can cover it. `uv` gives a
locked, reproducible environment quickly.

---

## 2026-11-03 — Start from Al Massira before generalising

**Decision:** build the MVP end to end on one reservoir (Al Massira), then
generalise, rather than designing the multi-basin datacube tool first.

**Options:** generic datacube abstraction up front; single-reservoir vertical
slice first.

**Reason:** the hard parts (processing-baseline offset, cloud masking, water
thresholding, sanity checks) are only discoverable by doing one case properly.
An abstraction written before that would encode guesses.

---

## OPEN — CHIRPS access route

**Status:** unresolved; blocks the rainfall half of the MVP.

CHIRPS is not a Planetary Computer collection. Candidate routes: the Climate
Hazards Center THREDDS/HTTP archive (UCSB), Google Earth Engine, or a
third-party STAC. Needs a decision on which, plus whether to use CHIRPS v2 or
v3 — v3 is newer and reportedly tracks Moroccan variability better, but most
published Moroccan validation work used v2.

---

## OPEN — Water index and threshold

**Status:** unresolved; affects every area number we produce.

NDWI (McFeeters, green/NIR) is the stated MVP choice. MNDWI (Xu, green/SWIR)
performs better in published reservoir studies but SWIR is 20 m rather than 10 m.
Threshold: fixed 0 versus per-scene Otsu — published work shows Otsu can return
implausible thresholds on some scenes. Decide after inspecting Al Massira
histograms, and record the validation used.

---

## OPEN — Reservoir boundary polygon provenance

**Status:** unresolved.

The maximum-extent polygon used to clip the analysis needs a cited source
(HydroLAKES, GRanD, OpenStreetMap, or hand-digitised from a high-water scene).
Affects the area ceiling used in sanity checks.

---

## 2026-11-03 — Datacube tool abstracts over sources, not just STAC

**Decision:** design the reusable tool around a source-agnostic interface rather
than assuming everything arrives via STAC/odc-stac.

**Reason:** confirmed by querying the Planetary Computer STAC API directly — of
its 139 collections, **neither CHIRPS nor GRACE is present**. Both of the
project's non-optical variables therefore need a different access path, so a
STAC-only abstraction would have to be rewritten the moment the project moves
past Sentinel-2. Available and relevant on PC: `sentinel-2-l2a`,
`landsat-c2-l2`, `sentinel-1-rtc`/`-grd`, `jrc-gsw`, `modis-13Q1-061`,
`terraclimate`, `era5-pds`, `cop-dem-glo-30`.

**Consequence:** `terraclimate` (monthly precip, PDSI, soil moisture, ~4 km,
1958–) is the PC-native stand-in to develop the rainfall comparison against
while the CHIRPS route is being settled. It is not a replacement for CHIRPS in
the final analysis — coarser, and not the dataset Moroccan validation literature
used.

---

## 2026-11-03 — Extend the window to Landsat, not just Sentinel-2

**Decision:** keep the Sentinel-2 MVP as step one, then extend the reservoir area
series back through `landsat-c2-l2`.

**Options:** stay with Sentinel-2 (2015–); extend with Landsat (1982–).

**Reason:** Al Massira was commissioned in 1979, so Landsat covers nearly the
dam's whole operating life, including the early-1980s and mid-1990s droughts.
That turns "the worst drought on record" from a rhetorical claim into a
measurement, and gives every later analysis a baseline distribution. Cost: a
cross-sensor harmonisation problem (different bands, 30 m vs 10 m) and a
non-stationary area-volume relationship because of siltation.

---

## OPEN — Maximum-area ceiling for sanity checks

**Status:** unresolved; previously asserted wrongly.

The first-pass review used Wikipedia's 80 km² as a maximum. Nothing establishes
it as one. Until a sourced maximum exists (digitised high-water scene, HydroLAKES,
GRanD, or the DGH cote-surface curve), derive the ceiling from the clip polygon
and log it rather than hard-coding a number. See `docs/novelty.md` §5.

---

## OPEN — Inter-basin transfer as a structural break

**Status:** unresolved and time-sensitive; **highest-priority open question.**

The "autoroute de l'eau" phase 2 extends 210 km from Bouregreg to Al Massira.
Once commissioned, Al Massira's storage is no longer a function of its own basin's
hydrology, and any rainfall-to-storage relationship fitted across that transition
fits two different systems. Phase 1 (Sebou→Bouregreg) has been operational since
August 2023.

**Needed:** confirmation from ABHOER or the Ministère de l'Équipement et de l'Eau
of whether phase 2 is yet delivering water to Al Massira. If not, there is a
closing window to establish the pre-transfer satellite baseline. If so, the
analysis needs a documented break date and the MVP framing changes.

---

## 2026-11-03 — RESOLVED: maximum-area ceiling is 128 km²

Supersedes the OPEN entry above. Bounif et al. (2023) report, from Landsat over
1999–2021, a mean lake area of 72 km², minimum 23 km², **maximum 128 km²**.
Sanity checks use 128 km² + 10%. Wikipedia's 80 km² is nominal and is not a
bound. Volume is additionally bounded by their in-situ range, 264–2,616 Mm³.

---

## 2026-11-03 — RESOLVED: the Sebou transfer does not yet reach Al Massira, but
## the reservoir is already heavily managed

Supersedes the OPEN entry above. Verified:

- The transfer commissioned 28 Aug 2023 (≤15 m³/s) feeds **Sidi Mohamed Ben
  Abdellah**, not Al Massira. Phase 2 to Al Massira is still studies/tendering.
- **However:** ~690 Mm³ was transferred into Al Massira from upstream Oum Er-Rbia
  works between Sep 2025 and Jul 2026, against a total storage gain of ~984 Mm³.
- **And:** the dam was perforated for a ~7 m³/s, ~125 km pipeline to Marrakech
  (AfDB), reported as partially commissioned.

**Consequence:** there is no clean "pre-transfer" baseline to establish, and the
MVP's rainfall-versus-storage comparison cannot be interpreted as a closed
basin. Storage change must be decomposed into natural inflow, transfers in, and
abstraction out. This is now the project's central question rather than a
caveat — see `docs/novelty.md` §6.8.

---

## 2026-11-03 — Do not rebuild the area→volume relationship

**Decision:** reuse Bounif et al.'s (2023) published second-degree polynomial for
Al Massira area→impoundment rather than deriving one, and spend the effort on
testing where it breaks.

**Reason:** they already fit it against in-situ retention at r = 0.97, R² = 0.98,
RMSE 117.5 Mm³. Re-deriving it would duplicate validated work. The open questions
are the ones they could not address: does it hold at the extreme low stage
observed in 2022–24 (below their 23 km² minimum), does it hold at monthly rather
than annual resolution, and how far has siltation shifted it since.

**Caveat:** the published coefficients were scrambled by PDF text extraction and
must be read off Table 4 / Figure 8 before use.

---

## OPEN — Scope of the cascade

**Status:** unresolved; needed before the datacube tool's interface is fixed.

The revised framing requires monitoring the whole Oum Er-Rbia reservoir cascade,
not just Al Massira. Candidates upstream: Bin El Ouidane, Ahmed El Hansali,
Ait Aadel, Hassan I. Needs a decision on which reservoirs are in scope and a
sourced polygon for each. GloLakes already covers several of them, which gives
free upstream validation.

---

## 2026-11-03 — Offset comes from `s2:processing_baseline`, not a date rule

**Finding:** Planetary Computer's `sentinel-2-l2a` publishes **no
`raster:bands` scale/offset** — verified by inspecting both a baseline-02.12
item (2019) and a baseline-05.10 item (2023), plus the collection's
`item_assets`. All three carry only `eo:bands`, `gsd`, `proj:*`. So the
authoritative STAC route for the radiometric offset does not exist on this
catalogue.

**Decision:** resolve the offset in three tiers — `raster:bands` if ever present,
then **`s2:processing_baseline`** (>= 04.00 implies `BOA_ADD_OFFSET` = −1000),
then the acquisition-date rule as a last resort with a warning.

**Reason:** the baseline string *is* per-item metadata, so tier 2 still satisfies
CLAUDE.md's "read it from metadata, don't hard-code by date". It is strictly
better than the date rule, because a scene reprocessed under a new baseline is
labelled correctly even though its acquisition date is old — and this archive is
full of them (the 2019 scene above was processed in 2020, the 2023 scene in 2024).

**Consequence for the project:** this is direct evidence for gap 3 in
`docs/novelty.md` — the offset discontinuity is a real trap on the most widely
used public Sentinel-2 catalogue, and nothing in the metadata warns you about it.

---

## 2026-11-03 — AOI mask validated: 128.3 km² vs a published 128.0 km²

**Decision:** the analysis mask is the JRC GSW occurrence >= 5% envelope,
restricted to the connected water body containing the dam.

**Why the isolation step is needed:** GSW flags every surface-water pixel in the
box — 530 connected components over Al Massira's bbox. Without isolation the
mask included the Oum Er-Rbia upstream and downstream of the dam plus irrigation
canals and farm ponds (9,343 px, ~3.7 km²). Those respond to rainfall on a
different timescale than reservoir storage, so counting them would both inflate
the area and smear the signal. The component is selected by the dam coordinate
rather than by size, so it is anchored to a known location.

**Result — this is a real validation, not a configuration note.** The isolated
max-extent mask measures **128.3 km²**. Bounif et al. (2023) report an observed
maximum of **128 km²** from Landsat over 1999–2021. Two independent datasets
(JRC GSW 1984–2021 vs Landsat 1999–2021) and two independent methods agree to
0.2%. That simultaneously confirms the mask, the projection and area arithmetic,
and the 128 km² ceiling now used in the sanity checks.

**Side effect:** cropping to the isolated body shrank the grid from
2552x3799 to 780x1613 px — a ~6x reduction in the read, which is what makes a
full 2016-2026 run practical.

---

## 2026-11-03 — First real measurements (smoke test)

Four scenes over Jun-Dec 2019 produced areas of 42.9-45.9 km² (combined rule)
and 43.3-46.5 km² (NDWI only). Plausible for mid-drought against Bounif's
1999-2021 mean of 72 km². The two rules differ by ~0.5-0.6 km², with NDWI
consistently *higher* — consistent with NDWI admitting pixels the combined rule
rejects. Whether that gap widens at low stage is the open question the
low-stage comparison is meant to answer.

**Not yet run:** the full 2016-2026 series. At ~20 s/solar-day after the crop,
several hundred usable days is roughly 2-3 hours, so it needs a background run.

---

## 2026-11-05 — REVERSED: TerraClimate cannot be the rainfall source

Supersedes the 2026-11-03 decision to start on TerraClimate.

**Finding:** Planetary Computer's `terraclimate` zarr store ends at
**2021-12-01** (768 monthly steps from 1958-01). It therefore covers *none* of
the period this project is about — not the 2022–24 collapse, not the 2025–26
recovery.

**How it surfaced, and why it mattered:** a first pass summed the returned
months per hydrological year and reported 90.4 mm for Sep 2021–Aug 2022 against
a 394.6 mm 1991–2020 normal — a 77% deficit that would have looked like a
spectacular result. It was an artefact: only 4 of 12 months existed and the sum
treated the absent ones as zero. `rainfall.py` now raises `CoverageError` when
the requested window is not fully present, before any aggregation.

**Decision:** CHIRPS is required, not optional, and becomes the next piece of
work rather than a follow-up. `era5-pds` is the fallback if CHIRPS access is
awkward.

**Retained value:** TerraClimate is still a usable 1958–2021 baseline for
computing long-term normals and placing the drought in context — just not for
the drought years themselves.

**Transferable lesson:** a silently truncated time series reads as a dramatic
anomaly. Every external series now gets a coverage assertion before it is
aggregated.

---

## 2026-11-05 — Rainfall is CHIRPS v3.0, read directly from CHC

**Decision:** `src/moroccowater/chirps.py` reads CHIRPS **v3.0** monthly GeoTIFFs
from the Climate Hazards Center over `/vsicurl`, windowed to the catchment, with
a local cache of monthly means.

**Path, because the server moved:** `CHIRPS-2.0/` no longer exists on
data.chc.ucsb.edu — the tutorials that cite
`products/CHIRPS-2.0/global_monthly/tifs/` all 404 now. The current layout is
`products/CHIRPS/v3.0/monthly/global/tifs/chirps-v3.0.YYYY.MM.tif`, confirmed by
listing: **549 months, 1981-01 through 2026-09.**

**Why v3.0 over v2.0:** Funk et al. (Sci. Data 2026) report v3 capturing observed
Moroccan rainfall variability better than v2, on a Tensift basin case study. The
cost is that most published Moroccan validation work used v2, so comparisons
against that literature carry a version caveat.

**Operational notes:** the CHC server rate-limits — it returns 429 to rapid
requests, including HEAD. The module sets `CPL_VSIL_CURL_USE_HEAD=NO`, pauses
1.5 s between months, and leans on GDAL's retry. Windowed reads mean a month
costs a range request instead of a global download.

**Coverage guard:** the same `CoverageError` check added after the TerraClimate
truncation applies here, so a short series fails rather than being averaged.

---

## 2026-11-05 — First rainfall result: the 2025-26 wet season was exceptional

CHIRPS v3.0, catchment mean upstream of Al Massira:

| Month | mm |
|---|---|
| 2025-11 | 43.8 |
| 2025-12 | 186.6 |
| 2026-01 | 159.4 |
| 2026-02 | 84.0 |
| 2026-03 | 108.0 |
| 2026-04 | 71.7 |
| **Nov–Apr total** | **653.5** |

For context, TerraClimate puts the 1991–2020 **annual** normal for this
catchment at 394.6 mm. So those six months delivered ~1.65x a normal *year*.
That is independent corroboration of the 519 mm / "64% above normal" basin
figure reported by Le360 for 1 Sep 2025 – 25 Mar 2026.

**What it does and does not settle.** It confirms the rain genuinely fell, so the
recovery is not purely an artefact of water being moved around. It does **not**
resolve the attribution question, because ~690 Mm³ was still reportedly
transferred into Al Massira from upstream works over roughly the same window
against a total storage gain of ~984 Mm³. Both things can be true: an
exceptional wet season upstream, captured by upstream dams, and then released
downstream. That is precisely the cascade budget in `docs/novelty.md` §6.8, and
it now has a measured rainfall term.

---

## 2026-11-05 — Asset signing must happen per batch, not at search time

**Bug, and it took 90 minutes to surface.** The catalogue was opened with
`modifier=pc.sign_inplace`, which rewrites every asset href with a SAS token at
**search** time. odc-stac then builds a *lazy* dask graph that may not read
those hrefs for an hour or more. Planetary Computer's tokens expire well inside
that window, so a long run dies partway through with

```
TIFFFillTile:Read error ... got 0 bytes, expected 392791
rasterio.errors.WarpOperationError: Chunk and warp failed
```

Short smoke tests passed throughout, because they finished inside the token's
lifetime. This is the worst shape of bug: invisible at small scale, fatal at
full scale, and the error message says nothing about credentials.

**Decision:** `open_catalog()` no longer signs by default. Hrefs stay unsigned
through search, and `patch_url=pc.sign` on each `odc.stac.load` signs them when
that batch's graph is built — so freshness is tied to the batch, which is sized
to finish comfortably inside the token lifetime.

**Corollary:** batches are now **monthly**, not yearly. A year of reads outlives
the token. Each batch is also isolated — one failure is recorded in the run log
and skipped, and a rerun retries just that month, instead of losing the whole
pass.

**Transferable lesson:** with lazy evaluation, a credential's lifetime must be
compared against when the read happens, not when the URL is built.

---

## 2026-11-05 — Other fixes found while getting the full run to complete

- **OOM, first attempt.** One dask graph over all 664 solar days exhausted a
  24 GB machine: it ran 8 hours at ~0 CPU with 12 GB of swap in use, making no
  progress. Batching is what makes the run finish, not a tuning nicety.
- **Chunk spec.** `{"x": -1}` is not accepted by odc-stac ("an integer is
  required"); use a number larger than the AOI (4096) for one spatial chunk.
- **GDAL config types.** `GDAL_CACHEMAX` and `VSI_CACHE_SIZE` must be passed to
  `rasterio.Env` as ints; strings raise the same cryptic "an integer is
  required" from `GDALSetCacheMax64`.
- **Throughput is latency-bound, not CPU-bound.** A full-year batch sat at 4%
  CPU. Concurrency tuning (32 threads, HTTP/2 multiplexing, VSI caching) helped
  less than hoped, because loading 10 m bands onto a 20 m grid forces a warp of
  4x the pixels actually needed. Hence `--resolution`: a 60 m pass reads from
  the COGs' internal overviews and is far cheaper, with shoreline precision as
  the trade. The plan is a coarse pass over the full decade plus a 20 m pass
  where precision matters, with the two compared on a common year.

---

## 2026-11-19 — An empty scene is not an error

**Bug.** `check_reflectance_range` sampled the first scene of each monthly batch
and raised `SanityError` if it was all-NaN. Sentinel-2 scenes clipped at the
edge of an orbit, or wholly cloud-masked, legitimately contain no valid pixel
over the AOI — so one such scene aborted the entire month.

**Cost: 11% of the series.** 14 of 131 monthly batches failed, among them
**2026-01 and 2026-02** — both inside the recovery the project is about.

**Fix.** The check now examines several scenes, skips empty ones, and raises only
if *every* sampled scene is empty (which would indicate a wrong geobox, mask or
offset, and is worth failing on). Empty scenes need no special handling
downstream: they come through with `valid_frac` 0 and are already excluded by the
monthly aggregation's gate.

**Lesson, and it cuts against the project's own rules.** CLAUDE.md says checks
should "fail loudly, not quietly produce a plot", and that is right — but a check
whose failure mode is *discarding valid data* is its own kind of silent error.
The abort was logged and isolated per batch, so nothing looked broken; the series
simply had holes. A check needs to distinguish "this data is wrong" from "this
data is absent", and only the first is a fault.

---

## 2026-11-19 — The radiometry check must judge usable pixels, not cloud

**Second bug in the same check.** After the empty-scene fix, four more months
still failed with `B03: reflectance outside [-0.1, 1.6] (max=1.641)`. The bound
looked too tight, and the tempting fix was to widen it.

**Diagnosing instead of widening.** For 2017-03, the one available scene has a
**median** B03 of 1.036, with 57% of pixels above 1.0 and a maximum of 1.681.
That is not a reservoir; it is a scene that is almost entirely thick cloud. Cloud
tops legitimately exceed 1.0 reflectance. The data was fine and the check was
looking at the wrong pixels.

**Fix.** `check_reflectance_range` now takes the SCL-derived `valid` mask and
judges only usable pixels, on **percentiles** (p0.1, p99.9) rather than extremes,
with a looser absolute bound to catch gross scale errors. A fully-clouded scene
then has no usable pixels, counts as empty, and is dropped by the `valid_frac`
gate as intended.

This makes the check *more* sensitive, not less: a misapplied offset drives the
dark end negative, and that signal was previously swamped by cloud outliers.

**Lesson.** When a sanity check fires on data you believe is good, the first move
is to find out what the data actually looks like, not to relax the threshold.
Here the measured distribution said "this is a cloud", which pointed at the real
defect — the check was running before masking rather than after.

---

## 2026-11-19 — Cascade reservoirs added; flow topology deliberately unverified

Added Bin el Ouidane, Hassan I and Ait Aadel. Each dam's published coordinate
matches a GloLakes/HydroLAKES centroid to within ~100 m, which is independent
corroboration that we are pointing at the right water body — and it corrected a
wrong guess: hylak_id 175448 is **Hassan I**, not Ahmed El Hansali as earlier
assumed. GloLakes also publishes storage for these upstream dams but not for Al
Massira, so they double as free validation.

**`drains_to` and `topology_verified` default to unverified, and the budget must
refuse to run without them.** El Abid, Lakhdar and Tessaout are all confirmed
left-bank Oum Er-Rbia tributaries joining from the south, but no source
consulted establishes whether the Lakhdar and Tessaout confluences lie **upstream
or downstream of Al Massira**. That distinction decides the whole attribution: a
reservoir downstream of Al Massira cannot contribute to its inflow, and assuming
otherwise would silently invert the result.

Measuring these reservoirs is safe and useful regardless; *budgeting* needs the
topology. Establishing it is its own task — flow accumulation over the Copernicus
DEM (on Planetary Computer) or HydroSHEDS/HydroBASINS routing.

**Ahmed El Hansali is deliberately NOT configured.** It is the main-stem
reservoir immediately upstream of Al Massira, so it matters most of the four, and
it has no Wikipedia article in English or French. Sources place it on the upper
Oum Er-Rbia near Zaouiat Ech Cheikh, ~50 km from Kasba Tadla, 740 Mm3 gross and
~473 Mm3 regulated, commissioned 2003 — but no verifiable coordinate was found. A
mislabelled reservoir in a published dataset is worse than an absent one.

---

## 2026-11-19 — Flow topology by DEM routing, with a built-in validation gate

**Decision:** resolve which reservoirs drain into Al Massira by D8 flow routing
over `cop-dem-glo-90`, delineating Al Massira's catchment from its dam as a pour
point and testing each other dam for membership.

**Why it carries its own check.** The delineated catchment area must land near Al
Massira's published ~35,000 km². If it does not, the routing is wrong and no
membership result from that run may be used. `resolve()` returns
`routing_validated` and records an explicit assumption when it fails.

**The gate immediately earned its place.** The first run returned a catchment of
**623 km² against 35,000 — 98% too small** — and reported all three reservoirs as
outside the catchment. Had the check not been there, "Bin el Ouidane does not
drain into Al Massira" would have been a confident, published, wrong answer that
inverted the entire attribution.

**Root cause: the pour-point snap.** The dam coordinate must be moved onto the
trunk channel before delineation, and the first implementation snapped to any
cell with accumulation above 20,000 cells. At 90 m that is only ~162 km² of
upstream area, so the pour point landed on a minor side stream about 1 km away.

**Fix:** snap to the **local maximum** of flow accumulation within a 5 km radius.
This needs no threshold to be guessed and lands on the trunk by construction. The
run now also reports the accumulation at the snapped cell, which should
correspond to ~35,000 km² and so cross-checks the catchment mask against the
accumulation grid independently, and the raw accumulation at each reservoir's own
dam, which distinguishes a main-stem dam from a headwater one.

**Lesson.** A validation gate is worth more than the analysis it guards. The
expensive part here — DEM conditioning, routing — was correct; the cheap part, a
magic-number threshold, was wrong, and only a comparison against an independent
published quantity could tell the difference.

---

## 2026-11-19 — pysheds under NumPy 2: shim rather than pin

pysheds 0.5 calls `np.in1d`, removed in NumPy 2.0. Pinning NumPy below 2 was
rejected: xarray, odc-stac and the rest of the stack need 2.x.

All nine call sites in `pysheds/sgrid.py` are the identical pattern
`np.in1d(fdir.ravel(), dirmap).reshape(fdir.shape)`. The input is already 1-D, so
`np.isin` is an exact drop-in rather than an approximation — verified by reading
every occurrence, not assumed from the function's docstring. The shim is applied
in `topology.py` before the pysheds import, with a test asserting the
equivalence on an array containing an invalid flow direction.

---

## 2026-11-19 — Testing the 2022 offset: measure something that cannot change

The pipeline reported a **-39.6% step in reservoir area across 2022-01-25**,
which is genuinely ambiguous: the drought was collapsing through that window
(2021 dry season 26.4 km², 2022 16.7 km²), so a real step of that size is
expected. Asserting "it's just the drought" would be exactly the kind of
unverified claim this project is supposed to avoid.

**Design: `offset_demo.py`.** Measure the median NDWI over **stable land** just
outside the reservoir's maximum extent — a quantity with no hydrological reason
to change at an arbitrary processing date — for scenes either side of the
boundary, computed three ways:

1. offset resolved per item from its processing baseline (our pipeline);
2. offset forced to zero (what a naive pipeline does);
3. offset applied to every scene (over-correction).

A step in arm 2 is pure artefact. Its absence in arm 1 is evidence the correction
works, and arm 3 bounds the error in the other direction. The reservoir's own
area cannot serve as the test statistic, because its change is confounded with
the drought; land can.

---

## 2026-11-24 — RESULT: the 2022 offset is a real artefact, and the correction removes it

`offset_demo.py` ran over 2021-04-25..2022-10-25 (96 solar days, baselines
03.00 / 04.00 / 05.10, 52 days carrying the offset), measuring median NDWI over
stable land outside the reservoir — a quantity with no hydrological reason to
change at a processing date.

| arm | land NDWI before | after | step |
|---|---|---|---|
| **corrected** (offset per item's baseline) | −0.2939 | −0.3057 | **−0.0118** |
| **uncorrected** (offset ignored) | −0.2927 | −0.2270 | **+0.0658** |
| **over-corrected** (offset applied to all) | −0.4581 | −0.3057 | **+0.1523** |

**Findings.**

1. **Ignoring the offset injects a spurious +0.066 NDWI step** at an arbitrary
   processing date. Nothing physical happened on 2022-01-25; this is pure
   artefact.
2. **Our correction reduces it to −0.012**, about 5.6x smaller and at the level
   of scene-to-scene noise. The correction works.
3. **Over-correcting is worse than doing nothing** (+0.152), which is worth
   knowing: applying −1000 to every scene — an easy mistake when back-filling an
   archive — produces a larger artefact than ignoring the offset entirely.

**Why it matters for the headline number.** NDWI is thresholded at 0 to classify
water, so a 0.066 shift moves the land/water boundary wherever the index sits
near zero — the shallow shoreline, which is exactly where a drawdown is measured.

**And it settles the ambiguity.** The pipeline had reported a −39.6% step in
*reservoir area* across the same boundary. Since the corrected land series is
flat there, that area step is **hydrological, not radiometric** — it is the
drought (2021 dry season 26.4 km² → 2022 16.7 km²), measured correctly. The
discontinuity check was right to flag it and right not to raise.

This is the deliverable for gap 3 in `docs/novelty.md`: none of the Moroccan
Sentinel-2 studies reviewed discusses the baseline-04.00 offset, and it lands
mid-drought on the most widely used public catalogue.

---

## 2026-11-24 — Pour-point selection, third attempt: over the water mask

Two failures, both caught by the 35,000 km² validation gate rather than by
inspection:

| attempt | pour point rule | catchment |
|---|---|---|
| 1 | first cell with accumulation > 20,000 cells | 623 km² |
| 2 | local accumulation maximum within 5 km | 1,622 km² |
| 3 | maximum accumulation on the reservoir's water mask | (pending) |

**Why attempt 2 failed, which is the interesting part.** Routing was never
broken: the global accumulation maximum is 3,299,153 cells = **26,723 km²**,
within the ±25% tolerance of the published 35,000 km². But it sits at
(−7.3817, 32.4640) — **24 km east of the dam wall, mid-reservoir.**

The cause is that `cop-dem-glo-90` is a *surface* model, so the impounded lake is
a flat plane. `resolve_flats` disperses flow across that plane instead of
concentrating it at the outlet, so the trunk's accumulation peaks where the river
*enters* the reservoir, not at the wall. Measured from the dam, accumulation
within 5 km is 1,622 km², within 15 km 1,782 km², and only at 40 km does it
reach 26,723 km².

**Fix:** choose the pour point as the highest-accumulation cell on the
reservoir's own JRC GSW water mask, loaded on the DEM's geobox so it is
cell-for-cell aligned with the flow grid. This is reservoir-size adaptive, needs
no radius guessed, and is where the trunk actually enters. The radius rule
survives only as a fallback.

**Lesson.** Three wrong answers in a row, each internally consistent and each
caught only by an external published quantity. The diagnostic that mattered was
not reading the code but asking the data where the accumulation maximum actually
was — the answer (24 km east) immediately explained the failure and named the
cause.

---

## 2026-11-24 — Runner scripts belong in the package, not the scratchpad

Topology attempt 3 appeared to produce the identical result to attempt 2 —
1,622 km², same 6.7 km snap shift. It had not run at all: the driver script lived
in a session scratchpad that had since been cleared, so Python exited
immediately, the old JSON stayed on disk, and the stale file read as a fresh
result.

**Fix:** `topology.py` now has its own `main()` and is run as
`python -m moroccowater.topology`, like every other module here. No analysis step
depends on a file outside version control.

**Lesson.** The failure was not the missing script — that error was loud and
immediate. It was that a stale output file was indistinguishable from a current
one. Outputs that get overwritten in place need either a timestamp checked
against the run, or deletion before the run. The run now writes
`<target>_topology.json` through the CLI, and the stale copy was removed rather
than left to be misread again.
