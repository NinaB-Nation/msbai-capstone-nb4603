"""Runs the Silver-layer SQL (reference table + cleaned views) in order."""
import os
import sys

from google.cloud import bigquery

PROJECT = "msbai-capstone-nb4603"
SQL_DIR = os.path.join(os.path.dirname(__file__), "sql")

STATEMENTS = [
    "silver_country_reference.sql",
    "silver_code_reference.sql",
    "silver_elv_totals.sql",
    "silver_elv_detail.sql",
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
