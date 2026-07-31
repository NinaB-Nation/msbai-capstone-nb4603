# Design decisions -- EU ELV Recycling Pipeline

## GCP setup

- **Project**: `msbai-capstone-nb4603`, separate from any other class project.
  Rather than provisioning a brand-new service account (which would have
  needed `iam.serviceAccounts.create` -- not available), the existing
  `claude-agent@` identity was reused cross-project: it was granted IAM
  roles directly on `msbai-capstone-nb4603` instead. This keeps the
  credential-management machinery (encrypted key, SessionStart hook)
  completely untouched, at the cost of one identity spanning two projects.
- **Dataset naming**: `elv_bronze` / `elv_silver` / `elv_gold`, no region
  prefix -- confirmed with the project owner before creating anything.
- Roles were granted incrementally as each stage actually needed them
  (BigQuery + GCS first, then Cloud Build/Artifact Registry once local
  `docker build`/`push` turned out to be blocked, then Cloud Run's public
  -invoker binding last) rather than requesting a broad role up front.

## Data acquisition

- **Eurostat's API (`ec.europa.eu`) is blocked by this environment's network
  egress policy** -- confirmed via both a direct `curl` and the `WebFetch`
  tool, both failing with a 403 at the proxy's CONNECT tunnel (a policy
  denial, not a transient failure). Both `env_waselvt` and `env_waselv` were
  instead exported manually from Eurostat's databrowser (SDMX-CSV "linear"
  format) and uploaded for loading into Bronze.
- The SDMX-CSV "linear" export is already one row per (geo, year, wst_oper,
  unit[, waste]) -- tidy/long -- so there is no wide year-columns layout to
  pivot in Silver, unlike older Eurostat bulk TSV formats.

## Automated API pull (2026-07-31) -- partially complete

The manual databrowser export was replaced with an automated pull straight
from Eurostat's SDMX 2.1 REST API. Since `ec.europa.eu` is blocked from the
dev sandbox but not from GCP itself, the fetch runs as a **Cloud Run Job**
(`pipeline/fetch_bronze_api.py` + `Dockerfile.fetch_job`), built and
submitted via Cloud Build -- the same pattern the dashboard image uses,
since local `docker push` to `*.pkg.dev` is also blocked.

- **Lands in a new bucket**: `msbai-capstone-nb4603-eu-elv-staging-us`,
  single-region `us-central1`. Deliberately *not* the existing
  `msbai-capstone-nb4603-eu-elv-staging`, which is EU multi-region and so
  doesn't qualify for GCS Always Free (that tier covers single-region US
  buckets only).
- **Lands in new tables**, `elv_bronze.env_waselvt_api` /
  `env_waselv_api`, alongside rather than over the hand-verified
  `env_waselvt_raw` / `env_waselv_raw`, so the automated pull can be diffed
  against data already checked by hand.
- **Schema is read from the live API's own header row**, not assumed to
  match the manual export's; a mismatch is logged and the actual header is
  used.
- **Result of the single run**: `env_waselvt_api` 4,305 rows and
  `env_waselv_api` 30,268 rows -- both exactly matching the manual tables'
  row counts.

### Correction: the schemas do *not* match (checked 2026-07-31)

An earlier version of this section recorded that "no mismatch was
reported" on the one run. That is wrong -- the loaded tables disagree, and
the note was written from the `run_job()` response rather than from the
job's own logs, where `load_to_bronze()`'s mismatch NOTE would have
appeared. The detection logic was working; nobody read its output.

The manual databrowser export is SDMX-CSV **with labels**; the API pull, at
`format=SDMX-CSV` with no `labels` parameter, returns the **codes-only**
variant:

| | `_raw` (manual) | `_api` (automated) |
|---|---|---|
| provenance cols | `STRUCTURE`, `STRUCTURE_ID`, `STRUCTURE_NAME` | `DATAFLOW`, `LAST UPDATE` |
| label cols | 8-9 (`geo_label`, `unit_of_measure`, `waste_label`, `obs_flag_label`, ...) | none |
| codes + measures | identical set | identical set |

**This blocks the `_raw` -> `_api` cutover**, and row counts hid it.
`silver_elv_detail.sql` and `silver_elv_totals.sql` select four label
columns the API tables do not have -- `waste_management_operations`,
`waste_label`, `unit_of_measure`, `obs_flag_label` -- so repointing Silver
at the `_api` tables today fails at view-creation time. The likely fix is
`format=SDMX-CSV2.0` plus `labels=both` on the fetch URL, which is what
produces the manual export's column shape; **not verified**, because
`ec.europa.eu` is unreachable from this sandbox, so it can only be
confirmed from inside the Cloud Run Job.

### Value-level diff: clean (`pipeline/diff_api_vs_raw.py`, 2026-07-31)

Row counts matching is not a value check, so the tables were compared cell
by cell over the columns they share -- natural key
(`freq`, `wst_oper`, `[waste,]` `unit`, `geo`, `TIME_PERIOD`) plus measures
(`OBS_VALUE`, `OBS_FLAG`, `CONF_STATUS`), via `FULL OUTER JOIN`:

- **Zero differences in both datasets.** 4,305 / 30,268 keys matched, no key
  present on only one side, no `OBS_VALUE` difference (string *or* numeric
  cast), no `OBS_FLAG` difference.
- Key uniqueness is **asserted, not assumed** -- a duplicated key would fan
  out the join and turn a real mismatch into a passing diff. All four
  tables are unique on it.
- **A negative control runs every time**, because "zero differences" and
  "the diff isn't comparing anything" look identical in the output. The same
  comparison is re-run against an API side with `TIME_PERIOD` shifted one
  year; it must report differences, and does (3,968 / 18,020 `OBS_VALUE`
  diffs, 84 / 508 `OBS_FLAG` diffs). If the control ever comes back clean
  the script fails loudly and voids the all-clear above.
- **`CONF_STATUS`'s agreement is vacuous**: it is 100% NULL in all four
  tables, so it cannot differ and the control cannot move it. `OBS_VALUE`
  and `OBS_FLAG` are the only measures carrying real signal.
- The label columns **were not diffed and could not be** -- they exist on
  only one side (see the correction above). The clean result covers codes
  and measures, not labels.
- Why the values agree exactly: both loads are the same Eurostat vintage.
  `_api` carries `LAST UPDATE = 28/04/26 11:00:00` and dataflow
  `ESTAT:ENV_WASELVT(1.0)` / `ENV_WASELV(1.0)`, matching `_raw`'s
  `STRUCTURE_ID`. This is a same-vintage agreement, so it validates the
  fetch-and-load path; it is not evidence about how the pull behaves once
  Eurostat republishes.

### Secret handling: reworked, still blocked on two grants

The job passed the service-account key as a plaintext env var on the Job
spec, which leaked it (Cloud Run's API returns env-var values in
describe/execution responses). The key has been revoked and rotated.
`build_and_run_fetch_job.py` has been reworked:

- The key is stored in Secret Manager and **mounted as a file** at
  `/secrets/sa/key.json`; the Job spec now carries only a secret
  *reference*, so the Admin API has no key material to echo. The container
  reads `GCP_SA_KEY_FILE` (a path), and `fetch_bronze_api.py` now **refuses
  `GCP_SA_KEY_JSON` outright** rather than silently accepting the shape that
  caused the incident.
- `summarize_execution()` replaced the raw `json.dumps(op)` -- every status
  readout selects named fields (counts, conditions) instead of dumping the
  object.
- `roles/secretmanager.secretAccessor` is bound **on the secret**, not
  project-wide, and to Cloud Run's project-local default compute SA
  (`919371925869-compute@developer.gserviceaccount.com`) -- the job's actual
  runtime identity, since the org-policy block on cross-project
  `iam.serviceAccounts.actAs` means it cannot run as `claude-agent@`.

**Two outstanding asks, both confirmed live rather than assumed** (a
`preflight()` check re-verifies both and refuses to run, so no
half-created secret is left behind):

1. **Enable `secretmanager.googleapis.com` on `msbai-capstone-nb4603`** --
   the API is not enabled at all; every call 403s with "has not been used in
   project ... before or it is disabled." This is separate from IAM, and is
   the same enable-then-wait-for-propagation step `cloudbuild` and `run`
   each needed here.
2. **Grant `roles/secretmanager.admin`** on `msbai-capstone-nb4603` to
   `claude-agent@msbai-dwd-nb4603.iam.gserviceaccount.com`.
   `testIamPermissions` returns all five needed permissions as missing:
   `secrets.create`, `secrets.get`, `versions.add`, `secrets.getIamPolicy`,
   `secrets.setIamPolicy`.

**Worth weighing before granting either:** the explicit key may not be
needed at all. It exists only to dodge the cross-project `actAs` block --
but the job already runs as `msbai-capstone-nb4603`'s own compute SA, which
is project-local. Granting *that* SA BigQuery + GCS roles directly would let
`fetch_bronze_api.py` fall back to ambient ADC (already its behaviour when
no key file is present), deleting the secret, the mount, and the key-handling
code path together -- no key to leak, rotate, or mount. That is the smaller
and safer surface; Secret Manager is the right answer only if the fetch must
keep writing as the cross-project `claude-agent@` identity.

## Silver: country-code reconciliation

- Eurostat's `geo` codes match ISO 3166-1 alpha-2 for every country in this
  dataset **except Greece** (Eurostat: `EL`, ISO: `GR`) -- the one real
  reconciliation case, handled via a hand-built `country_reference` table
  rather than a general transliteration rule.
- `EU27_2020` is Eurostat's own 27-member aggregate, not a country -- tagged
  `is_aggregate` rather than filtered out, since the dashboard's EU-aggregate
  trend view needs it; country-level views filter it out explicitly.
- Iceland, Liechtenstein, and Norway are EEA/EFTA members bound by the ELV
  Directive via the EEA Agreement, not EU members -- included in country
  views but tagged `is_eu_member = false`.
- Nulls vs. reported vs. estimated are kept as three independent boolean
  flags (`is_estimated`/`is_imputed`/`is_low_reliability`, from Eurostat's
  `e`/`i`/`u` OBS_FLAG codes) rather than one combined status, since a row
  can be estimated **and** low-reliability at once. First draft used
  `OBS_FLAG = 'e'` directly, which silently evaluates to `NULL` (not
  `FALSE`) for blank flags in SQL -- caught by checking `COUNTIF(is_estimated
  IS NULL)` after the first build, fixed with `COALESCE(..., FALSE)`.

## Silver: the EXP ("exported") category

`env_waselv` carries a `waste` (waste-category) dimension, not just
`wst_oper` (operation). `EXP` ("End-of-life vehicles exported") is a value of
that `waste` dimension, and it cross-cuts **all four** `wst_oper` values
(GEN/DSP/RCV/RCY) rather than standing alongside them as a fifth operation.
Verified by cross-tabulation, not assumed: for a given country/year,
`DSP(EXP) + RCV(EXP) = GEN(EXP)` exactly (e.g. Germany 2006: 215 + 24,644 =
24,859 tonnes). Practical meaning: **a country's reported recycling/recovery
rate can include tonnage that left the EU as an exported vehicle rather than
being physically recycled domestically** -- the operational link to this
capstone's export/leakage side. `elv_silver.elv_detail` preserves the full
(`wst_oper` x `waste`) cross rather than collapsing it, with an
`is_export_lens` boolean marking the `waste = 'EXP'` rows so a future query
doesn't have to re-derive this.

## Gold: targets and anomaly confidence

- `target_met_recycling` / `target_met_recovery` are `NULL` when the
  underlying rate is `NULL` (no data), not `FALSE` -- collapsing "no data"
  into "target missed" would misrepresent countries with late accession or
  reporting gaps (Croatia, Malta, Romania, Iceland) as failing.
- Two anomaly-confidence tiers, not one:
  - **`documented`** -- a verified, sourced cause, hand-authored in
    `elv_gold.documented_anomalies`:
    - **Malta 2023**: reuse+recycling rate dropped from 84.1% (2022) to
      62.8% (2023) -- material stockpiled pending export while awaiting more
      favorable export pricing.
    - **Poland 2019-2020**: rates exceeded 100% (up to 122.2%) -- backlog
      clearing, processing more tonnage in a year than was newly generated.
    - **Denmark 2019-2020**: reuse+recovery rate reached ~102% (recycling
      rate stayed normal) -- the same backlog-clearing mechanism as Poland,
      at much smaller scale.
    - **Greece 2015 and 2019**: rates dropped sharply (to 64.5%/68.9% and
      69.7%/77.2%) -- per Eurostat's End-of-life vehicle statistics
      Statistics Explained article, low scrap-metal prices caused temporary
      stockpiling of material at dismantling facility sites rather than
      processing it. Same stockpiling-for-favorable-pricing mechanism family
      as Malta's 2023 anomaly, triggered by metal prices rather than export
      timing.
    - An earlier draft of the Greece cause included a claim that 2022 was
      "89.1%, up 1 point from 2021." Checked against the loaded data before
      writing it down: 2021 was 91.7%, 2022 was 83.5% (a drop, not a rise),
      and no series has 89.1% in 2022 at all -- 89.0% is the 2023 recycling
      figure. Turned out to be the EU27 aggregate value, not Greece's own.
      Dropped from the note rather than included on trust.
  - **`flagged_undiagnosed`** -- rate > 100% or a > 15-point year-over-year
    swing, noticed in the data (Czechia, Slovenia, Germany 2010-2014,
    Liechtenstein, Iceland, and Greece's own 2016 spike to an exactly-round
    100.0% "estimated" value) but with no verified external cause on record.
    Disclosed as its own category rather than silently folded into the
    4 documented cases or left unflagged at face value.

## Dashboard

- **Baked-in CSV extract**, not a live BigQuery read at app startup --
  `elv_gold.elv_country_year` is 543 rows, trivially small, so baking it in
  removes network/auth latency from every cold start and means the Cloud Run
  service account needs zero BigQuery access at runtime.
- **`st.dataframe()` segfaults reproducibly in this environment** (confirmed
  via `dmesg`: `libarrow.so`, the same failure class as a `pd.read_parquet`
  segfault documented elsewhere in this environment for a different
  project) -- Streamlit's dataframe widget serializes through pyarrow
  internally. Streamlit renders every tab's body on every page load (tabs
  are CSS-hidden, not conditionally executed), so this crashed the whole
  server, not just the one widget. Fixed by rendering the undiagnosed
  -anomalies table as a plain markdown table instead, avoiding pyarrow
  entirely. Verified fixed: the server survived repeated navigation to that
  tab afterward, where it had reliably crashed before.
- **The country map's base geography could not be visually verified from
  this environment.** Plotly's `scope="europe"` choropleth fetches its base
  topology (`europe_110m.json`) from `cdn.plot.ly` client-side, at render
  time, in the viewer's own browser -- confirmed blocked from this sandbox
  specifically (`ERR_TUNNEL_CONNECTION_FAILED` against `cdn.plot.ly`, caught
  via the browser console, not guessed). The chart's data binding and
  colorbar render correctly; the country outlines could not be confirmed
  visually here. Since this fetch happens in the *end user's* browser, not
  through this environment's proxy, it should render normally in production
  -- disclosed rather than claimed as verified, and worth a check from
  outside this environment after deploy (same pattern as the live-URL
  reachability check needed for other dashboards built in this environment).

## Dashboard: multi-year selection (added after initial deploy)

- Country Performance's year control changed from a single `st.selectbox` to
  `st.multiselect`. Single-year selection keeps the original design (bars
  colored by status: pass/fail/documented-anomaly/undiagnosed-anomaly) since
  that's the more common case and status coloring doesn't compose across
  multiple bars per country. Selecting 2+ years switches the bar chart to
  grouped bars colored by **year** instead (fixed categorical palette,
  identity encoding) -- color can't mean two different things (status vs.
  year) on the same chart, so the encoding swaps deliberately rather than
  trying to overload one channel, and the caption discloses the swap.
  Countries are sorted by the most recently selected year's rate so the
  ordering stays stable and meaningful.
- The map tab does not support multiple years (no sensible way to show N
  years on one choropleth without animation, which was out of scope for this
  ask) -- it shows the latest of the selected years, captioned as such.
- Verified locally (Playwright): single-year mode unchanged, multi-year mode
  renders grouped bars with correct sort order and legend, server survived
  navigating both tabs repeatedly (re-checked given the earlier
  `st.dataframe`/pyarrow segfault history in this same app).

## Deployment

- **Local `docker build`/`push` is not an option**: `*.pkg.dev` is blocked by
  this environment's network egress policy (confirmed via `curl`, same
  policy-denial class as the Eurostat block). Built and pushed via the Cloud
  Build API instead, with `storageSource` pointing at a tarball uploaded to
  the GCS staging bucket -- Cloud Build itself runs inside GCP, not through
  this environment's proxy.
- This was a **fresh GCP project** with no pre-existing Cloud Build history,
  Artifact Registry repo, or enabled APIs -- unlike reusing an
  already-set-up project, every one of these had to be discovered and
  requested explicitly rather than assumed present:
  - `cloudbuild.googleapis.com` and `run.googleapis.com` were not yet
    enabled (confirmed via a live 403, "Access Not Configured").
  - No Artifact Registry repository existed yet, and `claude-agent@` lacked
    `artifactregistry.repositories.create` (deliberately not requested, to
    avoid a broader role than needed) -- the repo was created once by the
    project owner instead.
  - After granting `roles/cloudbuild.builds.editor` and
    `roles/artifactregistry.writer`, the first build submission still
    403'd with "Access Not Configured" -- API enablement needed a few
    minutes to propagate before the Cloud Build API itself would accept
    calls, even though IAM `testIamPermissions` already reported the
    permission as granted. Resolved by polling rather than guessing at a
    fixed wait time.
- **Cross-project runtime service account was abandoned, not fought
  through.** The Cloud Run service was initially configured to run as
  `claude-agent@msbai-dwd-nb4603...` (the same identity used for
  BigQuery/GCS), which needs `iam.serviceaccounts.actAs` granted on that SA
  resource. The project owner bound the role directly on the SA (confirmed
  applied, screenshot showed a fresh `etag`/`version: 1`), but the deploy
  kept 403ing on `actAs` for over 10 consecutive retries across 5 minutes --
  too long and too consistent for ordinary IAM propagation delay, and a
  strong signal of a cross-project service-account restriction enforced at
  the org level (common as a default on newer GCP organizations), which a
  project-level IAM binding cannot override. Rather than escalate further
  (e.g. asking an org admin to change an org policy), reconsidered whether
  the cross-project identity was even necessary: the dashboard makes **zero**
  GCP API calls at runtime (it reads the baked-in CSV extract), so it has no
  actual need to run as `claude-agent@` at all. Dropped the explicit
  `serviceAccount` field entirely and let Cloud Run default to
  `msbai-capstone-nb4603`'s own project-local compute service account
  (confirmed to already exist and be usable, since Cloud Build had used it
  automatically for the image build) -- deployed successfully on the next
  attempt. General lesson: a cross-project identity should be a deliberate
  choice tied to an actual runtime need, not a default carried over from
  the pipeline stages that came before it.
- **Public reachability could not be verified from this environment.**
  `*.run.app` is blocked by this environment's network egress policy at the
  proxy CONNECT level (confirmed via `curl`, same policy-denial class as the
  Eurostat and Artifact Registry blocks) -- this is a restriction on this
  build sandbox specifically, not on the deployed service or its real
  visitors. `roles/run.invoker` -> `allUsers` was bound successfully
  (confirmed via the `setIamPolicy` response); actual reachability needs to
  be checked from outside this environment.
