"""
Bronze layer loader: lands raw Eurostat SDMX-CSV exports in GCS (durable
staging, independent of Eurostat's own availability), then loads them into
BigQuery unmodified -- every column as STRING, no parsing/casting/renaming.
Cleaning happens in Silver, not here.

Source: manually exported from the Eurostat databrowser (this environment's
network egress policy blocks ec.europa.eu, so the live SDMX/REST API could
not be pulled directly -- see DECISIONS.md).
"""
import datetime
import os
import sys

from google.cloud import bigquery, storage

PROJECT = "msbai-capstone-nb4603"
BUCKET = "msbai-capstone-nb4603-eu-elv-staging"
BRONZE_DATASET = "elv_bronze"

DATASETS = {
    "env_waselvt": {
        "local_path": os.path.join(os.path.dirname(__file__), "data_raw", "env_waselvt_linear_2_0.csv"),
        "gcs_path": "bronze/env_waselvt/env_waselvt_linear_2_0.csv",
        "table": "env_waselvt_raw",
    },
    "env_waselv": {
        "local_path": os.path.join(os.path.dirname(__file__), "data_raw", "env_waselv_linear_2_0.csv"),
        "gcs_path": "bronze/env_waselv/env_waselv_linear_2_0.csv",
        "table": "env_waselv_raw",
    },
}

# Eurostat's SDMX-CSV "linear" export header -- identical shape for both
# datasets except env_waselv has the extra `waste` (waste category) dimension.
SCHEMAS = {
    "env_waselvt_raw": [
        "STRUCTURE", "STRUCTURE_ID", "STRUCTURE_NAME", "freq", "time_frequency",
        "wst_oper", "waste_management_operations", "unit", "unit_of_measure",
        "geo", "geo_label", "TIME_PERIOD", "time_label", "OBS_VALUE",
        "observation_value_label", "OBS_FLAG", "obs_flag_label",
        "CONF_STATUS", "conf_status_label",
    ],
    "env_waselv_raw": [
        "STRUCTURE", "STRUCTURE_ID", "STRUCTURE_NAME", "freq", "time_frequency",
        "wst_oper", "waste_management_operations", "waste", "waste_label",
        "unit", "unit_of_measure", "geo", "geo_label", "TIME_PERIOD",
        "time_label", "OBS_VALUE", "observation_value_label", "OBS_FLAG",
        "obs_flag_label", "CONF_STATUS", "conf_status_label",
    ],
}


def upload_to_gcs(storage_client, local_path, gcs_path):
    bucket = storage_client.bucket(BUCKET)
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(local_path)
    uri = f"gs://{BUCKET}/{gcs_path}"
    print(f"  landed {local_path} -> {uri} ({blob.size:,} bytes)")
    return uri


def load_to_bronze(bq_client, uri, table_name):
    dataset_ref = bigquery.DatasetReference(PROJECT, BRONZE_DATASET)
    table_ref = dataset_ref.table(table_name)

    schema = [bigquery.SchemaField(col, "STRING") for col in SCHEMAS[table_name]]
    schema.append(bigquery.SchemaField("_source_uri", "STRING"))
    schema.append(bigquery.SchemaField("_loaded_at", "TIMESTAMP"))

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        schema=schema[:-2],  # source file doesn't carry the metadata columns
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        allow_quoted_newlines=True,
    )
    load_job = bq_client.load_table_from_uri(uri, table_ref, job_config=job_config)
    load_job.result()

    table = bq_client.get_table(table_ref)
    print(f"  loaded {uri} -> {PROJECT}.{BRONZE_DATASET}.{table_name} ({table.num_rows:,} rows)")

    # Backfill ingestion metadata now that the raw columns are in place.
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    bq_client.query(f"""
        ALTER TABLE `{PROJECT}.{BRONZE_DATASET}.{table_name}`
        ADD COLUMN IF NOT EXISTS _source_uri STRING,
        ADD COLUMN IF NOT EXISTS _loaded_at TIMESTAMP
    """).result()
    bq_client.query(f"""
        UPDATE `{PROJECT}.{BRONZE_DATASET}.{table_name}`
        SET _source_uri = @uri, _loaded_at = @loaded_at
        WHERE _source_uri IS NULL
    """, job_config=bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("uri", "STRING", uri),
        bigquery.ScalarQueryParameter("loaded_at", "TIMESTAMP", now),
    ])).result()


def main():
    storage_client = storage.Client(project=PROJECT)
    bq_client = bigquery.Client(project=PROJECT)

    for name, cfg in DATASETS.items():
        print(f"{name}:")
        uri = upload_to_gcs(storage_client, cfg["local_path"], cfg["gcs_path"])
        load_to_bronze(bq_client, uri, cfg["table"])


if __name__ == "__main__":
    sys.exit(main())
