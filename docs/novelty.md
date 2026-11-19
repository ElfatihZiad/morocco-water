# Novelty assessment

Second-pass literature probe, 2026-11-03: French and Arabic sources, prior-art
tests against each original gap, and a data-feasibility check run directly
against the Planetary Computer STAC API.

**Headline:** four findings reshape the project. Two of the six original gaps are
weaker than claimed, one is unchanged, and three new candidates are stronger than
anything in the first pass. The recommended framing is at the bottom.

---

## 1. Four findings that change the project

### 1.1 Al Massira is no longer a rainfall-driven system — and the clock is running

Morocco is building the **"autoroute de l'eau"** (water highway), an inter-basin
transfer from the water-rich Sebou to the water-short centre.

- **Phase 1 (Sebou → Sidi Mohamed Ben Abdellah / Bouregreg): operational since
  August 2023.** Designed for 350–450 Mm³/yr; reported actual transfers have
  exceeded 560 Mm³/yr, with ~953 Mm³ cumulative cited.
  ([Le Matin](https://lematin.ma/nation/les-etudes-pour-relier-sebou-a-al-massira-finalisees-en-2026/281836),
  [Le360](https://fr.le360.ma/societe/300-km-de-trace-et-800-millions-de-m-par-an-ce-que-represente-le-projet-dinterconnexion-sebou-oum_WPJGYONNL5BCDL26FRALDLGFGQ/))
- **Phase 2 extends 210 km to Al Massira itself**, at a design ~30 m³/s, with
  total system capacity heading toward ~1.2 billion m³/yr. Studies finalise end
  of 2026; works announced to launch in 2026.
  ([TelQuel](https://telquel.ma/2026/03/31/autoroute-de-leau-ce-que-le-cahier-des-charges-revele-de-la-phase-ii-du-projet_1981667),
  [L'Opinion](https://lopinion.ma/fr/actu-maroc/autoroutes-de-leau-sebou-bouregreg-et-oum-er-rbia--les-travaux-lances-des-2026-selon-nizar-baraka-_a72000),
  [Ministry via industries.ma (AR)](https://ar.industries.ma/))

**Why this matters more than anything else here.** The MVP as originally framed —
Al Massira surface area versus CHIRPS rainfall — assumes reservoir storage is a
function of basin hydrology. Once phase 2 is commissioned that assumption breaks:
Al Massira becomes partly an engineered destination for Sebou water, and any
rainfall-to-storage relationship fitted across the transition is fitting two
different systems at once.

This is a **time-limited novelty window**. Nobody has published the satellite
record of Al Massira as a *pre-transfer* reservoir, because until now there was no
reason to label it that way. That record can only be established before the
transfer lands. It is also exactly the kind of structural-break reasoning that is
worth being able to explain in an interview.

**ASSUMPTION to verify:** that phase 2 is not yet delivering water to Al Massira.
Everything found says studies/tendering, and the Arabic ministry coverage says the
second phase is *expected* to be executed. Confirm before claiming a clean
pre-transfer baseline, because if deliveries have begun the window is already
closing.

### 1.2 The 2025–26 recovery is large, real, and completely unpublished

Arabic and French coverage give a consistent trajectory, and it is dramatic:

| Date | Fill | Volume |
|---|---|---|
| ~2022–24 trough | ~1–2% | — |
| Dec 2025 | 3.4% | — |
| Jan 2026 | 11% | — |
| early 2026 | ~34% | ~906 Mm³ |
| 24 Jul 2026 | 41.3% | ~1,094 Mm³ |

Sources: [le360 (FR)](https://fr.le360.ma/societe/de-39-a-413-en-chiffres-voici-comment-le-barrage-al-massira-a-decuple-son-stock-en-un-an_F6EUM2YPIVHKTGD2FFR3KOQSII/),
[Médias24](https://medias24.com/2026/02/14/oum-er-rbia-reprise-nette-des-principaux-barrages-bin-el-ouidane-et-hansali-en-forte-hausse-images-satellites-1628131/),
[nichanealane (AR)](https://www.nichanealane.ma/114587/),
[madar21 (AR)](https://madar21.com/401815.html).
Nationally, dam fill went from ~31% to ~66–68% year over year
([Maa Dialna](https://www.maadialna.ma/), [Hespress EN](https://en.hespress.com/146876-moroccos-dam-reserves-more-than-double-in-one-year-as-water-situation-improves.html)).

**Every peer-reviewed study found stops in 2023 or 2024.** The entire recovery is
unclaimed ground, and it is the most interesting part of the record: a drought
that only declines is one story, a drought that collapses and then partially
recovers lets you ask which parts of the system recovered and which did not.

### 1.3 Landsat is on Planetary Computer — the window is 40 years, not 10

`landsat-c2-l2` is available. Al Massira was commissioned in 1979, so a
Landsat-based area series can cover **essentially the dam's entire operating
life**, including the severe early-1980s and mid-1990s Moroccan droughts.

This converts an assertion into a test. "The worst drought on record" is a claim
every source makes rhetorically; with a 40-year satellite series it becomes a
measurement. It also gives the current drought a baseline distribution to be
unusual *against*, which is the difference between a chart and a finding.

### 1.4 CHIRPS and GRACE are not on Planetary Computer — confirmed, not assumed

I queried the STAC API directly: **139 collections, no CHIRPS, no GRACE.** What
*is* there and matters:

| Collection | Use | Note |
|---|---|---|
| `sentinel-2-l2a` | NDWI, 10 m | 2015/2016– |
| `landsat-c2-l2` | 40-year extension | 1982– for TM onward |
| `sentinel-1-rtc`, `sentinel-1-grd` | radar cross-validation | terrain-corrected; cloud-free |
| `jrc-gsw` | validation baseline | JRC Global Surface Water, monthly history |
| `modis-13Q1-061`, `modis-13A1-061` | NDVI, 250/500 m, 16-day | farmland response |
| `terraclimate` | precip, PDSI, soil moisture, monthly ~4 km | 1958– |
| `era5-pds` | reanalysis precip | cross-check |
| `cop-dem-glo-30`, `nasadem`, `alos-dem` | area→volume geometry | see §3.4 |

**Architectural consequence:** the project needs a second data path regardless, so
the datacube tool should abstract over *sources*, not just assume STAC. That is a
better design brief than "wrap odc-stac", and it is worth saying so in the
decision log. TerraClimate gives a PC-native precipitation and PDSI series to get
moving with while the CHIRPS route is settled.

---

## 2. Prior-art verdict on the original six gaps

| # | Gap | Verdict |
|---|---|---|
| 1 | Optical cross-validation of radar reservoir record | **Downgraded** — partly occupied |
| 2 | Reproducible open pipeline | **Holds** |
| 3 | Sentinel-2 baseline-offset discontinuity | **Holds** — cheap, still unaddressed |
| 4 | InSAR as arbiter of the GRACE contradiction | **Heavily downgraded** |
| 5 | Joint basin-by-basin response | **Strongest; unoccupied** |
| 6 | The 2025–26 recovery | **Wide open and time-sensitive** |

**Gap 1 — downgraded.** Radar-versus-optical water extent is a studied problem.
An IRD Sentinel-1&2 multitemporal paper reports both sensors carry a negative area
bias that *grows as reservoirs approach full*, with optical outperforming radar on
recall; a Sentinel-1 performance analysis puts radar's area discrepancy against
higher-resolution SAR at 15–20%; an Indian small-reservoir study reports ~17% MAPE
on area and ~31% on volume; and there is now an operational Algerian reservoir
monitoring paper with ground validation. The *generic* comparison is done. What
survives is narrower and still real: nobody has characterised the disagreement at
Al Massira **at extreme low stage**, where the lake is shallow, turbid and ringed
by saturated mud — the regime where NDWI and radar backscatter diverge most, and
precisely the 2022–24 period of interest. Keep it as a component, not a headline.

**Gap 4 — heavily downgraded.** Using InSAR to sharpen or arbitrate GRACE is an
established method, not an opening: there is a *Remote Sensing of Environment*
paper on quantitative mapping of groundwater depletion with a combined
GRACE/InSAR approach, a review on the potential and limitations of exactly this
pairing, and a 2026 MENA/GCC regional review proposing an uncertainty-aware
framework. Worse, that literature names the blocker: converting InSAR
displacement into storage loss needs lithological data that is usually
unavailable, and InSAR only works where aquifers deform measurably. Treat
"arbitrate GRACE with InSAR" as a known technique applied to a new place, which
is a modest claim, not a novel method.

**Gap 5 — unchanged and now clearly the best of the six.** The siloing is
confirmed by the second pass: reservoirs (Baba 2025, Sentinel-1), Oum Er-Rbia
multi-index drought (Serbouti 2024, 2002–2022), Doukkala land-use and ETa/NDVI
(2015–2023), Tadla/Tassaout arboriculture drought severity (Geocarto 2025), GRACE
(Ouatiki 2022 vs Ahmed 2021, contradictory), Tensift InSAR (Hajhouji 2026). Every
one is a single compartment over its own window. Nothing joins them.

---

## 3. New novelty candidates, ranked

Scored on novelty × feasibility × how well it survives an interviewer asking
"so what?"

### 3.1 ★ Recovery asymmetry: what came back in 2025–26, and what didn't

**The claim to test:** surface water and groundwater recover on different
timescales, so a wet year repairs the reservoir record while leaving the aquifer
deficit largely intact — and the satellite record can show that per basin.

This is the strongest idea available, and it is a genuine synthesis of gaps 5 and
6 rather than either alone. It is novel because the recovery is unpublished
(§1.2); it is *meaningful* because "the drought is over" is currently being argued
in Moroccan media on the basis of dam fill alone, and dam fill is the fastest-
recovering component of the system. Ouatiki et al. (2022) already warn that wet-year
TWS peaks **mask** ongoing depletion — this is that warning, tested on the biggest
wet year in a decade.

Testable signatures per basin: reservoir area/volume recovery fraction versus
TWS recovery fraction versus NDVI recovery fraction, each normalised against its
own pre-drought baseline. Divergence is the finding.

**Feasibility:** high for reservoirs and NDVI (both PC-native). GRACE needs the
off-PC path and has latency. Partial answers are still publishable-shaped.

### 3.2 ★ The pre-transfer baseline

Establish and document the satellite record of Al Massira as a pre-inter-basin-
transfer reservoir, before phase 2 commissioning (§1.1). Novelty comes from
timing rather than method, which is a legitimate kind — but it depends entirely on
the verification in §1.1, and if transfers have begun it evaporates. Cheap to
check, high value if it holds, and it pairs naturally with 3.1 as the control
you need to attribute recovery to rainfall rather than engineering.

### 3.3 ★ Forty-year drought context

Use Landsat (§1.3) to place 2016–2026 in the full instrumental satellite record.
Converts the universal "unprecedented" claim into a ranked measurement, and gives
every other analysis a baseline. Moderate novelty — Bounif et al. (2023) did
1999–2021 Landsat work on this exact dam, so this is an extension rather than a
new idea, and their paper must be read first to see how much is left. High
feasibility and high leverage on everything else.

### 3.4 Volume rather than area

Area is a proxy; **volume** is the decision-relevant quantity, and nothing found
publishes a satellite volume series for a Moroccan dam. Three routes:

1. **Altimetry + area → volume.** ICESat-2 agrees with gauges to ~14 cm RMSE
   globally; a Yellow River study reports <9% volume-change uncertainty from
   ICESat-2 plus optical area. Sentinel-3 SRAL is the denser-revisit alternative.
2. **Area → level regression.** Demonstrated on 20 Burkina Faso reservoirs from
   Sentinel-2 area series — directly transferable.
3. **DEM / published hypsometry.** Cote–volume and cote–surface curves for Al
   Massira **exist**, from DGH (1990), reproduced as figures in a *Hydroécologie*
   thermal-regime study ([PDF](https://www.hydroecologie.org/articles/hydro/pdf/2000/01/hydro00107.pdf)).
   Digitising a published curve is far cheaper than inverting altimetry.

**Must check first: GloLakes.** It publishes storage dynamics for 27,000 lakes
from 1984 to present using altimetry plus optical imaging, and a 2025 HESS paper
fitted curves for 6,000+ storage structures from it. If Al Massira is in GloLakes,
much of this is already done — **check before investing a single day here.**
([GloLakes, ESSD 2024](https://essd.copernicus.org/articles/16/201/2024/))

### 3.5 Substitution versus contraction (the mechanism question)

When surface water fails, does a basin pump harder (groundwater depletion signal
with *sustained* NDVI) or farm less (NDVI falls with storage)? This is the
mechanism underneath 3.1 and the most intellectually interesting framing in the
project — it is a question about human response, answered with physical data.
The Doukkala lead is promising: a 1998–2020 land-use study reports ~8% of cropland
converting to non-cropland, which would be the contraction signature, though the
attribution in that snippet is unconfirmed. Dependent on groundwater data quality,
so treat as the stretch goal it is.

### 3.6 An open ground-truth archive (low effort, real value)

There is **no public per-dam historical series**. I checked
[Maa Dialna](https://www.maadialna.ma/), the ministry's own platform: it is a
snapshot only — national and per-basin fill, three highlighted dams, PDF and PNG
exports, no CSV, no API, no per-dam history, and Al Massira not even listed. News
figures for overlapping dates disagree with each other.

Two consequences. First, this is *why* a satellite series has value — there is no
convenient alternative. Second, scraping and archiving the daily bulletin from
today onward costs almost nothing and compounds into the validation dataset
nobody has. Start it now; it cannot be backfilled.

---

## 4. Recommended framing

> **Morocco's dams refilled in 2025–26. Did its water system recover?**
>
> A satellite reconstruction of reservoir storage, groundwater and irrigated
> farmland across Morocco's major basins, placing the 2016–2024 drought and the
> 2025–26 recovery in a 40-year context — and distinguishing recovery driven by
> rainfall from recovery delivered by inter-basin transfer.

Why this framing earns the ambition:

- It leads with a question whose answer is **not already known**, and is being
  actively mis-answered in public on dam-fill numbers alone.
- Each component is individually feasible, and the MVP is unchanged — Al Massira
  area from Sentinel-2 NDWI is still step one. Nothing here is wasted work.
- It degrades gracefully. If GRACE proves too coarse or too laggy, the reservoir
  and NDVI halves still answer a real question. Ambition without a cliff.
- The confounds are *stated in the thesis*, which is the difference between an
  ambitious project and an overreaching one.

**Suggested order:** Al Massira Sentinel-2 MVP → extend to Landsat for 40-year
context → add Sentinel-1 for low-stage cross-validation → NDVI → generalise to
basins → groundwater last, where the uncertainty lives.

---

## 5. Verify before relying on any of this

Ordered by how much damage a wrong answer does.

1. **Is autoroute de l'eau phase 2 delivering to Al Massira yet?** Kills or
   confirms 3.2. Primary sources: ABHOER, Ministère de l'Équipement et de l'Eau.
2. **Is Al Massira in GloLakes?** Could pre-empt much of 3.4.
3. **Read Baba et al. (2025) in full.** Check for an optical comparison in the
   supplementary material before claiming anything about gap 1.
4. **Read Bounif et al. (2023) in full** — *J. Ecological Engineering* 24(2),
   340–349. It is Landsat, this dam, and area-versus-retention, so it bounds both
   3.3 and 3.4. A search snippet attributed "mean 72 km², min 23 km², max 128 km²
   (1999–2021)" to a study of this dam, but **I could not confirm those figures in
   the paper** and the only "128" I could verify on the dam is its 128 MW installed
   capacity. Do not reuse those numbers until read.
5. **Settle the maximum-area ceiling** used in the sanity checks — see the
   correction below.
6. **Search French/Arabic academic repositories properly.** This pass covered
   French and Arabic *media* well and found real substance, but not theses. Try
   theses.fr, HAL, IMIST/Toubkal, and Cadi Ayyad / Hassan II / Mohammed V
   repositories for *envasement*, *télédétection*, *Al Massira*. Siltation is a
   live local research topic — a Moulouya study used remote sensing for diachronic
   dam siltation, and reported silt inflow of ~30 Mm³/yr across four large dams
   including El Massira — and **siltation permanently reduces capacity, which means
   the area→volume relationship is not stationary over a 40-year window.** That is
   a methodological problem for 3.3 and 3.4 and was not on the radar before this
   pass.

### Correction to the first-pass review

I previously wrote that the self-published GitHub figure of ~125 km² for Al
Massira "exceeds the reservoir's nominal 80 km² surface area, which suggests a
methodological problem." **That reasoning was not sound.** The 80 km² figure is
Wikipedia's, and nothing establishes it as a *maximum* rather than a typical or
design value; unconfirmed satellite figures put the observed maximum far higher.
The number may still be wrong — ~125 km² is hard to reconcile with a reported
41.3% fill by volume at that date — but the ceiling argument I used does not
support that, and `CLAUDE.md` has been corrected to stop asserting an unverified
~80–100 km² bound.

---

# 6. Blocker verification (2026-11-03, second session)

All six items in §5 were checked. Four verdicts change the plan; the ranked list
in §3 is superseded by §6.8.

## 6.1 Transfer status — CONFIRMED, and reframed

**The Sebou inter-basin transfer does not yet reach Al Massira.** The
interconnection commissioned **28 August 2023** (up to 15 m³/s) feeds **Sidi
Mohamed Ben Abdellah** (Bouregreg), which supplies Casablanca — Le360 states it
"a joué un rôle important dans le maintien du niveau de SMBA", which "aurait été
complètement à sec en décembre dernier" without it. Phase 2 to Al Massira remains
studies and tendering, with works announced for 2026 and completion targets
ranging 2026–2030 across sources.

**But Al Massira is already a heavily managed reservoir, in both directions:**

- **Inflow — intra-basin transfers.** ~**690 Mm³ was moved into Al Massira
  between September 2025 and July 2026** from upstream works in the Oum Er-Rbia
  basin ("depuis les ouvrages situés en amont"), explicitly to rebalance the
  upper and lower basin ([Le Brief](https://www.lebrief.ma/barrages-des-reserves-deau-nettement-renforcees-malgre-la-canicule-100164928/)).
  Over the same window Al Massira rose from 105 Mm³ (4%) to 1,089 Mm³ (41.1%) —
  a gain of ~984 Mm³. **So the majority of the "rainfall recovery" may be
  redistribution from upstream reservoirs.**
- **Outflow — the Marrakech transfer.** The dam wall was **perforated** (a 2.5 m
  diameter conduit, an African first per the AfDB) to feed a ~125 km pipeline with
  three pumping stations at ~**7 m³/s** toward Marrakech, under a €150M AfDB
  programme. The AfDB completion report describes the raw-water pipeline as
  *partially* commissioned, and notes the original intake **went out of service
  when the reservoir level fell**, requiring alternatives.

**Numbers do not reconcile.** Le Brief gives 690 Mm³ transferred in; Le360 gives
Al Massira inflows of 505 Mm³ since September 2025 alongside 519 mm of basin
rainfall (64% above normal). These are not consistent, and the discrepancy is
itself worth resolving — it is the difference between a rainfall story and an
engineering story.

**Verdict:** §3.2 ("pre-transfer baseline") is **dead in its naive form** — Al
Massira has not been an unmanaged, rainfall-driven reservoir for years. It is
replaced by something better: a *managed-reservoir attribution problem*. See
§6.8.

## 6.2 GloLakes — VERIFIED ABSENT

Checked against the dataset, not the paper. GloLakes v1.1 is served over THREDDS/
OPeNDAP at NCI; I read the metadata arrays directly:

- `Global_Lake_Absolute_Storage_LandsatPlusICESat2_(1984-present).nc` — **22,232
  lakes**, 514 monthly steps since 1984-01-01, units MCM.
- `Global_Lake_Absolute_Storage_LandsatPlusGREALM_(1984-present).nc` — **135
  lakes**.

Al Massira is at **32.47528°N, 7.63750°W** (Wikipedia). Results:

| Product | Moroccan entries | Nearest to Al Massira |
|---|---|---|
| Landsat+ICESat-2 | 15 | **102 km** (`hylak_id=175486`, "Lac des Ait-Aadel") |
| Landsat+GREALM | 1 | 366 km |

**Al Massira is not in GloLakes.** The volume angle is not pre-empted.

**Bonus finding that matters more.** GloLakes *does* cover five reservoirs in the
Oum Er-Rbia region — including `hylak_id=15136` at (32.106, −6.463), consistent
with Bin El Ouidane, and `hylak_id=175448` at (31.815, −6.822), consistent with
Ahmed El Hansali. So the **upstream cascade has independent published storage
series while the key downstream reservoir does not.** That asymmetry is exactly
what makes §6.8 feasible: free validation upstream, original work downstream.

Reproduce with:
```bash
curl -s "https://thredds.nci.org.au/thredds/dodsC/ub8/global/GloLakes/GloLakes_v1.1/Global_Lake_Absolute_Storage_LandsatPlusICESat2_(1984-present).nc.ascii?latitude,longitude,country_name,lake_name,ID"
```

## 6.3 Baba et al. (2025) — VERIFIED, no optical comparison

Read in full. **Sentinel-1 only** for water detection. Sentinel-2 appears solely
as a cloud statistic ("35% to 50% of Sentinel-2 images covering Morocco have a
cloud presence") justifying radar, and as a figure background. Landsat, NDWI and
MNDWI are not used. Validation is **manually digitised Pleiades** (2.8 m)
boundaries over nine regions. Method: σ⁰ preprocessing (thermal noise removal,
calibration, Lee filter, Copernicus DEM terrain correction, 20 m grid), then
three classifiers compared — fixed threshold at **σ⁰ = −18.34**, SVM, and Random
Forest; **Random Forest selected, κ ≥ 0.95**. No supplementary optical comparison
is mentioned. Reported period is internally inconsistent (abstract 2018–2024,
results July 2018–January 2024, Fig. 3 caption April 2018–June 2024).

**Verdict:** the narrow version of gap 1 survives — an independent *optical*
series for Al Massira, cross-compared at extreme low stage, is genuinely not in
this paper.

## 6.4 Bounif et al. (2023) — READ IN FULL; this is the key prior work

*J. Ecological Engineering* 24(2), 340–349. Open access
([PDF](https://www.jeeng.net/pdf-156666-84220)). Far more consequential than the
abstract suggested.

**Method:** Landsat 4/5 TM, 7 ETM+ and 8 OLI via **Google Earth Engine**,
harmonised with Roy et al. (2016) OLS coefficients, CFMask cloud masking via
`pixel_qa`. Water extracted by **combined indices with fixed thresholds: MNDWI ≥ 0,
NDWI ≥ 0, NDVI ≤ 0, AWEI ≥ 0.** Crucially, **one image per year from August–
September, 1999–2021** — an annual dry-season snapshot, not a dense series.

**Results (these are the confirmed figures):**

| Quantity | Value |
|---|---|
| Lake area, mean 1999–2021 | **72 km²** |
| Lake area, minimum | **23 km²** |
| Lake area, maximum | **128 km²** |
| Area CV | 42% |
| Area reduction 2015→2021 | **−73%** |
| In-situ volume range | **264–2,616 Mm³** |
| In-situ volume mean | 1,145 Mm³ (CV 73%) |
| Area↔volume correlation | **r = 0.97** |
| Best model | 2nd-degree polynomial: **R² = 0.98, RMSE = 117.52 Mm³, ME = 2.86** |

**The 82-year inflow record.** The paper also reports Oum Er-Rbia inflows to the
dam from crop year **1938–39 onward**: mean 2.05 billion m³, CV 64%, max 7.25 bn
(1962–63), min **0.012 bn (2013–14)**. It identifies a **regime shift around
1980** — 1939–1980 averaged 3.2 bn m³, 1980–2020 averaged 0.8 bn m³. Monthly
inflows range 76–335 Mm³, peaking in May, with 71% arriving February–June.

**Implications:**
- §3.3 (40-year context) is **weakened** — 1999–2021 Landsat on this dam is done,
  and a far longer *inflow* record already exists. What remains: **monthly rather
  than annual** resolution, the 1984–1999 extension, and 2021→present.
- §3.4 route 2 is **solved for us**: a validated area→volume polynomial already
  exists at R² = 0.98. Don't rebuild it — cite it, re-fit it on monthly data, and
  check whether it still holds at the extreme low stage Bounif never observed.
- The coefficients came out **scrambled by PDF text extraction** (three numbers,
  ambiguous ordering). A quick dimensional check implies the quadratic term is the
  0.1205 one, since that is what reproduces ~2,616 Mm³ at 128 km² — but **that is
  my inference, not the paper's statement.** Read Table 4 / Figure 8 from the PDF
  before using the equation.

## 6.5 Maximum-area ceiling — RESOLVED

**128 km²** is the observed maximum (Bounif et al., Landsat, 1999–2021).
Wikipedia's 80 km² is a nominal figure, not a maximum. `CLAUDE.md` now uses 128 km²
as the sanity-check ceiling with a 10% tolerance, and the self-published ~125 km²
figure is **within the observed envelope** — my first-pass dismissal of it was
wrong on the facts as well as the reasoning.

## 6.6 French/Arabic repositories — SEARCHED, nothing hidden

Queried the HAL API and theses.fr API directly.

- **HAL, "Al Massira":** 3 results — Hanadé Houmma et al. (2026), Baba et al.
  (2025), and an unrelated tilapia genetics paper.
- **HAL, `envasement barrage Maroc télédétection`:** 1 result — a 2014 book
  chapter on Moulouya basin morphology and siltation (El Hannani, Taïbi,
  Boumeaza).
- **HAL,** `"Oum Er-Rbia" télédétection barrage` **and** `barrage Maroc sécheresse
  télédétection retenue`**: 0 results.**
- **theses.fr:** no relevant theses for Al Massira, *envasement barrage Maroc*, or
  *barrage Maroc télédétection*.

**Verdict:** no hidden French thesis occupies our gaps. But the search surfaced
two papers that do matter — §6.7.

## 6.7 Two papers found during verification

**Seasonal forecasting of dam water resources using optimized hybrid models under
unprecedented drought conditions** — Ismaguil Hanadé Houmma, Abdessamad Hadri,
Abdelghani Boudhar, El Mahdi El Khalki, Ismail Karaoui, Sabir Oussaoui, Mohamed
Samih, Christophe Kinnard — *Journal of Hydrology: Regional Studies*, 2026 —
[10.1016/j.ejrh.2025.103091](https://doi.org/10.1016/j.ejrh.2025.103091) ·
[HAL open access](https://hal.science/hal-05642023v1)

**This is an active 2026 paper on Al Massira specifically.** It forecasts monthly
reservoir **volume** 1–6 months ahead using explainable AI (ProbLSTM, GAM,
LightGBM) with Optuna tuning, driven by teleconnection indices, drought indices
and hydroclimatic variables. Best skill 86.2% (ProbLSTM, NMAE 3.6%); **MAE 17.7
Mm³**. It frames the drought as beginning in 2019.

Consequences: (a) the "nobody is working on Al Massira" framing is **dead** —
there is a current, well-resourced Moroccan group on this dam; (b) they have an
**in-situ monthly volume series**, so ground truth exists and is obtainable;
(c) they use **no satellite surface area at all**, so our contribution stays
distinct and is directly complementary — a satellite-derived volume series is a
new predictor and an independent check on their target variable.

**El Orfi T., El Ghachi M., Lebaut S. (2020)** — remote sensing for the
diachronic study of the Ahmed El Hansali dam. Reported **MNDWI-derived volumes
versus ABHOER in-situ at R² = 0.90**. Located only via citation in Bounif et al.;
**full text not retrieved and metadata unconfirmed.** Relevant because it is the
same method on the upstream cascade reservoir, and it confirms ABHOER in-situ
volumes are available to researchers.

## 6.8 Revised recommendation: the cascade water budget

Verification killed the pre-transfer idea and weakened the 40-year one, but it
handed over something stronger and more specific.

> **Where did Al Massira's water come from?**
>
> A satellite reconstruction of monthly storage across the **whole Oum Er-Rbia
> reservoir cascade**, used to separate the 2025–26 recovery into rainfall-driven
> net basin gain versus redistribution from upstream reservoirs — and to test
> whether groundwater and farmland recovered at all.

Why this is the best available framing:

1. **It is a real, unanswered, quantitative question.** ~690 Mm³ reportedly moved
   into Al Massira from upstream while the dam gained ~984 Mm³. Two published
   figures disagree (690 vs 505 Mm³). The public narrative is "the rains came."
   Nobody has closed this budget.
2. **Single-reservoir studies structurally cannot answer it.** Baba et al. covered
   many Moroccan reservoirs but computed no cascade budget; Bounif and Hanadé
   Houmma both treat Al Massira in isolation. Redistribution is invisible unless
   you monitor upstream and downstream *simultaneously* — which is precisely what
   a datacube tool over a STAC catalogue is good at. **The engineering and the
   science motivate each other**, which is the best possible position for an
   interview project.
3. **Validation is nearly free.** GloLakes covers the upstream cascade (§6.2) but
   not Al Massira; Bounif gives a validated area→volume curve and 1999–2021 areas;
   Hanadé Houmma's group holds in-situ monthly volumes; ABHOER data is evidently
   obtainable. Each piece independently checks a different part of the pipeline.
4. **It degrades gracefully.** Reservoir cascade alone is a complete result.
   NDVI adds the farmland response. Groundwater is the stretch, where the
   uncertainty lives.
5. **The confounds are the subject, not a caveat** — intra-basin transfers in, the
   Marrakech pipeline out, siltation shifting the area-volume curve over time.

**Retained from §3:** recovery asymmetry (3.1) as the second half of the question;
the baseline-offset demonstration (gap 3, still unaddressed anywhere);
low-stage radar-versus-optical comparison (narrowed gap 1); the ground-truth
archive (3.6, start scraping now — it cannot be backfilled).

**Dropped:** pre-transfer baseline (3.2, dead); naive 40-year novelty claim
(3.3, mostly done by Bounif); InSAR-arbitrates-GRACE as a headline (gap 4,
crowded).

**Order of work unchanged for the MVP:** Al Massira Sentinel-2 NDWI monthly series
is still step one. It is now step one of a bigger and better-defended question.

## 6.9 Still unverified

- **Bounif's polynomial coefficients** — read Table 4 / Figure 8 from the PDF.
- **El Orfi et al. (2020)** — full text and metadata.
- **Hanadé Houmma et al. (2026)** — read in full; confirm the in-situ volume
  source and period, and whether they publish the series.
- **The 690 vs 505 Mm³ discrepancy** — needs ABHOER or ministry primary data.
- **Marrakech pipeline commissioning date and actual delivered volumes** — the
  AfDB completion report is the lead; the AfDB news page blocked automated access.
- **Which upstream dams supplied the 690 Mm³**, and whether "ouvrages en amont"
  means reservoir releases, the Rocade canal, or both.
