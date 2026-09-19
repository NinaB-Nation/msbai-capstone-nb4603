# Belgium ELV Material Value Analysis

**Project:** NYU Stern MSBAi Capstone, "The Global ELV Recycling Gap"
**GCP project:** `msbai-capstone-nb4603`, dataset `elv_bronze`
**Eurostat vintage:** 28 April 2026 (no repull; all figures from the validated path)
**Analysis date:** 19 September 2026
**Comparator:** Netherlands method, mirrored for direct comparability

**Labelling convention used throughout.** Every number is tagged:

- **[DATA]** measured in `elv_bronze`, traceable to a table, year and code
- **[DERIVED]** computed from [DATA] with the arithmetic shown
- **[SOURCED]** external input with a citation and date
- **[OPEN]** required but not obtainable; deliberately left unfilled
- **[ASSUMPTION]** your assumption or mine, carried forward explicitly

---

## 0. The headline, stated before the detail

Three of the things this analysis was asked to produce **cannot be produced
from Eurostat ELV statistics**, and that is a finding rather than a caveat:

1. **Copper cannot be separated from aluminium.** Eurostat reports one
   combined code, `W191002` "Non-ferrous materials (aluminium, copper, zinc,
   lead, etc.)". There is no split.
2. **PGM content is not reported.** `W1608` "Catalysts" is reported as a
   gross mass (93 tonnes in 2023). Platinum, palladium and rhodium content
   within it does not exist as a statistic.
3. **Electronics and semiconductors have no category at all.** There is no
   code for them anywhere in the ELV waste codelist.

And the fourth, which is the important one for your Antwerp question:

4. **Belgium's `EXP` code is not used-vehicle exports.** It is "End-of-life
   vehicles exported", reported in **tonnes of waste**, not in vehicle
   counts. The Netherlands figure of 237,875 is a **count of vehicles**. The
   two are not the same measurement and a ratio built from them is not a
   like-for-like comparison. Detail in section 4.

---

## 1. Belgium rows: counts and coverage

**[DATA]** Queried `geo = 'BE'`, all years, both tables.

| Table | Rows (BE) | Year range | Distinct years | Null `OBS_VALUE` |
|---|---|---|---|---|
| `env_waselvt_api` | 144 | 2006 to 2023 | 18 | 0 |
| `env_waselv_api` | 1,375 | 2006 to 2023 | 18 | 0 |

**Note:** Belgium's series begins at **2006**, not 2005. If the Netherlands
run used 2005 as the start year, the panels are one year offset.

### 1.1 Category codes, resolved against the Eurostat codelist

**[DATA]** All 17 codes present for Belgium resolve. **None unresolved.**

| Code | Label | Note |
|---|---|---|
| `ELV` | Waste arising only from end-of-life vehicles of type passenger cars (M1), light commercial (N1) | Top-level total |
| `EXP` | **End-of-life vehicles exported** | **Tonnes, not counts** |
| `DMDP` | Waste from dismantling and de-pollution of end-of-life vehicles | Branch total |
| `W1910` | Waste arising from shredding of end-of-life vehicles | Branch total |
| `W191001` | Ferrous scrap (steel) from shredding | |
| `W191002` | **Non-ferrous materials (aluminium, copper, zinc, lead, etc.)** | **Combined, not split** |
| `W1910A` | Shredder Light Fraction (SLF) (LoW: 191003+191004) | |
| `W1910B` | Other materials arising from shredding (LoW: 191005+191006) | |
| `W1601B` | End-of-life vehicles: metal components (LoW: 160117+160118) | Ferrous/non-ferrous mix, unresolved |
| `W1601C` | End-of-life vehicles: other materials arising from dismantling | Residual, see 3.3 |
| `W1608` | Catalysts | Gross mass only |
| `W1606` | Batteries and accumulators | |
| `W160103` | End-of-life vehicles: tyres | British spelling in Eurostat's own label; means tires |
| `W160107` | End-of-life vehicles: oil filters | |
| `W160119` | End-of-life vehicles: large plastic parts | |
| `W160120` | End-of-life vehicles: glass | |
| `LIQ` | Liquids (excluding fuel) | |

Operation codes, all resolved: `GEN` waste generated, `REU` reuse, `RCY`
recycling, `RCV` recovery, `RCV_E` energy recovery (R1), `DSP` disposal.

---

## 2. The Belgium denominator

### 2.1 Units, stated explicitly

**[DATA]** Belgium reports in three units, and the unit matters:

| Unit | Label | Rows (BE) | What carries it |
|---|---|---|---|
| `T` | Tonne | 1,465 | Every material category, and `EXP` |
| `NR` | Number | 18 | `GEN` only, in `env_waselvt_api` |
| `PC` | Percentage | 36 | The reported rate series |

**There is exactly one count series for Belgium: `GEN` in `NR`.** Everything
else, including exports, is mass.

### 2.2 ELVs generated, counts and tonnes

**[DATA]** `env_waselvt_api`, `geo='BE'`, `wst_oper='GEN'`:

| Year | Generated (NR, vehicles) | Generated (T, tonnes) | Implied t/vehicle **[DERIVED]** |
|---|---|---|---|
| 2010 | 170,562 | 176,446 | 1.034 |
| 2015 | 107,425 | 119,054 | 1.108 |
| 2019 | 134,629 | 168,810 | 1.254 |
| 2020 | 110,161 | 138,468 | 1.257 |
| 2021 | 103,659 | 129,979 | 1.254 |
| 2022 | 81,350 | 102,334 | 1.258 |
| **2023** | **63,592** | **80,190** | **1.261** |

**[DERIVED] The count-to-tonne conversion factor is 1.261 t/vehicle (2023),
computed as 80,190 / 63,592.** This is derived from Belgium's own reported
data, not imported from an external source, which makes it the defensible
factor to use for this country. It has drifted upward from 1.034 in 2010,
consistent with vehicles getting heavier, and is stable at about 1.25 to 1.26
across 2019 to 2023.

**[DATA] Belgium's ELV intake has fallen 63 percent from its 2010 peak**
(170,562 to 63,592 vehicles). This is the same collapse pattern the capstone
has documented elsewhere and is not explained within this dataset.

### 2.3 Treated against generated, and the divergence

**[DATA]** `env_waselvt_api`, unit `T`:

| Year | GEN (t) | REU (t) | RCY (t) | RCV (t) | RCV_E (t) | DSP (t) |
|---|---|---|---|---|---|---|
| 2019 | 168,810 | not reported | 112,802 | 119,888 | not reported | not reported |
| 2020 | 138,468 | not reported | 100,412 | 106,373 | not reported | not reported |
| 2021 | 129,979 | not reported | 95,215 | 100,159 | not reported | not reported |
| 2022 | 102,334 | not reported | 73,782 | 78,110 | not reported | not reported |
| 2023 | 80,190 | not reported | 56,651 | 60,014 | not reported | not reported |

**[DATA] Divergence, 2023.** Generated 80,190 t. Recovery 60,014 t. The gap
is **20,176 tonnes, 25.2 percent of generated mass, unaccounted for in the
totals table.** The same gap appears every year: 2022 is 24,224 t (23.7
percent), 2021 is 29,820 t (22.9 percent), 2020 is 32,095 t (23.2 percent).

**[DATA] `REU`, `RCV_E` and `DSP` are not populated in `env_waselvt_api` for
Belgium in any year.** They are populated in the detailed table
`env_waselv_api`. The totals table alone therefore understates what Belgium
reports, and the gap above closes substantially once the detailed table is
used (section 3.1). **Anyone comparing the two tables without noticing this
will conclude Belgium loses a quarter of its ELV mass, which is wrong.**

---

## 3. Material value composition, 2023

2023 is the most recent year and is complete for Belgium.

### 3.1 Mass decomposition **[DATA]**

From `env_waselv_api`, `geo='BE'`, `TIME_PERIOD='2023'`, mass per category
taken as `REU + RCY + RCV_E + DSP`:

| Category | Code | Tonnes | Share of treated stream |
|---|---|---|---|
| Ferrous scrap from shredding | `W191001` | 33,904 | **45.3%** |
| Other materials from dismantling | `W1601C` | 18,852 | 25.2% |
| Shredder Light Fraction | `W1910A` | 6,948 | 9.3% |
| Metal components, dismantled | `W1601B` | 4,960 | 6.6% |
| Non-ferrous, combined | `W191002` | 4,907 | **6.6%** |
| Other from shredding | `W1910B` | 1,999 | 2.7% |
| Tyres | `W160103` | 1,945 | 2.6% |
| Batteries | `W1606` | 564 | 0.8% |
| Liquids | `LIQ` | 462 | 0.6% |
| Large plastic parts | `W160119` | 121 | 0.2% |
| **Catalysts** | `W1608` | **93** | **0.12%** |
| Glass | `W160120` | 49 | 0.07% |
| Oil filters | `W160107` | 16 | 0.02% |
| **Total** | | **74,819** | 100% |

**[DATA] The decomposition reconciles exactly.** Dismantling branch `DMDP` =
27,061 t and shredding branch `W1910` = 47,758 t sum to 74,819 t. The
shredding sub-categories sum to 47,758 t exactly. The dismantling
sub-categories sum to 27,062 t, one tonne off from rounding. Treated `ELV` is
reported as 74,954 t, 135 t above the branch sum, a 0.18 percent discrepancy.

This reconciliation is worth stating because it means the mass side of this
analysis is solid. **The weakness is entirely on the value side.**

### 3.2 Two mass figures that should not be believed

**[DATA]** Glass at 49 tonnes and large plastic parts at 121 tonnes, against
a 74,819 tonne stream, are **0.07 percent and 0.16 percent**. A passenger car
is roughly 3 percent glass and 8 to 12 percent plastic by mass. On 74,819
tonnes that would be roughly 2,200 t of glass and 6,000 to 9,000 t of plastic.

**[DERIVED] Belgium is reporting about 2 percent of the glass and about 2
percent of the plastic that must physically be in the stream.** The
explanation consistent with the data is that glass and plastic are not
separately dismantled in Belgium and instead pass into the shredder, arriving
in `W1910A` Shredder Light Fraction (6,948 t) and `W1910B` (1,999 t). These
codes measure dismantling outputs, not material content.

**This is directly relevant to your stripping question and I address it in
3.4.**

### 3.3 The residual problem

**[DATA]** `W1601C` "other materials arising from dismantling" is **18,852
tonnes, 25.2 percent of the entire stream**, of which 17,898 t is reuse.

A quarter of Belgium's ELV mass sits in a category whose label is "other".
Its composition is not reported. **[OPEN]** No value can be attributed to it
without knowing what it contains. Since it is overwhelmingly reuse, it is
most likely whole reusable parts, which are the highest-value output of a
dismantling operation, but the data does not say so.

### 3.4 The stripping question, unresolved

You asked me not to assume stripping. **The Belgium data cannot resolve it,
and here is precisely why.**

**[DATA]** The evidence points both ways:

- **Consistent with stripping:** catalysts (93 t), batteries (564 t) and
  liquids (462 t) appear as separate dismantling outputs, so *some*
  depollution and selective removal is certainly happening. This is legally
  mandatory under the ELV Directive for exactly these components.
- **Consistent with no stripping:** glass and plastics appear at roughly 2
  percent of their physical presence (3.2), which means the bulk of those
  materials is going into the shredder with the shell.

**[DERIVED]** The reconcilable reading is that Belgium strips what regulation
requires it to strip (depollution: liquids, batteries, catalysts, tyres, oil
filters) and shreds the rest. But **the ELV statistics report treatment
routes, not material content**, so they cannot tell you whether the copper in
a wiring harness was recovered as copper or went into Shredder Light Fraction.

**[ASSUMPTION, carried forward explicitly]** For the value estimate below I
assume **regulatory stripping only**: catalysts, batteries, liquids, tyres
and oil filters removed; copper, aluminium and electronics enter the shredder
with the shell and are recovered, if at all, in `W191002`. **This assumption
is unverified and it materially changes the answer.** If Belgian dismantlers
in fact hand-strip harnesses and modules before shredding, the recovered
value rises and the SLF loss falls. Resolving it requires operator-level data
or a site visit, not Eurostat.

### 3.5 Assumptions table, prices

Every price used, with source and date. Nothing here is invented; where I
could not source a figure it is marked **[OPEN]** and left unfilled.

| # | Input | Value | Unit | Source | Date | Tag |
|---|---|---|---|---|---|---|
| P1 | Ferrous scrap, Europe | 340 | USD/tonne | [Intratec ferrous scrap prices](https://www.intratec.us/solutions/primary-commodity-prices/commodity/ferrous-scrap-prices) | Jan 2026 | **[SOURCED]** dated, not current |
| P2 | Copper, COMEX | ~13,900 | USD/tonne | [Fastmarkets base metals update](https://www.fastmarkets.com/metals-and-mining/base-metals/monthly-base-metals-market-update-2026/) via search, $6.30/lb | 14 Sep 2026 | **[SOURCED]** |
| P3 | Aluminium | ~3,250 | USD/tonne | [Trading Economics aluminum](https://tradingeconomics.com/commodity/aluminum) | mid-Sep 2026 | **[SOURCED]** |
| P4 | Platinum | 1,796 | USD/troy oz | [Kitco platinum](https://www.kitco.com/charts/platinum) | 19 Sep 2026 | **[SOURCED]** |
| P5 | Palladium | 1,314.50 | USD/troy oz | [Trading Economics palladium](https://tradingeconomics.com/commodity/palladium) | 18 Sep 2026 | **[SOURCED]** |
| P6 | Rhodium | 9,225 | USD/troy oz | [Trading Economics rhodium](https://tradingeconomics.com/commodity/rhodium) | 17 Sep 2026 | **[SOURCED]** |
| P7 | Copper share of `W191002` | n/a | % | none | n/a | **[OPEN]** |
| P8 | Aluminium share of `W191002` | n/a | % | none | n/a | **[OPEN]** |
| P9 | PGM grams per catalyst tonne | n/a | g/t | none | n/a | **[OPEN]** |
| P10 | Semiconductor mass and value | n/a | n/a | no Eurostat category exists | n/a | **[OPEN]** |
| P11 | Composition of `W1601C` (25.2% of stream) | n/a | n/a | not reported | n/a | **[OPEN]** |
| P12 | Plastics, glass, SLF value | assumed ~0 or negative | EUR/t | disposal cost, not revenue | n/a | **[ASSUMPTION]** |
| P13 | USD/EUR | not applied | n/a | prices left in USD | n/a | see note |

**Note on P13.** I have not converted to euros. Mixing a January 2026 scrap
price with September 2026 metal prices at a single exchange rate would
manufacture false precision. All figures stay in USD at their quoted dates.

**Note on P1.** This is the weakest sourced input: it is eight months stale
and the largest single mass component depends on it. Western European scrap
was reported as broadly stable through September 2026
([Kallanish](https://www.kallanish.com/en/news/steel/market-reports/article-details/western-european-scrap-seen-stable-0926/)),
which supports using it, but it should be refreshed before publication.

### 3.6 What can and cannot be computed

**[DERIVED] What can be computed:** ferrous mass and value, using P1.

```
Ferrous:  33,904 t x 340 USD/t  =  11,527,360 USD
```

**[OPEN] What cannot be computed, and why:**

| Requested output | Blocked by | Status |
|---|---|---|
| Copper value share | P7, no Cu/Al split in `W191002` | **cannot compute** |
| Aluminium value share | P8, same | **cannot compute** |
| PGM value share | P9, catalyst mass reported but not PGM content | **cannot compute** |
| Semiconductor value share | P10, no category exists | **cannot compute** |

**Therefore the Netherlands headline contrast cannot be reproduced for
Belgium from this data.** The Netherlands figure states steel at about 2
percent of value against 40 to 41 percent concentrated in copper, catalytic
converters and semiconductors. **Every one of those three components is an
[OPEN] input for Belgium.** I am not going to substitute plausible numbers to
fill that shape, because the resulting contrast would be an artefact of my
assumptions rather than a finding about Belgium.

**[DERIVED] What can be said.** Ferrous is **45.3 percent of the mass**. The
combined non-ferrous fraction that would contain all the copper is **6.6
percent of the mass**, and catalysts, which contain all the PGMs, are **0.12
percent of the mass**. If the Netherlands value structure holds
approximately in Belgium, then a mass share of 45.3 percent in the cheapest
material and 6.7 percent combined in the expensive ones reproduces the same
qualitative inversion. **But that is a conditional statement resting on the
Netherlands result, not an independent Belgian measurement, and it should be
presented as such.**

**To close the gap you need exactly two numbers:** the copper share of
`W191002`, and grams of PGM per tonne of catalyst. Both are obtainable from
a Belgian shredder operator or from published recycling-industry
coefficients. Neither is in Eurostat. A third number, the ferrous against
non-ferrous split of `W1601B`, is not needed for the value total but is
needed to sharpen the recovery estimate in 3.7.

### 3.7 Closing the open inputs: run both methods, not one

The four [OPEN] inputs in 3.5 can be closed two different ways, and the two
ways answer **different questions**. Running both is not redundancy. The
difference between them is the result.

| Method | What you do | What it tells you |
|---|---|---|
| **Top-down** | Apply published material composition per vehicle to Belgium's 63,592 vehicles / 80,190 t | What is **physically present** in the stream |
| **Bottom-up** | Obtain actual recovered tonnages by material from Febelauto or an operator | What was **actually recovered** |

**These are not interchangeable.** Applying top-down composition figures and
labelling the output "recovered value" would be wrong: the number produced is
value *present*, not value *captured*. The gap between the two is the
recycling gap expressed in materials rather than in compliance percentages,
which is the capstone thesis stated in one number.

Bottom-up is also the only route that settles the stripping question in 3.4.
Top-down describes what went into the shredder and can never say what came
out separately.

#### 3.7.1 Worked reconciliation **[DERIVED]**

Using the sourced anchors from 3.5 and the mass data from 3.1:

| Component | Tonnes | Basis |
|---|---|---|
| Top-down copper | 1,590 | 25 kg/vehicle x 63,592 vehicles **[SOURCED anchor]** |
| Top-down aluminium | 6,415 | 8% of 80,190 t **[SOURCED anchor]** |
| **Top-down non-ferrous present** | **8,005** | sum |
| Bottom-up `W191002` recovered | 4,907 | **[DATA]** |
| `W1601B` metal components | 4,960 | **[DATA]**, Fe/non-Fe split unknown |

Because `W1601B` is an unresolved mix, the answer is a **bracket rather than
a point estimate**, which is the honest form:

- If `W1601B` is **entirely ferrous**: **3,098 t of non-ferrous is not
  recovered as non-ferrous, 39 percent of what is present.**
- If `W1601B` is **entirely non-ferrous**: the gap closes to **zero**.

The truth sits between these, and **one number from the operator collapses
the bracket to a point estimate.** That is a far sharper request than asking
for a data extract.

#### 3.7.2 The consistency check that makes this credible

A top-down estimate is only worth reporting if the implied missing mass has
somewhere physical to go. It does:

```
unrecovered non-ferrous (upper bound)   3,098 t
Shredder Light Fraction (W1910A)        6,948 t
                                        3,098 / 6,948 = 45%
```

The missing non-ferrous fits inside SLF with room to spare. **If the
top-down method had implied 20,000 t of unaccounted copper, the method would
be broken and should be discarded.** It does not, so the estimate survives
its own sanity check. This check should be reported alongside the bracket,
because it is what distinguishes an estimate from a guess.

#### 3.7.3 The vintage correction, which is not optional

**[ASSUMPTION, and the one most likely to be challenged]** The 8 percent
aluminium anchor is a current-fleet figure. **Vehicles scrapped in Belgium in
2023 were built around 2005 to 2010**, since average EU scrappage age is
roughly 15 years. Aluminium content in new cars has risen substantially over
that period, so applying a 2023 new-car composition to a 2008-build vehicle
**overstates aluminium, plausibly by up to a third.**

The correction is to use composition **at build year**, not at scrappage
year. This is precisely what the JRC "Material composition **trends** in
vehicles" report exists to provide; the trend line is the point of it.

**Copper travels better across vintages than aluminium does.** Wiring harness
mass has been comparatively stable, so the 25 kg/vehicle anchor is the more
robust of the two and the aluminium figure carries most of the vintage risk.

**Without the vintage adjustment the top-down side will not survive review.
With it, it will.**

### 3.8 Provenance of the routes to the open inputs

| Open input | Route | Source | Status |
|---|---|---|---|
| P7 copper share, P8 aluminium share | Top-down | JRC126564, "Material composition trends in vehicles", European Commission Joint Research Centre | **Lead, not verified.** `rmis.jrc.ec.europa.eu` is blocked from the analysis sandbox, so the contents could not be confirmed here |
| P8 aluminium | Top-down | [European Aluminium, *Aluminium Content in Passenger Vehicles (Europe)*](https://european-aluminium.eu/wp-content/uploads/2023/05/23-05-02Aluminum-Content-in-Cars_Public-Summary.pdf) | Europe-specific, roughly 123 kg castings per vehicle, roughly 80 kg in powertrain |
| P9 PGM grams per tonne | Both | [Johnson Matthey PGM Market Report](https://matthey.com/media/2026/johnson-matthey-publishes-2026-pgm-market-report1) | Free, annual, the industry reference. Gives market-level autocatalyst recovery; per-converter loading may need a teardown study on top |
| P10 semiconductors | Top-down only | No statistical source exists; teardown and academic literature only | Hardest of the four, and may stay [OPEN] |
| P7, P9, and the `W1601B` split | Bottom-up | **Febelauto**, Belgium's ELV compliance scheme | See Appendix A |

**Why Febelauto is the right counterparty, evidenced rather than assumed.**
Febelauto reported **81,350 vehicles collected in 2022**, which matches the
Eurostat `GEN` count for Belgium in 2022 in this dataset **exactly** (see
2.2). That identity establishes the reporting chain as ATFs to Febelauto to
Eurostat, which means **Febelauto holds the granularity that Eurostat
aggregates away before publication.** They operate a network of over 100
authorised treatment facilities and publish annual reports in Dutch and
French.

Source: [Recycling International on Belgium ELV
performance](https://recyclinginternational.com/business/95-elv-recycling-target-within-reach-for-belgium/5491/),
[Febelauto](https://www.febelauto.be/).

**Incidental finding relevant to the other workstream.** The "over 100 ATFs"
figure is an operator count for Belgium. The scrap price case needs an
operator concentration measure and found permitted storage capacity to be
unharmonised. Compliance schemes such as Febelauto may hold ATF counts per
country that Eurostat SBS does not publish at 4-digit NACE. Worth checking
before settling for the SBS route.

---

## 4. Export to fleet, and the Antwerp hypothesis

### 4.1 The fleet denominator **[DATA]**

`road_eqs_carmot_api` in `elv_bronze`, `geo='BE'`, `mot_nrg='TOTAL'`,
`engine='TOTAL'`, unit `NR`:

| Year | Belgium passenger car fleet |
|---|---|
| 2021 | 5,926,009 |
| 2022 | 5,955,127 |
| **2023** | **6,047,551** |

Source: Eurostat road equipment stock, same 28 April 2026 vintage, already in
`elv_bronze`. No repull.

### 4.2 The measurement problem, stated plainly

**[DATA] Belgium's `EXP` is reported in tonnes and means "End-of-life
vehicles exported".** The 2023 values are 5,371 t on a `GEN` basis and 5,020 t
across treatment operations.

**The Netherlands comparator of 237,875 is a count of vehicles.** These are
different measurements of different populations:

| | Netherlands figure | Belgium `EXP` |
|---|---|---|
| Unit | vehicles (count) | tonnes (mass) |
| Population | used vehicles exported for resale | end-of-life vehicles exported for treatment |
| Leaves as | a vehicle | waste |
| In ELV statistics? | no | yes |

**A used vehicle driven onto a ship at Antwerp is not an end-of-life vehicle
and never enters `env_waselv_api`.** It leaves the fleet through
deregistration and appears in no ELV statistic at all. This is the border
where the regulatory statistics stop, and it is the whole of your hypothesis.

### 4.3 Computing the ratio anyway, both ways

**[DERIVED]** Using the 1.261 t/vehicle factor from 2.2:

```
5,371 t / 1.261 t per vehicle  =  4,259 vehicle-equivalents
```

| Construction | Belgium 2023 | Netherlands comparator |
|---|---|---|
| `EXP` vehicle-equivalents / fleet | 4,259 / 6,047,551 = **0.07%** | 237,875 / 986,000 = **24.1%** |
| `EXP` tonnes / generated tonnes | 5,371 / 80,190 = **6.7%** | not available |
| `EXP` vehicle-equivalents / ELVs generated | 4,259 / 63,592 = **6.7%** | not available |

### 4.4 The answer to your test

**You asked whether Belgium's export-to-fleet ratio actually runs higher than
the Netherlands, or whether that is an assumption the numbers do not support.**

**The numbers do not support it, and more importantly the comparison as
constructed is invalid.** Belgium's ratio computes to 0.07 percent against
the Netherlands 24.1 percent, a factor of roughly 340. That difference is
almost entirely a definitional artefact, not a behavioural one: it compares
ELV waste exports against used-vehicle exports.

**[DATA] What the data does support**, and it is a real finding: Belgium's
ELV exports have **collapsed**, from 31.4 percent of generated tonnage in
2006 to 6.7 percent in 2023.

| Year | `EXP` (t) | Generated (t) | `EXP` as % of generated |
|---|---|---|---|
| 2006 | 41,079 | 131,030 | 31.4% |
| 2010 | 37,031 | 176,446 | 21.0% |
| 2014 | 8,630 | 138,703 | 6.2% |
| 2018 | 26,890 | 177,439 | 15.2% |
| 2021 | 12,140 | 129,979 | 9.3% |
| 2022 | 6,945 | 102,334 | 6.8% |
| 2023 | 5,371 | 80,190 | 6.7% |

**[DERIVED] Note the 2014 to 2018 reversal.** The ratio fell to 6.2 percent
in 2014, recovered to 15.2 percent by 2018, then fell again. A monotonic
decline would suggest a structural change; this looks more like a reporting
or policy discontinuity around 2014 to 2016. It should be checked before any
claim is built on the trend.

### 4.5 A caution on the Netherlands denominator

**[OPEN]** The Netherlands comparator is given as 237,875 exports against "a
fleet of roughly 986,000". **The Dutch passenger car fleet is approximately
8.5 to 9 million vehicles, not 986,000.** A denominator of 986,000 is close
to the Netherlands' annual ELV and deregistration volume, not its fleet.

If 986,000 is in fact annual deregistrations, then the Netherlands 24.1
percent is an **export-to-deregistration** ratio, and the correct Belgian
analogue is the 6.7 percent in the table above, not the 0.07 percent. **That
changes the comparison from a factor of 340 to a factor of 3.6.**

**I flag this rather than resolve it because the Netherlands run is yours and
I cannot see its construction.** Confirm what 986,000 counts before the two
countries are put on a slide together. It is the single highest-risk number
in this comparison.

---

## 5. Questions a professor is most likely to ask

1. **"Your non-ferrous number contains both copper and aluminium. How can you
   claim anything about copper value?"**
   I cannot, and I say so. `W191002` is a single Eurostat code covering
   aluminium, copper, zinc and lead. The split is [OPEN].

2. **"You report 93 tonnes of catalysts. What is the PGM content?"**
   Not reported by Eurostat. Catalyst mass is gross. PGM grams per tonne is
   [OPEN] and is one of only two numbers needed to complete the value picture.

3. **"Why is Belgium reporting 49 tonnes of glass?"**
   Because the code measures separately dismantled glass, not glass content.
   Physical glass in the stream is roughly 2,200 t. About 98 percent of it
   goes to the shredder. This is the clearest single piece of evidence on the
   stripping question.

4. **"A quarter of your mass is in a category called 'other'. What is in it?"**
   Unknown. `W1601C` is 18,852 t, 25.2 percent, overwhelmingly reuse. Most
   likely whole reusable parts. [OPEN].

5. **"Your generated total and your recovery total differ by 25 percent.
   Where did the mass go?"**
   Nowhere. `REU`, `RCV_E` and `DSP` are unpopulated in the totals table for
   Belgium and populated in the detailed table. Using the detailed table
   closes most of the gap. This trips up anyone using only `env_waselvt_api`.

6. **"Is Belgium's export ratio higher than the Netherlands, as the Antwerp
   story implies?"**
   Not as measured, and the comparison is not valid as constructed. See 4.4.
   Also confirm what the Netherlands 986,000 denominator counts, see 4.5.

7. **"Do you know whether high-value materials are stripped before
   shredding?"**
   No. The data shows regulatory depollution happening and glass and plastic
   not being separated. I carry "regulatory stripping only" forward as an
   explicit assumption and flag that it materially changes the value result.

8. **"Why is your scrap price from January when your metal prices are from
   September?"**
   Because that is the most recent European ferrous scrap price I could
   source. It is the weakest input and the largest mass component depends on
   it. It should be refreshed.

9. **"Belgium's ELV intake fell 63 percent since 2010. Does that not dominate
   everything else here?"**
   It may. 170,562 vehicles in 2010 to 63,592 in 2023 is not explained within
   this dataset, and any value total scales directly with it.

---

## 6. Provenance

| Figure | Source | Tag |
|---|---|---|
| Row counts, year coverage | `elv_bronze.env_waselvt_api`, `env_waselv_api`, `geo='BE'` | [DATA] |
| Category labels | `elv_bronze.codelists_api`, Eurostat DSD | [DATA] |
| ELVs generated, counts and tonnes | `env_waselvt_api`, `wst_oper='GEN'`, units NR and T | [DATA] |
| 1.261 t/vehicle | 80,190 / 63,592, both [DATA] | [DERIVED] |
| 2023 mass decomposition | `env_waselv_api`, `TIME_PERIOD='2023'`, REU+RCY+RCV_E+DSP | [DATA] |
| Fleet 6,047,551 | `elv_bronze.road_eqs_carmot_api`, TOTAL/TOTAL, NR | [DATA] |
| `EXP` series | `env_waselv_api`, `waste='EXP'` | [DATA] |
| All prices | section 3.5 table, each with source and date | [SOURCED] / [OPEN] |
| Stripping behaviour | not resolvable from Eurostat | [ASSUMPTION] |
| Netherlands 986,000 denominator | supplied, construction unverified | [OPEN] |

**Eurostat vintage 28 April 2026 throughout. No API repull was performed.
All Belgium figures come from the validated `elv_bronze` tables.**

---

## Appendix A. Data request to Febelauto

Three specific numbers, not a data extract. Each one is named because it
closes a stated gap in this analysis, and the request says which. A narrow,
justified ask is far more likely to be answered than a general one.

**Ask 1. The ferrous against non-ferrous split of dismantled metal
components.**
Eurostat code `W1601B`, 4,960 tonnes for Belgium in 2023. This is currently
the single number preventing a point estimate: with it, the unrecovered
non-ferrous bracket in 3.7.1 collapses from "somewhere between 0 and 3,098
tonnes" to one figure.

**Ask 2. Platinum, palladium and rhodium content per tonne of catalyst.**
Eurostat code `W1608`, 93 tonnes for Belgium in 2023, reported as gross mass
only. Grams per tonne, or total grams recovered, either is usable. Without it
no PGM value can be computed at all.

**Ask 3. Whether wiring harnesses and electronic modules are removed before
shredding.**
A yes or no with an approximate share is enough. Section 3.4 carries
"regulatory stripping only" as an explicit unverified assumption, and the
answer materially changes the recovered value estimate. Eurostat reports
treatment routes rather than material content and cannot settle it.

**Useful context to include in the approach.** Their published figure of
81,350 vehicles collected in 2022 matches the Eurostat `GEN` count for
Belgium exactly, which is worth stating: it shows the request comes from
someone who has already reconciled the published data and is asking only for
what sits beneath it.

**Optional fourth ask, for the scrap price workstream.** The number of
authorised treatment facilities per year, which would give an operator
concentration series that Eurostat SBS may suppress at 4-digit NACE 38.31.

**If Febelauto cannot share operator-level data,** the fallback is that Asks
1 and 2 are also obtainable from any single Belgian shredder operator, and
Ask 2 from published recycling-industry assay coefficients. Ask 3 has no
documentary substitute and would remain [OPEN].
