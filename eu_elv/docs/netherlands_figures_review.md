# Note on the Netherlands comparator figures

**To:** whoever owns the Netherlands ELV run
**From:** the Belgium material value analysis (`belgium_material_value.md`)
**Date:** 19 September 2026
**Status:** two issues found while mirroring the method. Neither is resolved
here, because the Netherlands construction is not visible from the Belgium
side. Both need confirming before the two countries appear on the same slide.

---

## Why this note exists

The Belgium analysis was asked to mirror the Netherlands method so the two
would be directly comparable. While doing that, two problems surfaced that
are **about the Netherlands figures rather than about Belgium**, so they do
not belong buried in a Belgium deliverable. They are here instead.

The figures supplied as the comparator were:

- **237,875** reported exports, 2023
- against a fleet of **roughly 986,000**
- steel at about **2 percent of value by mass** against about **40 to 41
  percent** concentrated in copper, catalytic converters and semiconductors

---

## Issue 1: the 986,000 denominator is very unlikely to be a fleet

**This is the higher-risk of the two.**

The Dutch passenger car fleet is approximately **8.5 to 9 million vehicles**.
A denominator of 986,000 is off by nearly an order of magnitude from that,
and is much closer to the Netherlands' **annual** ELV or deregistration
volume.

**Why it matters.** If 986,000 is annual deregistrations rather than the
registered fleet, then 237,875 / 986,000 = 24.1 percent is an
**export-to-deregistration** ratio, not an export-to-fleet ratio. Those are
different statistics and they are not interchangeable.

The consequence for the comparison is large. Belgium's equivalents, from the
Belgium analysis section 4.3:

| Construction | Belgium 2023 |
|---|---|
| Exports against registered fleet | 0.07% |
| Exports against annual ELV volume | 6.7% |

So:

- If 986,000 **is** the fleet, the correct Belgian analogue is **0.07
  percent**, and the gap between the countries is a factor of roughly **340**.
- If 986,000 is **annual deregistrations**, the correct analogue is **6.7
  percent**, and the gap is a factor of roughly **3.6**.

**One ambiguity in the denominator moves the headline comparison by two
orders of magnitude.** Whichever it is, the Belgium side has both numbers
ready, so this is quick to reconcile once confirmed.

**What to check:** what 986,000 counts, and from which source and year.

---

## Issue 2: the two export figures are not the same measurement

**237,875 appears to be a count of vehicles. Belgium's Eurostat export
figure is tonnes of waste.** These measure different populations:

| | Used-vehicle exports | Eurostat `EXP` |
|---|---|---|
| Unit | vehicles (count) | tonnes (mass) |
| Population | used vehicles exported for resale | end-of-life vehicles exported for treatment |
| Leaves as | a roadworthy vehicle | waste |
| In ELV statistics? | **no** | yes |

A used vehicle exported for resale is **not** an end-of-life vehicle. It
leaves the fleet through deregistration and never enters `env_waselv_api` at
all. Belgium's `EXP` code, by contrast, is explicitly "End-of-life vehicles
exported" and is reported in tonnes.

**Why it matters.** If the Netherlands 237,875 came from a
vehicle-registration or trade source rather than from Eurostat ELV
statistics, then the two countries' export figures are not comparable as
they stand, and a ratio built across them would report a difference that is
definitional rather than behavioural.

**What to check:** which source 237,875 came from. If it is Eurostat
`env_waselv` `EXP` for NL, it should be in tonnes and the count needs
explaining. If it is a registration or trade source, Belgium needs the same
source rather than Eurostat for any comparison to hold.

**Note for the wider project.** This is the same border the capstone thesis
is about. The regulatory statistics stop where the vehicle stops being waste
and becomes a traded good. It is worth treating as a finding rather than a
data-cleaning problem.

---

## Issue 3, minor: panel start year

Belgium's Eurostat series begins at **2006**, not 2005. If the Netherlands
panel starts at 2005, the two are offset by one year. Worth aligning before
any pooled regression.

---

## What the Belgium side can confirm

For reference, the Belgium figures are on the validated `elv_bronze` path,
Eurostat vintage 28 April 2026, no repull:

| Item | Belgium 2023 | Source |
|---|---|---|
| ELVs generated (count) | 63,592 | `env_waselvt_api`, `GEN`, unit `NR` |
| ELVs generated (mass) | 80,190 t | `env_waselvt_api`, `GEN`, unit `T` |
| Implied mass per vehicle | 1.261 t | derived, 80,190 / 63,592 |
| `EXP` exported ELVs | 5,371 t | `env_waselv_api`, `waste='EXP'`, `GEN` |
| Registered passenger car fleet | 6,047,551 | `road_eqs_carmot_api`, TOTAL/TOTAL, `NR` |

The 1.261 t/vehicle factor is derived from Belgium's own reported data rather
than assumed, so it can be used to move between counts and tonnes on the
Belgium side without importing an external conversion.

**If the Netherlands run has an equivalent count and mass pair, comparing the
two implied vehicle masses is a quick sanity check on whether both countries
are measuring the same thing.**

---

## Two things that would settle both issues

1. **What 986,000 counts**, with source and year.
2. **Which source 237,875 came from**, and whether it is a count or a mass.

Both Belgian analogues are already computed and waiting, so the comparison
can be rebuilt the same day either way.
