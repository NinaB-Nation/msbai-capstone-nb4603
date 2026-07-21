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
