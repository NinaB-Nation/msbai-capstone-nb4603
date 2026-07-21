"""
Bakes elv_gold.elv_country_year into a CSV the Streamlit app reads directly,
so Cloud Run never needs BigQuery access at runtime (same reasoning as the
Bronze/Silver/Gold pipeline's data volume: 543 rows, trivially small -- no
argument for a live query per page load). Re-run this and redeploy whenever
elv_gold.elv_country_year changes.
"""
import os
import sys

from google.cloud import bigquery

PROJECT = "msbai-capstone-nb4603"
OUT_PATH = os.path.join(os.path.dirname(__file__), "data", "elv_country_year.csv")


def main():
    client = bigquery.Client(project=PROJECT)
    df = client.query(f"""
        SELECT *
        FROM `{PROJECT}.elv_gold.elv_country_year`
        ORDER BY country_code_eurostat, year
    """).to_dataframe()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"wrote {len(df):,} rows -> {OUT_PATH}")


if __name__ == "__main__":
    sys.exit(main())
