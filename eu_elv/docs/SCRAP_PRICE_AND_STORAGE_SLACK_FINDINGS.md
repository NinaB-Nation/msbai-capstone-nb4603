# Scrap Price Series and Storage Slack Proxies — Source Findings

**Project:** NYU Stern MSBAi Capstone, "The Global ELV Recycling Gap"
**GCP project:** `msbai-capstone-nb4603`
**Date:** 2026-09-19
**Status:** Findings only. No pipeline built. Awaiting source approval.

---

## 0. Summary

**Task 1.** The benchmark you preferred — steel scrap CFR Turkey — has no free,
reproducible series. Every publisher of it is a paid subscription. Of the free
options, two are worth using and they are complements, not substitutes:
Eurostat Comext HS 7204 (country-year joinable, but a derived unit value) and
the US BLS producer price index for scrap via FRED (a true price, but a single
series with no country dimension).

**My recommendation is Comext as primary, built as a single EU-aggregate series
rather than country-specific, with FRED as an independent cross-check.** The
reasoning for "EU-aggregate, not country-specific" is in §2.2 and it is a
design point about your identification strategy, not a convenience.

**Task 2(a).** Dataset codes confirmed. There is a structural break at 2021
that forces two datasets to span 2005–2023, and there is a real risk that the
4-digit NACE 38.31 class is suppressed for exactly the countries your
hypothesis cares about. A pull was in flight at the time of writing.

**Task 2(b).** **Not harmonised.** ATF counts and permitted storage volumes do
not exist in any EU-level source. Per your instruction I have not assembled a
partial version. The nearest harmonised dataset measures something different
and I explain why in §4.

---

## 1. Task 1 — Options for a scrap price series

All coverage, licence and access facts below were checked against live sources
on 2026-09-19, not recalled.

| # | Source | Coverage | Frequency | Licence | Access method | True price or unit value? |
|---|--------|----------|-----------|---------|---------------|---------------------------|
| 1 | **Steel scrap HMS 1&2 80:20 CFR Turkey** (Platts / Fastmarkets / Kallanish / CME / Barchart) | back to ~1980 | daily–weekly assessments | **Commercial subscription only** | Paid terminal / API | True price (physical assessment) |
| 2 | **FRED `WPU10121191`** — PPI, Heavy Melting Scrap | Jun 1996 → present | Monthly | US public domain (BLS) | Keyless CSV | **True price**, but an *index*, US market |
| 3 | **FRED `WPU1012`** — PPI, Iron and Steel Scrap | long history → present | Monthly | US public domain (BLS) | Keyless CSV | **True price**, index, US market |
| 4 | **UN Comtrade HS 7204** | 1988 → present | Monthly / annual | Free tier, limited; bulk needs key | REST API **requires key** | Derived unit value |
| 5 | **Eurostat Comext `DS-045409` HS 7204** | **1988 → present** | **Monthly** | Eurostat open data (free reuse, attribution) | **SDMX-CSV, no key** | Derived unit value |
| 6 | **Eurostat `ENV_WASTRDMP`** — trade in waste by material and partner | see note | Annual | Eurostat open data | SDMX-CSV, no key | Derived unit value |
| 7 | DBnomics | wraps 2–5 | varies | Free, no key | REST API | Passthrough |

### 1.1 Why option 1 is out

CFR Turkey HMS 80:20 is published by S&P Global Platts, Fastmarkets and
Kallanish, traded as a CME swap, and redistributed by Barchart. Historical
series access is subscription-gated at every one of them (Barchart requires
Premier membership for historical download). There is no free reproducible
version. This fails your "free and reproducible" constraint outright, so I did
not pursue a workaround.

This matters beyond licensing: CFR Turkey is the price that actually clears the
European scrap export market, so losing it is a genuine loss of precision, not
a formality. Options 2/3 are the closest free stand-in because US HMS and
Turkish import HMS are the same grade in a globally arbitraged market.

### 1.2 Why option 4 is out

UN Comtrade's bulk endpoint requires a subscription key. Storing one would
violate your no-plaintext-credentials rule, and you already chose Route B over
it. Not pursued.

### 1.3 Option 5 — verified working end to end today

This is the one I actually tested against the live API, from inside the Cloud
Run job. Three things were established that are not documented anywhere I could
find, and all three change how the pull must be built:

**(a) Comext is on a different API base from the rest of Eurostat.** The main
dissemination endpoint carries 8,151 dataflows and `DS-045409` is not among
them — it returns `ERR_NOT_FOUND_4`. Comext is served from its own base, which
carries 11 dataflows:

```
https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1
  agency = ESTAT   id = DS-045409   version = 1.0
  "EU trade since 1988 by HS2-4-6 and CN8"
```

**(b) The dimension key, read off the DSD rather than guessed:**

```
freq . reporter . partner . product . flow . indicators
 M   .          .         .  7204   .  2   .
```

`flow` is enumerated `1 = IMPORT`, `2 = EXPORT`, `3 = RE-EXPORT`, confirmed
from codelist `CXT_EU_FLUX`. `freq` supports `M` monthly (codelist `CXT_FREQ`),
so monthly-preferred-with-annual-aggregate is satisfiable.

**(c) Quantity is in 100 kg, not kg or tonnes.** The data returns indicator
codes `QUANTITY_IN_100KG` and `VALUE_IN_EUROS`. So:

```
unit value (EUR/tonne) = VALUE_IN_EUROS / (QUANTITY_IN_100KG × 100) × 1000
```

Getting this wrong would silently scale the whole series by 10×.

Working request and its actual response:

```
GET .../data/DS-045409/M...7204.2.?format=SDMX-CSV&compressed=false
    &startPeriod=2023-01&endPeriod=2023-12
→ 200, application/vnd.sdmx.data+csv

DATAFLOW,LAST UPDATE,freq,reporter,partner,product,flow,indicators,TIME_PERIOD,OBS_VALUE
ESTAT:DS-045409(1.0),15/09/26,M,AT,AE,7204,2,QUANTITY_IN_100KG,2023-09,1772.90
ESTAT:DS-045409(1.0),15/09/26,M,AT,AE,7204,2,VALUE_IN_EUROS,  2023-09,204548
```

**(d) Unfiltered pulls are refused.** Both a no-time-window request and a
query-parameter-style request return `413 EXTRACTION_TOO_BIG`. The pull must be
chunked — one request per year, 19 requests for 2005–2023.

---

## 2. Task 1 — Recommendation

### 2.1 What I recommend

| Role | Series | Why |
|------|--------|-----|
| **Primary** | Comext `DS-045409`, HS 7204, flow = EXPORT, **aggregated to a single EU-wide EUR/tonne series**, monthly + annual mean | Free, no key, verified working, covers 2005–2023 monthly, and it is the European market |
| **Cross-check** | FRED `WPU10121191` (Heavy Melting Scrap), monthly | Independent, a *true price* rather than a unit value, same grade basis as CFR Turkey |

If the two move together, the unit value is behaving like a price and the
primary series is credible. If they diverge, that divergence is itself
diagnostic and needs explaining before the series is used.

### 2.2 Why EU-aggregate and not country-specific — please read this one

Your mechanism is that operators hold hulks back when scrap prices are poor and
release them when prices recover. If that is true, then a country's **own**
export unit value is partly an *outcome* of the behaviour you are trying to
explain: the timing and grade mix of what it ships is exactly what the
stockpiling decision changes. Regressing reported recycling rates on own-country
unit values therefore puts a consequence of the dependent variable on the
right-hand side.

A common price series avoids that. And you already identified why this costs
nothing — **"identification comes from price interacted with exposure, not from
price alone."** A common price has no country variation by construction, so all
the cross-sectional variation has to come from the exposure term. That is the
Task 2 proxies, which is where you want it. The aggregate series is the
*correct* specification here, not a compromise forced by data limits.

If you want country-level price variation despite this, the defensible version
is a **leave-one-out** construction: for country *i*, use the EU unit value
computed excluding *i*'s own trade. Say the word and I will build that instead —
it is the same pull, different aggregation in silver.

### 2.3 Caveats I am not going to bury

- **A unit value is not a price.** It is value divided by mass, so it moves with
  grade mix and destination mix as well as with price. A shift toward
  higher-grade scrap raises it with no price change.
- **HS 7204 is all ferrous waste and scrap**, not ELV-specific. Vehicle hulks
  are a subset. If you want to narrow, the 6-digit subheadings are available in
  the same dataset at the same cost — `7204.21` (stainless), `7204.49` (other),
  etc. Worth deciding before the pull.
- **FRED is a US index**, base 1982 = 100. It is a level-free index, so it can
  only be used in changes/logs, not in EUR/tonne terms.
- **Both FRED and Eurostat are blocked from the dev sandbox.** Verified again
  today: `fred.stlouisfed.org` returns `connect_rejected` from here. Every fetch
  has to run inside the Cloud Run job. This is a workflow constraint, not a
  blocker.

---

## 3. Task 2(a) — Operator concentration via SBS, NACE 38.31

Confirmed against the live catalogue of all 8,151 Eurostat dataflows.

| Dataset | Title | Coverage | Note |
|---------|-------|----------|------|
| **`SBS_NA_IND_R2`** | Annual detailed enterprise statistics for industry (NACE Rev. 2, B–E) | **2005–2020** | NACE 38.31 sits in Section E. The pre-2021 series. |
| **`SBS_OVW_ACT`** | Enterprises by detailed NACE Rev. 2 activity and special aggregates | **2021 onwards** | Post-restructure successor |
| **`SBS_SC_OVW`** | Enterprise statistics by size class and NACE Rev. 2 activity | **2021 onwards** | Size-class breakdown — the better concentration proxy |
| `SBS_R_NUTS2021` | Enterprises by NUTS 2 region and NACE Rev. 2 activity | 2021 onwards | Regional |
| `SBS_R_NUTS06_R2` | SBS data by NUTS 2 region and NACE Rev. 2 | 2008–2020 | Regional, pre-break |

### The 2021 break is a real problem, not a formality

Regulation (EU) 2019/2152 (EBS) restructured SBS at reference year 2021. The
old `SBS_NA_*` family stops at 2020 and the new `SBS_OVW_*` family starts at
2021. **Covering 2005–2023 requires stitching two datasets across a definitional
break**, and the variable definitions, population scope and rounding are not
guaranteed comparable across it. Any level shift at 2021 must be assumed to be
an artefact until shown otherwise — which means a break test, and probably a
year fixed effect that absorbs it.

Your three requested variables — enterprises, turnover, employment — are
standard SBS indicators and available in both families.

### The suppression risk, which is the thing to worry about

4-digit NACE classes are routinely suppressed for statistical confidentiality
when a country has few enterprises in them. **That is precisely the
high-concentration case your hypothesis is about.** The countries where "a
handful of operators control dismantling" is true are the countries most likely
to have 38.31 blanked. If that happens, the missingness is informative and
non-random, and dropping those rows biases the exposure measure toward
competitive markets.

A pull of `SBS_NA_IND_R2` was in flight when this was written. **Country
coverage at 38.31 is therefore confirmed as a dataset code but not yet as
populated data.** That is one run away and needs no new code.

---

## 4. Task 2(b) — Permitted storage capacity

### Plainly: this is not harmonised. It does not exist at EU level.

You asked me to say so plainly rather than assemble a partial version, so:
**there is no harmonised EU source for Authorised Treatment Facility counts or
permitted storage volumes.**

How I checked, so you can judge the claim: I searched the complete catalogue of
all 8,151 Eurostat dataflows for facility, permit, licence, authorisation and
capacity terms. The permit/licence matches are residential building permits,
licensed physicians, and migration residence permits. Nothing on waste treatment
authorisation. The only ELV datasets in the entire catalogue are `ENV_WASELV`
and `ENV_WASELVT` — both already in this project — plus `CEI_SRM010`
(end-of-life recycling input rate).

ATF permitting is done by national and regional competent authorities under the
ELV Directive, and the registers stay there. They are not reported up to
Eurostat in harmonised form.

### The nearest harmonised dataset, and why it is not an answer

`ENV_WASFAC` — *Number and capacity of recovery and disposal facilities by NUTS
2 region*. I loaded it to bronze today to check rather than assume: **41,641
rows**.

| `indic_env` | Rows | Years | Distinct geo | OBS_VALUE null % |
|-------------|------|-------|--------------|------------------|
| `FAC` — number of facilities | 24,997 | 2004–2022 | 587 | 1.4% |
| `CAP` — capacity | 10,410 | 2004–2022 | 585 | 6.8% |
| `CAP_RST` — capacity (restricted) | 5,321 | 2004–2022 | 548 | 3.1% |
| `FAC_CL` | 913 | 2010–2022 | 90 | 0.2% |

Geographic granularity: **34 country-level codes** (4,472 rows), 136 NUTS-1,
416 NUTS-2. So it *is* country-year joinable.

**But it measures the wrong thing.** The `wst_oper` dimension contains only:

```
RCV_E      energy recovery        DSP_I      incineration
RCV_R      recycling              DSP_L      landfill
RCV_B      backfilling            DSP_LH     landfill, hazardous
RCV_R_B    recycling+backfilling  DSP_LNH    landfill, non-hazardous
DSP_OTH    other disposal         DSP_LIN    landfill, inert
DSP_L_OTH  other landfill
```

There is **no storage operation and no dismantling or ATF category**. Its
"capacity" is treatment throughput — how much a plant can process — not
permitted space to hold vehicles awaiting processing. Those are different
quantities, and for your mechanism the difference is the whole point: a
dismantler's ability to *wait* is about yard space and permit limits, not about
shredder throughput. Coverage also ends in 2022.

Using it as a storage-slack proxy would be assembling exactly the partial
version you told me not to assemble.

### If you want a storage-slack proxy anyway

Three honest options, in descending order of defensibility:

1. **SBS 38.31 enterprise and size-class counts** (§3) — concentration as a
   proxy for slack, subject to the suppression risk.
2. **`ENV_WASFAC` `FAC` counts** as a crude waste-infrastructure density
   control — defensible as a *control*, not as the exposure variable.
3. **National ATF registers, country by country** — genuinely measures the
   right thing, but not harmonised, definitions differ per member state, and it
   is a large manual effort with no guarantee of a consistent panel.

---

## 5. Source links

- Eurostat Comext SDMX API base — `https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1`
- Eurostat `DS-045409` — EU trade since 1988 by HS2-4-6 and CN8
- Eurostat `ENV_WASFAC` — https://ec.europa.eu/eurostat/databrowser/view/env_wasfac
- Eurostat `SBS_NA_IND_R2` — https://ec.europa.eu/eurostat/databrowser/view/sbs_na_ind_r2
- Eurostat `SBS_OVW_ACT` — https://ec.europa.eu/eurostat/databrowser/view/sbs_ovw_act
- FRED `WPU10121191` (Heavy Melting Scrap) — https://fred.stlouisfed.org/series/WPU10121191
- FRED `WPU1012` (Iron and Steel Scrap) — https://fred.stlouisfed.org/series/WPU1012
- Fastmarkets scrap HMS 1&2 80:20 cfr Turkey — https://www.fastmarkets.com/commodity-prices/steel-scrap-hms-1-and-2-8020-mix-us-origin-cfr-turkey-dollar-tonne-mb-ste-0417/
- CME HMS 80/20 CFR Turkey (Platts TSI) swap — https://www.cmegroup.com/markets/metals/ferrous/hms-80-20-ferrous-scrap-cfr-turkey-platts-swap.html
- Kallanish HMS 1&2 80:20 Turkey CFR — https://www.kallanish.com/en/prices/details/Scrap-price-turkey-cfr/

---

## 6. What I need from you before building anything

1. **Comext pull — go or no-go**, and if go: EU-aggregate (my recommendation)
   or leave-one-out by country.
2. **HS granularity** — stay at 4-digit `7204`, or narrow to 6-digit
   subheadings.
3. **FRED cross-check** — add it or skip it. It needs no key, but it is a second
   fetch path in the job.

Nothing is built yet. The only things loaded this session are `ENV_WASFAC`
(41,641 rows) and a `SBS_NA_IND_R2` pull that was still running, both landed in
bronze unchanged with source URI and load timestamp.
