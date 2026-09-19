# Belgium ELV Material Value Analysis

**19 September 2026 · NYU Stern MSBAi Capstone**
The Global ELV Recycling Gap · material value composition, Belgium 2023

---

## Scope and reading conventions

This analysis decomposes Belgium's end-of-life vehicle stream by material mass
and attempts to convert that to value. All figures come from the validated
`elv_bronze` path at the 28 April 2026 Eurostat vintage. No API repull was
performed.

Every number below carries a tag. The tags are the point of the document: the
mass side of this analysis is solid and the value side is not, and the tags
are what make that visible at a glance.

| Item | Value |
|---|---|
| GCP project | `msbai-capstone-nb4603` |
| Dataset | `elv_bronze` |
| Source tables | `env_waselvt_api`, `env_waselv_api`, `road_eqs_carmot_api`, `codelists_api` |
| Eurostat vintage | 28 April 2026 |
| Reference year | 2023 |
| Currency | USD at quoted dates, not converted (see Price assumptions) |
| Companion note | `netherlands_figures_review.md` |

| Tag | Meaning |
|---|---|
| `[DATA]` | Measured in `elv_bronze`, traceable to a table, year and code |
| `[DERIVED]` | Computed from [DATA], with the arithmetic shown |
| `[SOURCED]` | External input with a citation and a date |
| `[OPEN]` | Required but not obtainable, deliberately left unfilled |
| `[ASSUMPTION]` | An assumption, carried forward explicitly |

> **Nothing in this document substitutes a plausible number for a missing
> one.** Where an input could not be sourced it is marked [OPEN] and the
> dependent calculation is not performed.

---

## Headline: four things Eurostat cannot tell you

A mass-share against value-share contrast cannot be computed for Belgium from
Eurostat ELV statistics, and the reason is structural rather than a Belgian
data quality problem. This is a finding about why a global recycling gap can
exist, not a caveat on the analysis.

1. **Copper cannot be separated from aluminium.** Eurostat reports one
   combined code, `W191002` "Non-ferrous materials (aluminium, copper, zinc,
   lead, etc.)". There is no split anywhere in the codelist.
2. **PGM content is not reported.** `W1608` "Catalysts" is reported as a gross
   mass, 93 tonnes in 2023. Platinum, palladium and rhodium content within
   that mass does not exist as a statistic.
3. **Electronics and semiconductors have no category at all.** There is no
   code for them anywhere in the ELV waste codelist.
4. **Belgium's `EXP` code is not used-vehicle exports.** It is "End-of-life
   vehicles exported", reported in tonnes of waste. Used vehicles shipped
   abroad for resale leave the fleet through deregistration and appear in no
   ELV statistic at all.

The first three block the value decomposition. The fourth blocks the Antwerp
hypothesis as currently constructed, and is addressed in Export to fleet
below.

What the data does support is a mass decomposition that reconciles exactly, a
Belgium-specific tonnes-per-vehicle conversion factor, and a 63 percent
collapse in ELV intake since 2010 that no variable in this dataset explains.

---

## Rows, coverage and category codes

`[DATA]` Queried `geo = 'BE'`, all years, both tables. No null observations in
either.

| Table | Rows (BE) | Year range | Years | Null OBS_VALUE |
|---|---|---|---|---|
| `env_waselvt_api` | 144 | 2006 to 2023 | 18 | 0 |
| `env_waselv_api` | 1,375 | 2006 to 2023 | 18 | 0 |

**Belgium's series begins at 2006, not 2005.** Any panel built alongside
countries whose series start in 2005 will be one year offset.

### Category codes, resolved against the Eurostat codelist

`[DATA]` All 17 codes present for Belgium resolve. None unresolved.

| Code | Label | Note |
|---|---|---|
| `ELV` | Waste arising only from end-of-life vehicles of type passenger cars (M1), light commercial (N1) | Top-level total |
| `EXP` | **End-of-life vehicles exported** | **Tonnes, not counts** |
| `DMDP` | Waste from dismantling and de-pollution of end-of-life vehicles | Branch total |
| `W1910` | Waste arising from shredding of end-of-life vehicles | Branch total |
| `W191001` | Ferrous scrap (steel) from shredding | |
| `W191002` | **Non-ferrous materials (aluminium, copper, zinc, lead, etc.)** | **Combined, not split** |
| `W1910A` | Shredder Light Fraction (SLF) | Where unstripped material lands |
| `W1910B` | Other materials arising from shredding | |
| `W1601B` | End-of-life vehicles: metal components | Ferrous / non-ferrous mix, unresolved |
| `W1601C` | End-of-life vehicles: other materials arising from dismantling | Residual, 25.2 percent of stream |
| `W1608` | Catalysts | Gross mass only |
| `W1606` | Batteries and accumulators | |
| `W160103` | End-of-life vehicles: tyres | British spelling in Eurostat's label |
| `W160107` | End-of-life vehicles: oil filters | |
| `W160119` | End-of-life vehicles: large plastic parts | |
| `W160120` | End-of-life vehicles: glass | |
| `LIQ` | Liquids (excluding fuel) | |

Operation codes, all resolved: `GEN` waste generated, `REU` reuse, `RCY`
recycling, `RCV` recovery, `RCV_E` energy recovery (R1), `DSP` disposal.

---

## The Belgium denominator

`[DATA]` Belgium reports in three units, and the unit matters. **There is
exactly one count series: `GEN` in `NR`.** Everything else, exports included,
is mass.

| Unit | Label | Rows (BE) | What carries it |
|---|---|---|---|
| `T` | Tonne | 1,465 | Every material category, and `EXP` |
| `NR` | Number | 18 | `GEN` only, in `env_waselvt_api` |
| `PC` | Percentage | 36 | The reported rate series |

### ELVs generated, counts and tonnes

| Year | Generated (vehicles) | Generated (tonnes) | Implied t/vehicle |
|---|---|---|---|
| 2010 | 170,562 | 176,446 | 1.034 |
| 2015 | 107,425 | 119,054 | 1.108 |
| 2019 | 134,629 | 168,810 | 1.254 |
| 2020 | 110,161 | 138,468 | 1.257 |
| 2021 | 103,659 | 129,979 | 1.254 |
| 2022 | 81,350 | 102,334 | 1.258 |
| **2023** | **63,592** | **80,190** | **1.261** |

> `[DERIVED]` **The count-to-tonne conversion factor is 1.261 t/vehicle for
> 2023**, computed as 80,190 / 63,592. It is derived from Belgium's own
> reported data rather than imported, which makes it the defensible factor for
> this country. It has drifted up from 1.034 in 2010, consistent with vehicles
> getting heavier, and is stable at about 1.25 to 1.26 across 2019 to 2023.

`[DATA]` **Belgium's ELV intake has fallen 63 percent from its 2010 peak**,
from 170,562 to 63,592 vehicles. Nothing in this dataset explains it.

### Treated against generated, and the divergence trap

| Year | GEN (t) | RCY (t) | RCV (t) | Gap (t) | Gap as % of GEN |
|---|---|---|---|---|---|
| 2020 | 138,468 | 100,412 | 106,373 | 32,095 | 23.2% |
| 2021 | 129,979 | 95,215 | 100,159 | 29,820 | 22.9% |
| 2022 | 102,334 | 73,782 | 78,110 | 24,224 | 23.7% |
| 2023 | 80,190 | 56,651 | 60,014 | 20,176 | 25.2% |

> **This gap is an artefact, not lost mass.** `REU`, `RCV_E` and `DSP` are not
> populated in `env_waselvt_api` for Belgium in any year. They are populated
> in the detailed table `env_waselv_api`, and using it closes most of the gap.
> Anyone working from the totals table alone will conclude Belgium loses a
> quarter of its ELV mass, which is wrong.

---

## Mass composition, 2023

`[DATA]` From `env_waselv_api`, mass per category taken as
`REU + RCY + RCV_E + DSP`. Ferrous is 45.3 percent of the stream. The combined
non-ferrous fraction that would contain all the copper is 6.6 percent, and
catalysts, which contain all the PGMs, are 0.12 percent.

| Category | Code | Tonnes | Share of stream |
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
| Catalysts | `W1608` | 93 | 0.12% |
| Glass | `W160120` | 49 | 0.07% |
| Oil filters | `W160107` | 16 | 0.02% |
| **Total** | | **74,819** | **100%** |

**The decomposition reconciles exactly.** Dismantling (`DMDP`, 27,061 t) and
shredding (`W1910`, 47,758 t) sum to 74,819 t. The shredding sub-categories
sum to their branch total to the tonne. Treated `ELV` is reported as 74,954 t,
135 t above the branch sum, a 0.18 percent discrepancy. **The mass side is
solid. The weakness is entirely on the value side.**

### Two mass figures that should not be believed

Glass at 49 tonnes and large plastic parts at 121 tonnes, against a 74,819
tonne stream, are 0.07 and 0.16 percent. A passenger car is roughly 3 percent
glass and 8 to 12 percent plastic by mass, which on this stream would be
roughly 2,200 t of glass and 6,000 to 9,000 t of plastic.

> `[DERIVED]` **Belgium is reporting about 2 percent of the glass and about 2
> percent of the plastic that must physically be in the stream.** These codes
> measure separately dismantled material, not material content. The remainder
> goes into the shredder and arrives in Shredder Light Fraction. This is the
> clearest single piece of evidence on the stripping question below.

### The residual problem

`W1601C` "other materials arising from dismantling" is **18,852 tonnes, 25.2
percent of the entire stream**, of which 17,898 t is reuse. A quarter of
Belgium's ELV mass sits in a category whose label is "other" and whose
composition is not reported. `[OPEN]` No value can be attributed to it without
knowing what it contains. Since it is overwhelmingly reuse, it is most likely
whole reusable parts, which are the highest-value output of a dismantling
operation, but the data does not say so.

### The stripping question, unresolved

The evidence points both ways, and the data cannot settle it.

- **Consistent with stripping:** catalysts (93 t), batteries (564 t) and
  liquids (462 t) appear as separate dismantling outputs, so some selective
  removal is certainly happening. This is legally mandatory under the ELV
  Directive for exactly these components.
- **Consistent with no stripping:** glass and plastics appear at roughly 2
  percent of their physical presence, so the bulk of those materials goes into
  the shredder with the shell.

> `[ASSUMPTION]` **Carried forward explicitly:** regulatory stripping only.
> Catalysts, batteries, liquids, tyres and oil filters removed; copper,
> aluminium and electronics enter the shredder with the shell. **This is
> unverified and it materially changes the answer.** If Belgian dismantlers
> hand-strip harnesses and modules before shredding, recovered value rises and
> the SLF loss falls. The ELV statistics report treatment routes, not material
> content, so they cannot resolve it.

---

## Price assumptions and what cannot be computed

Every price used, with source and date. Where a figure could not be sourced it
is marked [OPEN] and left unfilled.

| # | Input | Value | Source and date | Tag |
|---|---|---|---|---|
| P1 | Ferrous scrap, Europe | 340 USD/t | Intratec ferrous scrap prices, January 2026 | `[SOURCED]` stale |
| P2 | Copper, COMEX | ~13,900 USD/t | Fastmarkets base metals update, 14 Sep 2026 | `[SOURCED]` |
| P3 | Aluminium | ~3,250 USD/t | Trading Economics, mid-Sep 2026 | `[SOURCED]` |
| P4 | Platinum | 1,796 USD/oz | Kitco, 19 Sep 2026 | `[SOURCED]` |
| P5 | Palladium | 1,314.50 USD/oz | Trading Economics, 18 Sep 2026 | `[SOURCED]` |
| P6 | Rhodium | 9,225 USD/oz | Trading Economics, 17 Sep 2026 | `[SOURCED]` |
| P7 | Copper share of `W191002` | not available | no source | `[OPEN]` |
| P8 | Aluminium share of `W191002` | not available | no source | `[OPEN]` |
| P9 | PGM grams per catalyst tonne | not available | no source | `[OPEN]` |
| P10 | Semiconductor mass and value | not available | no Eurostat category exists | `[OPEN]` |
| P11 | Composition of `W1601C` | not available | not reported, 25.2% of stream | `[OPEN]` |
| P12 | Plastics, glass, SLF value | ~0 or negative | disposal cost, not revenue | `[ASSUMPTION]` |

**No USD to EUR conversion has been applied.** Mixing a January 2026 scrap
price with September 2026 metal prices at a single exchange rate would
manufacture false precision. P1 is the weakest input and the largest mass
component depends on it; Western European scrap was reported broadly stable
through September 2026 (Kallanish), which supports using it, but it should be
refreshed before publication.

### What can and cannot be computed

`[DERIVED]` Ferrous value, using P1: `33,904 t x 340 USD/t = 11,527,360 USD`.

| Requested output | Blocked by | Status |
|---|---|---|
| Copper value share | P7, no Cu/Al split in `W191002` | Cannot compute |
| Aluminium value share | P8, same | Cannot compute |
| PGM value share | P9, catalyst mass reported but not PGM content | Cannot compute |
| Semiconductor value share | P10, no category exists | Cannot compute |

The mass is concentrated in the cheapest material while the materials that
carry most of the value sit in fractions of a few percent. That is the
**precondition** for a value inversion. Whether the inversion actually holds
in Belgium cannot be established without the [OPEN] inputs above, and must not
be asserted from the mass shares alone.

---

## Closing the open inputs: run both methods

The [OPEN] inputs can be closed two different ways, and the two ways answer
different questions. Running both is not redundancy. The difference between
them is the result.

| Method | What you do | What it tells you |
|---|---|---|
| **Top-down** | Apply published material composition per vehicle to Belgium's 63,592 vehicles and 80,190 t | What is **physically present** in the stream |
| **Bottom-up** | Obtain actual recovered tonnages by material from Febelauto or an operator | What was **actually recovered** |

> **These are not interchangeable.** Applying top-down composition figures and
> labelling the output "recovered value" would be wrong: the number produced
> is value present, not value captured. **The gap between the two is the
> recycling gap expressed in materials rather than in compliance
> percentages**, which is the capstone thesis stated in one number. Bottom-up
> is also the only route that settles the stripping question above.

### Worked reconciliation

`[DERIVED]` Using the sourced anchors and the mass data above.

| Component | Tonnes | Basis |
|---|---|---|
| Top-down copper | 1,590 | 25 kg/vehicle x 63,592 vehicles `[SOURCED]` |
| Top-down aluminium | 6,415 | 8 percent of 80,190 t `[SOURCED]` |
| **Non-ferrous present** | **8,005** | sum |
| Recovered, `W191002` | 4,907 | `[DATA]` |
| `W1601B` metal components | 4,960 | `[DATA]`, Fe / non-Fe split unknown |

Because `W1601B` is an unresolved mix, the answer is a **bracket rather than a
point estimate**, which is the honest form:

- If `W1601B` is **entirely ferrous**: **3,098 t of non-ferrous is not
  recovered as non-ferrous, 39 percent of what is present.**
- If `W1601B` is **entirely non-ferrous**: the gap closes to **zero**.

The truth sits between these, and **one number from the operator collapses the
bracket to a point estimate.** That is a far sharper request than asking for a
data extract.

### The consistency check that makes this credible

A top-down estimate is only worth reporting if the implied missing mass has
somewhere physical to go. It does.

```
unrecovered non-ferrous (upper bound)   3,098 t
Shredder Light Fraction (W1910A)        6,948 t
                                        3,098 / 6,948 = 45%
```

The missing non-ferrous fits inside SLF with room to spare. **If the method
had implied 20,000 t of unaccounted copper it would be broken and should be
discarded.** It does not, so the estimate survives its own sanity check.
Report this check alongside the bracket: it is what distinguishes an estimate
from a guess.

### The vintage correction, which is not optional

> `[ASSUMPTION]` **The most likely challenge.** The 8 percent aluminium anchor
> is a current-fleet figure. Vehicles scrapped in Belgium in 2023 were built
> around **2005 to 2010**, since average EU scrappage age is roughly 15 years.
> Aluminium content in new cars has risen substantially over that period, so
> applying a 2023 new-car composition to a 2008-build vehicle **overstates
> aluminium, plausibly by up to a third**.
>
> The correction is to use composition **at build year**. This is precisely
> what a material composition *trends* report exists to provide. **Copper
> travels better across vintages than aluminium does**, since wiring harness
> mass has been comparatively stable, so the aluminium figure carries most of
> the vintage risk.

### Where the missing inputs come from

| Open input | Route | Source and status |
|---|---|---|
| P7, P8 copper and aluminium share | Top-down | JRC126564, "Material composition trends in vehicles", European Commission Joint Research Centre. **Lead, not verified:** the domain is blocked from the analysis sandbox, so contents could not be confirmed |
| P8 aluminium | Top-down | European Aluminium, *Aluminium Content in Passenger Vehicles (Europe)*. Roughly 123 kg castings per vehicle, roughly 80 kg in powertrain |
| P9 PGM grams per tonne | Both | Johnson Matthey PGM Market Report, free and annual, the industry reference. Market-level recovery; per-converter loading may need a teardown study on top |
| P10 semiconductors | Top-down only | No statistical source exists. Teardown and academic literature only. May stay [OPEN] |
| P7, P9 and the `W1601B` split | Bottom-up | **Febelauto**, Belgium's ELV compliance scheme. See appendix |

> **Why Febelauto is the right counterparty, evidenced rather than assumed.**
> Febelauto reported **81,350 vehicles collected in 2022**, which matches the
> Eurostat `GEN` count for Belgium in 2022 in this dataset **exactly**. That
> identity establishes the reporting chain as ATFs to Febelauto to Eurostat,
> which means Febelauto holds the granularity Eurostat aggregates away before
> publication. They operate a network of over 100 authorised treatment
> facilities.

**Incidental finding for the scrap price workstream.** That "over 100 ATFs"
figure is an operator count for Belgium. The scrap price case needs an
operator concentration measure and found permitted storage capacity to be
unharmonised across the EU. Compliance schemes may hold ATF counts per country
that Eurostat SBS does not publish at 4-digit NACE. Worth checking before
settling for the SBS route.

---

## Export to fleet, and the Antwerp hypothesis

`[DATA]` Belgium passenger car fleet from `road_eqs_carmot_api`,
`mot_nrg=TOTAL`, `engine=TOTAL`, unit `NR`: **6,047,551 in 2023** (5,955,127
in 2022; 5,926,009 in 2021). Same Eurostat vintage, already in `elv_bronze`,
no repull.

`[DATA]` Belgium's `EXP` is reported in tonnes and means "End-of-life vehicles
exported". The 2023 values are 5,371 t on a `GEN` basis and 5,020 t across
treatment operations.

### The measurement problem, stated plainly

Two different populations are easily conflated here, and any export-to-fleet
ratio depends entirely on which one is meant.

| | Used-vehicle exports | Eurostat `EXP` |
|---|---|---|
| Unit | vehicles (count) | tonnes (mass) |
| Population | used vehicles exported for resale | end-of-life vehicles exported for treatment |
| Leaves as | a roadworthy vehicle | waste |
| In ELV statistics? | **No** | Yes |

**A used vehicle driven onto a ship at Antwerp is not an end-of-life vehicle
and never enters `env_waselv_api`.** It leaves the fleet through
deregistration and appears in no ELV statistic at all. This is the border
where the regulatory statistics stop, and it is the whole of the Antwerp
hypothesis.

### Computing the ratio anyway

`[DERIVED]` Using the 1.261 t/vehicle factor:
`5,371 t / 1.261 = 4,259 vehicle-equivalents`.

| Construction | Belgium 2023 |
|---|---|
| `EXP` vehicle-equivalents / registered fleet | 4,259 / 6,047,551 = **0.07%** |
| `EXP` tonnes / generated tonnes | 5,371 / 80,190 = **6.7%** |
| `EXP` vehicle-equivalents / ELVs generated | 4,259 / 63,592 = **6.7%** |

**Which of these is the right ratio depends on what it is being compared
against.** A ratio built on the registered fleet and one built on annual ELV
volume differ here by a factor of roughly 100. They are not interchangeable,
and a cross-country comparison that mixes the two will report a difference
that is entirely definitional.

### The Antwerp hypothesis, tested

> **The proposition was that Belgium's used-vehicle export volume through
> Antwerp is large relative to its domestic fleet, and that this should show
> up as a high export-to-fleet ratio.**
>
> **The ELV statistics cannot test it.** `EXP` measures end-of-life vehicles
> exported for treatment, not used vehicles exported for resale. The Antwerp
> flow leaves as roadworthy vehicles and is absent from these tables entirely.
>
> **This is a measurement finding, not a null result.** The hypothesis is not
> disproved; it is untestable on this data and needs a vehicle-registration or
> trade source instead.

### Reporting history

`[DATA]` What the data does support: Belgium's ELV exports have collapsed,
from 31.4 percent of generated tonnage in 2006 to 6.7 percent in 2023.

| Year | EXP (t) | Generated (t) | EXP as % of generated |
|---|---|---|---|
| 2006 | 41,079 | 131,030 | 31.4% |
| 2010 | 37,031 | 176,446 | 21.0% |
| 2014 | 8,630 | 138,703 | 6.2% |
| 2018 | 26,890 | 177,439 | 15.2% |
| 2021 | 12,140 | 129,979 | 9.3% |
| 2022 | 6,945 | 102,334 | 6.8% |
| 2023 | 5,371 | 80,190 | 6.7% |

`[DERIVED]` **Note the 2014 to 2018 reversal.** The ratio fell to 6.2 percent
in 2014, recovered to 15.2 percent by 2018, then fell again. A monotonic
decline would suggest structural change; this looks more like a reporting or
policy discontinuity around 2014 to 2016. **Any trend claim on EU export
reporting should be checked against that break first.**

---

## Open items, ranked by what they block

| # | Item | What it blocks, and how to close it |
|---|---|---|
| 1 | Ferrous / non-ferrous split of `W1601B` | Collapses the recovery bracket from "0 to 3,098 t" to a point estimate. One number from Febelauto |
| 2 | Per-vehicle catalyst PGM loading | All PGM value. Johnson Matthey, or an operator assay |
| 3 | Copper share of `W191002` | All copper value. JRC composition data, or an operator |
| 4 | Stripping behaviour before shredding | Whether recovered value is understated. Only obtainable from an operator |
| 5 | Composition of `W1601C` | 25.2 percent of stream mass carries no attributable value |
| 6 | Refreshed European ferrous scrap price | P1 is from January 2026 and the largest mass component depends on it |
| 7 | Semiconductor mass per vehicle | No statistical source exists; may remain permanently open |

Comparator data issues raised by this analysis have moved to the companion
note, `netherlands_figures_review.md`, so they reach the owner of that run
rather than sitting inside a Belgium deliverable.

---

## Likely questions

1. **"Your non-ferrous number contains both copper and aluminium. How can you
   claim anything about copper?"** I cannot, and I say so. `W191002` is a
   single code covering aluminium, copper, zinc and lead. The split is [OPEN].
2. **"You report 93 tonnes of catalysts. What is the PGM content?"** Not
   reported. Catalyst mass is gross. Grams per tonne is [OPEN] and is one of
   only two numbers needed to complete the value picture.
3. **"Why is Belgium reporting 49 tonnes of glass?"** Because the code
   measures separately dismantled glass, not glass content. Physical glass is
   roughly 2,200 t, so about 98 percent goes to the shredder. This is the
   clearest evidence on the stripping question.
4. **"A quarter of your mass is in a category called 'other'. What is in
   it?"** Unknown. `W1601C`, 18,852 t, overwhelmingly reuse, most likely whole
   reusable parts. [OPEN].
5. **"Your generated and recovery totals differ by 25 percent. Where did the
   mass go?"** Nowhere. `REU`, `RCV_E` and `DSP` are unpopulated in the totals
   table and populated in the detailed table. This trips up anyone using
   `env_waselvt_api` alone.
6. **"Does the Antwerp export story show up in the numbers?"** Not in these
   numbers, and it cannot. `EXP` is ELV waste exported for treatment; used
   vehicles exported for resale are absent from ELV statistics entirely.
   Untestable here rather than disproved.
7. **"Do you know whether high-value materials are stripped before
   shredding?"** No. Regulatory depollution is happening and glass and plastic
   are not being separated. "Regulatory stripping only" is carried forward as
   an explicit assumption that materially changes the value result.
8. **"Why is your scrap price from January when your metal prices are from
   September?"** Because that is the most recent European ferrous scrap price
   I could source. It is the weakest input and the largest mass component
   depends on it.
9. **"Belgium's ELV intake fell 63 percent since 2010. Does that not dominate
   everything?"** It may. 170,562 to 63,592 vehicles is not explained within
   this dataset, and any value total scales directly with it.

---

## Provenance

| Figure | Source | Tag |
|---|---|---|
| Row counts, year coverage | `env_waselvt_api`, `env_waselv_api`, `geo='BE'` | `[DATA]` |
| Category labels | `codelists_api`, Eurostat DSD | `[DATA]` |
| ELVs generated, counts and tonnes | `env_waselvt_api`, `wst_oper='GEN'`, units NR and T | `[DATA]` |
| 1.261 t/vehicle | 80,190 / 63,592, both [DATA] | `[DERIVED]` |
| 2023 mass decomposition | `env_waselv_api`, 2023, REU+RCY+RCV_E+DSP | `[DATA]` |
| Fleet 6,047,551 | `road_eqs_carmot_api`, TOTAL/TOTAL, NR | `[DATA]` |
| `EXP` series | `env_waselv_api`, `waste='EXP'` | `[DATA]` |
| All prices | Price assumptions table, each with source and date | `[SOURCED]` / `[OPEN]` |
| Febelauto 81,350 for 2022 | Recycling International; matches Eurostat GEN exactly | `[SOURCED]` |
| Stripping behaviour | not resolvable from Eurostat | `[ASSUMPTION]` |

**Eurostat vintage 28 April 2026 throughout. No API repull was performed. All
Belgium figures come from the validated `elv_bronze` tables.**

---

## Appendix: data request to Febelauto

Three specific numbers, not a data extract. Each names the gap it closes. A
narrow, justified ask is far more likely to be answered than a general one.

| Ask | Number wanted | Why, and what it closes |
|---|---|---|
| **1** | Ferrous against non-ferrous split of dismantled metal components (`W1601B`, 4,960 t in 2023) | Currently the single number preventing a point estimate. Collapses the bracket from "between 0 and 3,098 tonnes" to one figure |
| **2** | Platinum, palladium and rhodium per tonne of catalyst (`W1608`, 93 t in 2023, gross mass only). Grams per tonne or total grams, either works | Without it no PGM value can be computed at all |
| **3** | Whether wiring harnesses and electronic modules are removed before shredding. A yes or no with an approximate share is enough | Settles the assumption carried forward above, which materially changes the recovered value estimate |
| 4 *(optional)* | Authorised treatment facilities per year | Operator concentration series for the scrap price workstream, which Eurostat SBS may suppress at 4-digit NACE 38.31 |

**Useful context for the approach.** Their published figure of 81,350 vehicles
collected in 2022 matches the Eurostat `GEN` count for Belgium exactly. Saying
so shows the request comes from someone who has already reconciled the
published data and is asking only for what sits beneath it.

**If Febelauto cannot share operator-level data**, Asks 1 and 2 are also
obtainable from any single Belgian shredder operator, and Ask 2 from published
recycling-industry assay coefficients. Ask 3 has no documentary substitute and
would remain [OPEN].

---

## Before publication

- Refresh the ferrous scrap price (P1, January 2026) and state its date.
- Apply the build-year vintage correction to the aluminium anchor, or state
  plainly that the top-down figure is uncorrected.
- Open JRC126564 and verify it carries the composition split. It is currently
  a lead, not a confirmed source.
- Report the bracket together with its SLF consistency check. The check is
  what makes the bracket credible.
- Confirm the comparator construction in the companion Netherlands note before
  the two countries appear on one slide.
