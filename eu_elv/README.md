# EU End-of-Life Vehicle (ELV) Recycling Pipeline

EU-region initial data analysis for the Global ELV Recycling Gap capstone:
Eurostat End-of-Life Vehicle statistics, cleaned through a Bronze -> Silver
-> Gold pipeline in BigQuery, explored via a public Streamlit dashboard on
Cloud Run.

## Data sources

- **env_waselvt** -- ELV totals: count, weight, reuse/recycling rate,
  reuse/recovery rate by country, 2005-2023.
- **env_waselv** -- detailed breakdown by waste-management operation,
  including an `EXP` waste category (weight of vehicles exported) --
  see DECISIONS.md for how this connects to the export/leakage side of the
  broader capstone.

Eurostat's own API (`ec.europa.eu`) is blocked by this environment's network
egress policy, so both source files were exported manually from Eurostat's
databrowser (SDMX-CSV, "linear" format) and loaded as-is into Bronze.

## BigQuery inventory

Project: **`msbai-capstone-nb4603`**

| Layer | Object | Type | Description |
|---|---|---|---|
| Bronze | `elv_bronze.env_waselvt_raw` | TABLE | Raw env_waselvt, every column STRING, unmodified |
| Bronze | `elv_bronze.env_waselv_raw` | TABLE | Raw env_waselv, every column STRING, unmodified |
| Silver | `elv_silver.country_reference` | TABLE | Hand-built Eurostat-geo -> ISO reconciliation |
| Silver | `elv_silver.elv_totals` | VIEW | Typed, country-reconciled env_waselvt |
| Silver | `elv_silver.elv_detail` | VIEW | Typed, country-reconciled env_waselv, with `is_export_lens` |
| Gold | `elv_gold.documented_anomalies` | TABLE | Hand-authored, verified-cause anomaly notes |
| Gold | `elv_gold.elv_country_year` | TABLE | One row per country per year: rates, targets, anomaly flags |

GCS staging bucket: `msbai-capstone-nb4603-eu-elv-staging` (EU multi-region).

## Reproducing

```bash
cd pipeline
pip install -r requirements.txt   # or use the .venv this was built with
python load_bronze.py             # lands data_raw/*.csv in GCS, loads Bronze
python build_silver.py            # builds Silver reference table + views
python build_gold.py              # builds Gold documented-anomalies + elv_country_year

cd ../dashboard
python build_extract.py           # bakes elv_gold.elv_country_year into data/elv_country_year.csv
streamlit run app.py              # reads the baked-in extract, no BigQuery needed
```

## Dashboard

**https://eu-elv-dashboard-57ndvlnytq-uc.a.run.app**

Reuse/recycling/recovery performance by country, an EU-aggregate trend view,
a flagged-anomalies panel (documented causes + generic undiagnosed outliers),
and a methodology panel. See DECISIONS.md for the full design rationale.

Public reachability could not be verified from the environment this was
built in (`*.run.app` is blocked by its network egress policy) -- confirm
from an outside network if in doubt.
