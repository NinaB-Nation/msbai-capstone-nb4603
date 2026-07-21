"""Runs the Gold-layer SQL (documented-anomaly reference + final country-year table)."""
import os
import sys

from google.cloud import bigquery

PROJECT = "msbai-capstone-nb4603"
SQL_DIR = os.path.join(os.path.dirname(__file__), "sql")

STATEMENTS = [
    "gold_documented_anomalies.sql",
    "gold_elv_country_year.sql",
]


def main():
    client = bigquery.Client(project=PROJECT)
    for filename in STATEMENTS:
        path = os.path.join(SQL_DIR, filename)
        with open(path) as f:
            sql = f.read()
        print(f"running {filename} ...")
        client.query(sql).result()
        print(f"  done")


if __name__ == "__main__":
    sys.exit(main())
