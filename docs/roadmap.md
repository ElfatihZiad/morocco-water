# Roadmap

Three phases, each ending in something that stands on its own. Agreed
2026-11-19.

The ordering is deliberate: the reusable tool comes **last**, built from three
real use cases, rather than being designed up front from guesses about what
would be reusable. An abstraction written before the seams are visible encodes
assumptions instead of experience.

---

## Phase 1 — Morocco drought: surface water (in progress)

**Question:** how did reservoir storage across Morocco's basins respond to the
2016–2024 drought and the 2025–26 recovery, and how much of the recovery was
rainfall versus water moved between reservoirs?

**Status.** Al Massira is measured, 2016–2026, from Sentinel-2. Dry-season area
fell from 79.3 km² (2016) to **5.8 km² (2024)** — a 93% loss, with every month
from 2022 on below the published 1999–2021 minimum of 23 km² — then recovered to
63.7 km² by 2026.

**Remaining.**
1. Fix the all-NaN batch abort (currently loses 11% of months, including
   2026-01/02) and backfill.
2. Generalise to the Oum Er-Rbia cascade: Bin El Ouidane, Ahmed El Hansali,
   Ait Aadel, Hassan I.
3. Close the basin budget — separate rainfall-driven gain from upstream
   redistribution. ~690 Mm³ was reportedly transferred into Al Massira from
   upstream works between Sep 2025 and Jul 2026, against a total gain of
   ~984 Mm³. Those two figures are the heart of the question.
4. CHIRPS rainfall at lag; the Sentinel-2 baseline-offset discontinuity figure.

**Deliverable:** an open, validated, per-reservoir monthly storage series for the
basin — which does not currently exist publicly — plus the attribution result.

**Why it is novel.** Baba et al. (2025) published a Sentinel-1 radar series for
Moroccan reservoirs through 2024 but computed no cascade budget. Bounif et al.
(2023) and Hanadé Houmma et al. (2026) treat Al Massira in isolation.
Redistribution between reservoirs is invisible unless upstream and downstream are
measured together.

---

## Phase 2 — Groundwater subsidence: the same story one layer deeper

**Question:** where is the land sinking in Moroccan agricultural basins, how
fast, and does it track groundwater stress?

**The gap, stated precisely.** Europe has the European Ground Motion Service, a
free continent-wide ground-motion product. Africa has no equivalent. For Morocco
the published InSAR work is a **single irrigated perimeter**: Hajhouji et al.
(2026) measured Sentinel-1 subsidence up to 6.5 mm/yr over Ouled Gaid in the
Tensift catchment, correlating 0.39–0.71 with estimated pumping. Hssaisoune et
al. (2020) report water-table declines of 20–65 m over 30 years across the
Souss, Haouz, Tadla and Saïss plains, but with no deformation measurement.

So the opening is **coverage and reproducibility, not technique**: a multi-basin,
continuous, reproducible deformation product with the code published. The
single-perimeter study is evidence the method works, not a competitor.

**What we will and will not claim.**
- **Will:** millimetre-scale deformation rates and time series per basin; their
  spatial correlation with irrigated extent, pumping proxies and the Phase 1
  reservoir-stress series; the seasonal elastic signal versus irreversible
  compaction.
- **Will not:** volumetric groundwater loss inverted from displacement. That
  requires lithological and aquifer-compressibility data these basins do not
  have, and the literature says so plainly (Castellazzi et al., *RSE* 2017).
  Promising cubic metres would invite a reviewer to take the whole thing apart.

**Approach.** ASF **HyP3** does the interferogram processing, so the engineering
here is job orchestration, retries, cost control and provenance over a remote
processor — a genuinely different problem from Phase 1's chunked-raster work, and
worth having solved. Candidate basins: Saïss (no InSAR published), Tadla and
Haouz (severe declines, inside/adjacent to Oum Er-Rbia), Souss-Massa.

**Deliverable:** a basin-set ground-motion dataset plus the pipeline, framed
explicitly as a first step toward an African EGMS analogue.

---

## Phase 3 — Generalise into an open-source tool

Only after Phases 1 and 2 have exercised the code against three different
problem shapes: multi-temporal optical rasters, a non-STAC HTTP archive
(CHIRPS), and remote job orchestration (HyP3).

**What the three phases will already have proven is needed:**
- Source abstraction that is not STAC-only — forced by CHIRPS and HyP3, since
  Planetary Computer carries neither CHIRPS nor GRACE.
- Radiometric correctness as a first-class concern: per-item offsets from
  metadata, superseded-reprocessing deduplication, float-before-arithmetic.
- Provenance that reproduces a number from its exact inputs.
- Sanity checks that fail loudly, and coverage assertions before aggregation —
  both of which caught real errors in Phase 1.
- Batching sized to credential lifetime, with per-batch failure isolation and
  resume.

**Deliverable:** a documented, tested, installable package for basin-scale water
and deformation accounting from public satellite archives, with Morocco as the
worked example.

---

## What ties the phases together

One region, one question, three measurements: surface water leaves, groundwater
is pumped to replace it, and the land sinks. Phase 1 measures the first, Phase 2
the third, and together they constrain the second — which is the compartment
nobody can observe directly and where the published literature openly
contradicts itself (Ouatiki et al. 2022 versus Ahmed et al. 2021).

That is the argument for doing them in this order, in this place, rather than
building a generic tool and looking for somewhere to point it.
