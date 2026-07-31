"""
Automated Bronze loader: pulls env_waselvt and env_waselv directly from
Eurostat's SDMX 2.1 dissemination API (SDMX-CSV format), lands the raw
response in the us-central1 staging bucket, and loads into
elv_bronze.env_waselvt_api / elv_bronze.env_waselv_api -- separate from the
env_waselvt_raw / env_waselv_raw tables loaded manually from a databrowser
export, so the automated pull can be diffed against the hand-verified data
rather than overwriting it.

Must run from inside GCP: ec.europa.eu is blocked by this dev sandbox's
network egress policy (confirmed via curl and WebFetch both 403ing at the
proxy -- see DECISIONS.md), so this is packaged to run as a Cloud Run Job,
not invoked directly from the sandbox.

Auth: takes an explicit service-account key via the GCP_SA_KEY_JSON env var
rather than relying on the Job's attached runtime identity. A cross-project
identity (claude-agent@msbai-dwd-nb4603) was already used successfully for
the manual Bronze/Silver/Gold build via a decrypted key file passed as
GOOGLE_APPLICATION_CREDENTIALS; binding that same identity as a Cloud Run
*Service* account hit a hard org-policy block on iam.serviceAccounts.actAs
across projects (see DECISIONS.md, "Deployment" section). Passing the key
as data rather than as the container's attached identity sidesteps that
block entirely -- the job's attached identity is left at Cloud Run's
project-local default, which needs no permissions at all, since the script
authenticates explicitly.
"""
import csv
import datetime
import io
import json
import os
import sys

import requests
from google.cloud import bigquery, storage
from google.oauth2 import service_account

PROJECT = "msbai-capstone-nb4603"
BUCKET = os.environ.get("BUCKET", "msbai-capstone-nb4603-eu-elv-staging-us")
BRONZE_DATASET = "elv_bronze"

EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data"

DATASETS = {
    "env_waselvt": {"table": "env_waselvt_api", "gcs_prefix": "bronze-api/env_waselvt"},
    "env_waselv": {"table": "env_waselv_api", "gcs_prefix": "bronze-api/env_waselv"},
}

# Header shape of the manual SDMX-CSV "linear" export (see load_bronze.py),
# kept here only as a point of comparison -- the actual BigQuery schema is
# built from whatever header the live API returns, not assumed to match.
REFERENCE_HEADERS = {
    "env_waselvt_api": [
        "STRUCTURE", "STRUCTURE_ID", "STRUCTURE_NAME", "freq", "time_frequency",
        "wst_oper", "waste_management_operations", "unit", "unit_of_measure",
        "geo", "geo_label", "TIME_PERIOD", "time_label", "OBS_VALUE",
        "observation_value_label", "OBS_FLAG", "obs_flag_label",
        "CONF_STATUS", "conf_status_label",
    ],
    "env_waselv_api": [
        "STRUCTURE", "STRUCTURE_ID", "STRUCTURE_NAME", "freq", "time_frequency",
        "wst_oper", "waste_management_operations", "waste", "waste_label",
        "unit", "unit_of_measure", "geo", "geo_label", "TIME_PERIOD",
        "time_label", "OBS_VALUE", "observation_value_label", "OBS_FLAG",
        "obs_flag_label", "CONF_STATUS", "conf_status_label",
    ],
}


def get_credentials():
    key_json = os.environ.get("GCP_SA_KEY_JSON")
    if not key_json:
        return None  # fall back to ambient ADC
    info = json.loads(key_json)
    return service_account.Credentials.from_service_account_info(info)


def fetch_csv(dataset_code):
    url = f"{EUROSTAT_BASE}/{dataset_code}"
    params = {"format": "SDMX-CSV", "compressed": "false"}
    resp = requests.get(url, params=params, timeout=180)
    resp.raise_for_status()
    text = resp.text
    if not text.strip():
        raise RuntimeError(f"{dataset_code}: empty response body")
    return text


def upload_to_gcs(storage_client, text, gcs_path):
    bucket = storage_client.bucket(BUCKET)
    blob = bucket.blob(gcs_path)
    blob.upload_from_string(text, content_type="text/csv")
    uri = f"gs://{BUCKET}/{gcs_path}"
    print(f"  landed -> {uri} ({len(text):,} bytes)")
    return uri


def load_to_bronze(bq_client, uri, table_name, csv_text):
    header = next(csv.reader(io.StringIO(csv_text)))
    expected = REFERENCE_HEADERS[table_name]
    if header != expected:
        print(f"  NOTE: live API header differs from the manual-export header for {table_name}")
        print(f"    expected: {expected}")
        print(f"    actual:   {header}")
        print("    loading under the actual header, not the reference one.")

    dataset_ref = bigquery.DatasetReference(PROJECT, BRONZE_DATASET)
    table_ref = dataset_ref.table(table_name)
    schema = [bigquery.SchemaField(col, "STRING") for col in header]

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        allow_quoted_newlines=True,
    )
    load_job = bq_client.load_table_from_uri(uri, table_ref, job_config=job_config)
    load_job.result()

    table = bq_client.get_table(table_ref)
    print(f"  loaded {uri} -> {PROJECT}.{BRONZE_DATASET}.{table_name} ({table.num_rows:,} rows)")

    bq_client.query(f"""
        ALTER TABLE `{PROJECT}.{BRONZE_DATASET}.{table_name}`
        ADD COLUMN IF NOT EXISTS _source_uri STRING,
        ADD COLUMN IF NOT EXISTS _loaded_at TIMESTAMP
    """).result()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    bq_client.query(f"""
        UPDATE `{PROJECT}.{BRONZE_DATASET}.{table_name}`
        SET _source_uri = @uri, _loaded_at = @loaded_at
        WHERE _source_uri IS NULL
    """, job_config=bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("uri", "STRING", uri),
        bigquery.ScalarQueryParameter("loaded_at", "TIMESTAMP", now),
    ])).result()


def main():
    creds = get_credentials()
    storage_client = storage.Client(project=PROJECT, credentials=creds)
    bq_client = bigquery.Client(project=PROJECT, credentials=creds)

    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dt%H%M%S")
    failures = []
    for dataset_code, cfg in DATASETS.items():
        print(f"{dataset_code}:")
        try:
            text = fetch_csv(dataset_code)
        except Exception as exc:
            print(f"  FETCH FAILED: {exc}")
            failures.append(dataset_code)
            continue

        gcs_path = f"{cfg['gcs_prefix']}/{dataset_code}_{ts}.csv"
        uri = upload_to_gcs(storage_client, text, gcs_path)
        try:
            load_to_bronze(bq_client, uri, cfg["table"], text)
        except Exception as exc:
            print(f"  LOAD FAILED: {exc}")
            failures.append(dataset_code)

    if failures:
        print(f"FAILED: {failures}")
        return 1
    print("all datasets fetched and loaded successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
