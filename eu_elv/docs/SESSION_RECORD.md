# Session record: EU ELV pipeline, 2026-07-31 to 2026-08-14

Branch: `claude/eu-elv-credential-rotation-pbjhep`
Project: msbai-capstone-nb4603 (NYU Stern MSBAi capstone, "The Global ELV Recycling Gap")

This is a working record of one long session. It covers what was asked, what
was built, what was found, what was wrong and later corrected, and what
remains open. It is written to be useful to someone picking the work up
cold, so it includes the mistakes as well as the results.

---

## 1. Starting state and premise corrections

The session opened with three premises in the request that did not hold. All
three were checked rather than assumed, and the work proceeded on the
corrected footing.

| Stated | Actual |
|---|---|
| Read `CLAUDE.md` in this repo | No `CLAUDE.md` exists here. The credential incident write-up lives in the separate `msbai-dwd-nb4603` repo, and only on its `claude/eu-elv-recycling-pipeline-r18pmo` branch, not on `main`. |
| Clone the separate `msbai-capstone-nb4603` repo | That is the repo the session already started in. Nothing to clone. |
| The designated branch continues the pipeline work | The branch pointed at `main`, which lacks the fetch job entirely. The work sits on the unmerged commit `f23d85a`, which had to be merged in first. |

The credential incident itself was real and is documented in the other
repo. A service account key had been exposed twice, once through a Cloud
Run Job environment variable echoed back by the Admin API, and once through
a stale plaintext file in Cloud Shell. Key and passphrase were both rotated.

**GCP auth verification.** The SessionStart hook silently no-ops in this
session, because it looks for `.cloud-credentials.<user email>.enc` and the
repo carries a different team member's file. Credentials were decrypted
manually and verified three ways: the rotated passphrase decrypts the
committed `.enc`, `private_key_id` matches the documented active key
`fc611a58...`, and a live BigQuery query against the project succeeded.

---

## 2. Task one: Secret Manager rework

**Goal.** Stop passing the service account key as a plaintext Cloud Run Job
environment variable, which is what leaked it.

**What was built.** The key now lives in Secret Manager and is mounted as a
file at `/secrets/sa/key.json`. The Job spec carries only a secret
reference, so the Admin API has no key material to echo back.
`fetch_bronze_api.py` refuses `GCP_SA_KEY_JSON` outright rather than
silently accepting the shape that caused the incident.
`summarize_execution()` replaced a raw `json.dumps(op)` status dump with
named-field output. The `secretAccessor` binding is scoped to the single
secret and granted to Cloud Run's project local compute service account,
which is the Job's real runtime identity, since an organization policy
blocks running as the cross project `claude-agent@`.

**Two grants were needed, both confirmed live rather than assumed.**

1. `secretmanager.googleapis.com` was not enabled on the project at all.
   Every call returned 403 "has not been used in project". This is separate
   from IAM, and no role grant would have cleared it.
2. `claude-agent@` held none of the five required Secret Manager
   permissions. `roles/secretmanager.admin` covered all five.

The project owner granted both. A `preflight()` function re-verifies both on
every run and refuses to proceed rather than leaving a half created secret
behind.

### Four defects found on the first live run

The rework had never been executed. The original session wrote it and ran
only the parts that worked. None of these is a regression.

| Defect | Detail |
|---|---|
| Wrong HTTP verb | `getIamPolicy` is a GET on Secret Manager. POSTing it returns **404**, not 405, which reads exactly like a missing secret while the secret had just been created successfully. |
| Version churn | `addVersion` was called unconditionally, minting a new version of byte identical key material every run. Always Free covers 6 active versions. Now the latest version is compared first. |
| Missing credentials | `storage.Client(project=PROJECT)` took no credentials and fell back to ambient ADC, which is set only when the SessionStart hook fires. Worked in the authoring session, died here. Every other call in the file passed credentials explicitly. |
| Wrong API field | The secret volume used `versions`, the v1 and Knative spelling. Cloud Run **v2 calls it `items`** and rejects the v1 form with `400 Unknown name "versions"`. |

That last one cost an extra round trip because every call used bare
`raise_for_status()`, which reports only the status line and URL and
discards the response body, where the API had named the offending field
exactly. All call sites now go through a `check()` helper that surfaces the
API's own message.

**Verified, not assumed.** After the job ran clean, the full Job resource
was fetched back and probed for `BEGIN PRIVATE KEY`, `private_key`,
`GCP_SA_KEY_JSON` and the active key's `private_key_id`. None matched. All
the spec carries is a mount path and a secret reference. That is the exact
response shape that leaked the key when the spec held a plaintext env var.

---

## 3. Task two: value level diff of the automated pull

**Goal.** The automated Eurostat API pull had matched the hand verified
manual export on row counts (4,305 and 30,268). Row counts are not a value
check.

**Result: zero differences**, on every shared column, in both datasets.

The diff script (`eu_elv/pipeline/diff_api_vs_raw.py`) does three things
that matter more than the result:

- Compares over the **shared** columns only, because the two loads do not
  have the same schema.
- **Asserts key uniqueness** rather than assuming it. A duplicated natural
  key would fan out the join and turn a real mismatch into a passing diff.
- **Runs a negative control on every invocation.** A clean diff and a diff
  that is not comparing anything look identical in the output. The same
  comparison is re-run against an API side with `TIME_PERIOD` shifted one
  year, and it must report differences. It does: 3,968 and 18,020
  `OBS_VALUE` diffs. If the control ever comes back clean, the script fails
  loudly and voids the all clear.

One honest limit recorded: `CONF_STATUS` is 100% NULL in all four tables,
so its agreement is vacuous. `OBS_VALUE` and `OBS_FLAG` carry the real
signal.

### Correction: the schemas do not match

The existing `DECISIONS.md` recorded that "no mismatch was reported" on the
one API run. That was wrong. The manual databrowser export is SDMX-CSV with
labels; the API pull returns the codes only variant.

| | `_raw` (manual) | `_api` (automated) |
|---|---|---|
| provenance columns | `STRUCTURE`, `STRUCTURE_ID`, `STRUCTURE_NAME` | `DATAFLOW`, `LAST UPDATE` |
| label columns | 8 to 9 | none |
| codes and measures | identical | identical |

The detection logic in `load_to_bronze()` was working correctly and did
print a NOTE. It went to the Cloud Run job logs, which nobody read, and the
note in `DECISIONS.md` was written from the `run_job()` response instead.
Matching row counts made it look verified.

This blocked the cutover: `silver_elv_detail.sql` and
`silver_elv_totals.sql` select four label columns the `_api` tables do not
have.

---

## 4. Four probe rounds: no URL produces the labels

The obvious fix was a fetch URL parameter. It is not. Four rounds of live
probing from inside the Cloud Run Job, since `ec.europa.eu` is unreachable
from the sandbox, settled it.

| Attempt | Result |
|---|---|
| `format=SDMX-CSV2.0` | **406** `UNSUPPORTED_FORMAT`, not a valid value |
| `labels=both`, `label=both`, `labels=name`, `lang=en` | **silently ignored**, header byte identical to baseline |
| `Accept: application/vnd.sdmx.data+csv;version=2.0.0;labels=both` | **ignored**, served `Content-Type: application/vnd.sdmx.genericdata+xml`, meaning SDMX-ML rather than CSV |
| `statistics/1.0/data` endpoint | **400** `Invalid value for 'wsOutputFormat'` |
| `datastructure/ESTAT/ENV_WASELVT` | **200**, SDMX structure XML |

**The conclusion is structural, not a missing flag.** Labels are code to
name mappings held in the DSD and codelists, not in the observations. The
databrowser inlines them when building an export; the SDMX data endpoint
returns codes and expects the consumer to resolve them. Dropping
`format=SDMX-CSV` does not help either, because Eurostat then serves
SDMX-ML rather than honouring an Accept CSV media type.

### Two methodological failures in the probe itself

These are more reusable than the answer.

**Round 2 was inconclusive by construction.** It varied the `Accept` header
while leaving `format=SDMX-CSV` in the query string. An explicit `format`
param overrides content negotiation, so all seven "different" candidates
issued the same request. Fourteen byte identical results looked like strong
evidence and were actually a broken experiment. A probe that cannot
distinguish its own candidates produces confident looking uniform output.

**Round 3 discarded its two most informative results.** `csv.reader` raised
on an unparseable body before anything was recorded, so the one response
that genuinely differed survived only as an exception string. Recording
`Content-Type` unconditionally is what finally identified it as SDMX-ML,
and that single header is what turned four rounds of negative results into
a structural explanation.

---

## 5. The cutover: labels resolved in Silver

Labels now come from Eurostat's own codelists.
`fetch_bronze_api.py` loads `elv_bronze.codelists_api` (5,290 entries, 7
codelists) in the same execution as the data, so the two cannot drift apart.
`elv_silver.code_reference` exposes it as `(codelist_id, code, label)`, and
both Silver views now read the `_api` tables and join it.

Getting the codelists took two fixes, both found by reading the actual
document rather than guessing.

1. **The plain `/datastructure` response is a 6KB stub** with no component
   definitions at all. `references=descendants&detail=full` returns 3.4MB
   carrying components and every codelist inline, which also collapses a
   discovery call plus one fetch per codelist into one request per dataflow.
2. **`<Ref>` inside `<Enumeration>` is in the default, empty namespace**,
   not SDMX `common`. Qualifying it matched nothing and produced an *empty
   mapping rather than an error*. This was caught only because
   `load_codelists()` refuses to load an empty table. Without that guard the
   run would have reported success and blanked every label in Silver.

### Verification of the cutover

| Check | Result |
|---|---|
| Label text vs databrowser | **29 of 29 codes byte identical**, no casing or punctuation drift |
| `(codelist_id, code)` uniqueness | unique across all 5,290 rows |
| `elv_totals` vs pre cutover snapshot | 4,305 rows, **0 differing rows either direction** |
| `elv_detail` vs pre cutover snapshot | 30,268 rows, **0 differing rows either direction** |
| Unresolved labels | **0** join misses in either view |
| Gold rebuild | `elv_country_year` still 543 rows |
| Dashboard extract regenerated | byte identical to the committed CSV |

The view diff used a full row `EXCEPT DISTINCT` in both directions, not a
row count. Row counts already matched before any of this work, which is
exactly how the original schema mismatch went unnoticed.

**Operational note.** `claude-agent@` has no Cloud Logging read access,
confirmed by a 403 "Permission denied for all log views". A failed Cloud Run
execution therefore reports only "the container exited with an error".
Rather than request a broader role, every run now mirrors its stdout to
`gs://<staging bucket>/runs/run_<ts>.log` from a `finally` block, a bucket
the job can already write. That is what turned an opaque exit code into the
exact failing step, and it is worth keeping.

---

## 6. Documents produced

All in `eu_elv/docs/`, all ASCII only apart from the euro sign, all US
spellings, all schema validated.

| File | Contents |
|---|---|
| `EU_ELV_Talking_Points.docx` | Six sections on the EU-wide findings: target attainment, the export lens, the two tier anomaly split, reading caveats, provenance, likely questions |
| `EU_ELV_Top_Contender.docx` | Evidence based country selection (Belgium) with a landscape appendix covering all 30 reporting countries |
| `EU_ELV_Dashboard_Tool_Comparison.docx` | Tableau, Looker Studio and Streamlit against the BigQuery gold layer, with licensing separated from hosting cost |
| `Belgium_ELV_Research_Brief_Full.docx` | Full A to G research brief with sources, confidence ratings and complete limitations |
| `Belgium_ELV_Material_Value_Brief.docx` | Condensed version of the same, leading with the number |
| `EU_ELV_Source_Data_Reference.docx` | The raw data with no interpretation: 543 country year records and 677 Belgium material records |

### Top contender: Belgium

Selected on consistency and margin rather than peak rate.

- Recycling target met in **18 of 18 years** (2006 to 2023)
- Both targets met in **9 consecutive years** (2015 to 2023)
- 2023 at 93.5% recycling and 97.7% recovery
- Monotonic improvement from 87.7% and 90.0%
- **Zero** quality flags or anomalies of any kind
- Export share 11.0%

Runner up Netherlands, on the longest both target streak (11 years) but a
3.1 point margin and 19.0% export share.

**Croatia was actively rejected** despite a 12 of 12 (100%) attainment
record: 58.3% export share, seven missing years, a flat to declining trend,
and a 2013 entry at exactly 100.0% / 100.0% carrying an "estimated" flag.

### Belgium material value

**Estimated EUR 19.7M to 25.8M (USD 22.6M to 29.6M)** of gross material
value recovered annually from 51,840 tonnes recycled domestically in 2023.

The quantities are official Eurostat figures. The **monetary figure is
calculated, not reported**, because Belgium publishes no value for
recovered ELV materials. Prices are secondary market bands with per material
confidence ratings, so the arithmetic can be reproduced with better inputs.
Steel contributes 60 to 69% of the total and carries the best sourced
prices. Catalytic converters are excluded for lack of a defensible price,
making the estimate a lower bound.

The material breakdown reconciles exactly, which is what makes the domestic
and export split defensible:

```
ELV recycled 56,651 t = dismantling and depollution 8,609 t
                      + shredding 43,231 t
                      + exported 4,811 t
```

**Research constraint.** Web search worked but web fetch was blocked by the
egress proxy for `febelauto.be` and `cemonitor.be`. Febelauto's annual
reports were never opened. Institutional details in the brief rest on search
engine summaries of secondary coverage, which is flagged prominently in the
document itself.

---

## 7. The investigation that produced the strongest finding

This started as a causal reasoning exercise for a course assignment and
turned into the most substantive result of the session.

### The question

Does exporting used vehicles cause a country to recover less material
domestically?

### What the tests showed

**Test 1: is Belgium's ELV collapse Belgium specific?** Partly. The EU27
total fell from 6.1M to 4.26M vehicles since 2018, a 30% decline, so a
continental shock is real. But Belgium's 55.5% fall is the **largest in the
EU**, with zero of 27 countries falling more, roughly double the median.

**Test 2: COVID shock or structural trend?** Structural. Indexed to 2018,
Belgium ran 100, 94, 77, 73, 57, 45. The steepest drops are 2022 and 2023,
after COVID, not during it.

**Test 3: does intra-EU relocation explain it?** No, and this **refuted an
overstatement made earlier in the session**. Lithuania at +45% and Latvia at
+25% looked like an eastward shift, but in absolute terms all country gains
total 25,923 vehicles against 1,920,578 in losses. Gains offset **1.3%** of
losses. The percentage growth was on tiny bases.

**Test 4: vehicle weight.** Flat at roughly 1.25 t per vehicle. Neutral.

**Test 5: the fleet balance.** This required data Eurostat holds but the
sandbox cannot reach, so the Cloud Run job was extended with a generic
`--extra=` flag that pulls any Eurostat dataflow. Fleet stock, age
distribution and new registrations were loaded.

| Year | Fleet | ELVs | Scrappage rate |
|---|---:|---:|---:|
| 2018 | 5,848,425 | 142,852 | 2.44% |
| 2023 | 6,047,551 | 63,592 | **1.05%** |

The fleet **grew** 6.8% while scrappage more than halved.

**Test 6: is the fleet aging?** Yes, unmistakably. Cars under 2 years fell
22%, cars 10 to 20 years rose 12%, cars over 20 years rose **26%**. That is
the retention signature.

### Two findings, answering different questions

**Why did ELV counts collapse? Retention.** Belgians are keeping cars
longer, and registrations fell from 557,487 in 2018 to 374,597 in 2022
during the chip shortage. The export hypothesis is **not supported** as the
explanation for the decline.

**Where do Belgian cars actually go? Mostly not to recycling.** The vehicle
balance, computed with actual registration data rather than a proxy, shows:

| | vehicles, 2018 to 2023 |
|---|---:|
| Entered the ELV system | 636,243 |
| Left the fleet unaccounted for | **1,921,678** |
| Ratio | **3.0 to 1** |

**Belgium's ELV statistics capture 24.9% of vehicles leaving its fleet**,
and the share has fallen from 28.1% in 2018 to 16.2% in 2023.

### The cross country pattern

| Low capture, cars leave before scrapping | High capture, scrapping more than they lose |
|---|---|
| Luxembourg 5.7% | Poland **727%** |
| Germany 15.3% | Czechia **309%** |
| Austria 21.8% | Slovakia **264%** |
| **Belgium 24.9%** | Finland 230%, Portugal 207%, Ireland 181% |

A rate above 100% means a country scraps more vehicles than leave its own
fleet, which means it is scrapping imported cars. Wealthy Western fleets
lose cars they never scrap; Central and Eastern European processors scrap
cars that were never in their fleet.

### What this is and is not

This is **accounting, not causal inference**. The balance is a subtraction,
and the residual absorbs stolen vehicles, administrative deregistrations and
mismatches between two independently collected Eurostat series. It shows a
gap exists and how large it is. It does not establish causation.

What it buys is a **better measured outcome variable** for a causal design
and a documented reason to care.

**Caveats.** Poland at 727% almost certainly includes data quality problems
as well as real imports, since fleet stock series in some countries are
known to overstate. Belgium's 2023 fleet jump of +92,424 against a typical
+29,000 may be a series break. Treat the exporter and processor direction as
solid and the exact percentages as indicative.

### The causal design, for the assignment

- **Cause:** used vehicle export intensity
- **Effect:** share of fleet exits captured by the domestic ELV system
- **Instrument:** destination country import restrictions, such as the
  vehicle age ceilings adopted by Kenya and Nigeria, measured as each EU
  country's pre period export exposure interacted with adoption timing
- **Why the instrument works:** a Nigerian import age law has no plausible
  direct effect on Belgian shredder productivity, so it can affect domestic
  recovery only by changing how many vehicles stay in the country
- **Known weakness:** destination demand may correlate with global scrap
  prices, which independently affect recycling profitability

The chain reads: foreign demand (instrument), then exports (cause), then
domestic material recovery (effect).

---

## 8. Corrections made during the session

Recorded because the pattern is instructive.

| Correction | What happened |
|---|---|
| `DECISIONS.md` schema claim | Recorded "no mismatch was reported" when the schemas plainly differ. The detection worked; its output went to unread logs. |
| The 47% ferrous decline framing | Presented as "material value declining despite improving compliance", which implies deteriorating recycling. The real cause is 55% fewer vehicles arriving. Recovery per tonne actually improved slightly. |
| EU27 export figures | First computed from the EU27 aggregate row, which Eurostat publishes only for 2020 and 2023, making exports appear to vanish in other years. Corrected by summing country rows: a stable 5.7% to 8.2%. |
| Intra-EU relocation | Called the eastward pattern "hard to explain any other way" before checking absolute numbers. Those gains are 1.3% of losses. |
| Sweden's target record | Written as 4 of 18 years in a draft. Verified as 10 of 18 before it shipped. |
| Document characters | Typographic characters including U+2212 true minus, arrows and middle dots render as boxes in Word. Replaced with ASCII. |
| British spellings | `organisation`, `authorised`, `licence`, `favourable`, `labelled` and `tyres` corrected to US forms in prose. Eurostat's own label text keeps "tyres" verbatim, with a note explaining why. |

The recurring trap is that **matching row counts prove nothing**. It hid the
schema mismatch, it would have hidden a bad label join, and it is why the
diff carries a negative control and the cutover was checked with a full row
comparison in both directions.

---

## 9. Open items

- **Febelauto's annual reports** remain unopened. They are the single most
  valuable missing source, likely carrying material level and possibly
  financial detail Eurostat lacks. Needs a network without the egress block.
- **Costs and therefore net value** are unavailable. No public source covers
  Belgian collection, dismantling or shredding costs, so only gross material
  value can be computed.
- **UN Comtrade HS 8703** is blocked from this environment. It is required
  to build the export exposure measure for the causal design. Eurostat's own
  trade dataflows may be reachable from the Cloud Run job as a substitute.
- **`build_and_deploy.py` line 118** has the same ambient ADC bug that was
  fixed in the fetch job. It will fail in any session where the SessionStart
  hook does not fire.
- **`deploy_cloud_run.py`** is superseded by `build_and_deploy.py` and
  should be deleted to avoid someone picking the wrong one.
- **Dashboard reachability** has never been verified. `*.run.app` is blocked
  from this sandbox. The service is deployed, routes are ready and
  `roles/run.invoker` is bound to `allUsers`, but no one has confirmed the
  page loads in a browser. Given this app's history of a pyarrow segfault
  taking down the whole server, that check is worth doing.
- **Regional ELV data** for Flanders, Wallonia and Brussels was not
  obtained. Eurostat reports Belgium nationally.
- **Single data vintage.** Everything derives from the Eurostat release
  dated 28 April 2026. The pipeline has not been tested across a
  republication.

---

## 10. Reproducing any of this

Pipeline, in order:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/tmp/gcp-adc-credentials.json

python3 eu_elv/pipeline/build_and_run_fetch_job.py    # Bronze + codelists
python3 eu_elv/pipeline/diff_api_vs_raw.py            # integrity check
python3 eu_elv/pipeline/build_silver.py               # Silver views
python3 eu_elv/pipeline/build_gold.py                 # Gold
python3 eu_elv/dashboard/build_extract.py             # dashboard CSV
git diff --stat eu_elv/dashboard/data/                # the deploy gate
python3 eu_elv/pipeline/build_and_deploy.py           # only if the CSV changed
```

Useful flags on the fetch job:

| Flag | Effect |
|---|---|
| `--probe` | Try API format candidates, write results to GCS, load nothing |
| `--dump-structure` | Write raw SDMX structure XML to GCS for inspection |
| `--extra=code1,code2` | Pull arbitrary Eurostat dataflows into Bronze |

Every figure in the documents traces to `elv_silver.elv_detail` or
`elv_gold.elv_country_year`, sourced from Eurostat via
`eu_elv/pipeline/fetch_bronze_api.py`. Run logs for any Cloud Run execution
are at `gs://msbai-capstone-nb4603-eu-elv-staging-us/runs/`.
