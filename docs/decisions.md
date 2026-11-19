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
