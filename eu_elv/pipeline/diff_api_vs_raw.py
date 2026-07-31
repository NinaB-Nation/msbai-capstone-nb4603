"""
Value-level diff: elv_bronze.*_api (automated Eurostat API pull) vs.
elv_bronze.*_raw (hand-verified manual databrowser export).

Row counts already matched (4,305 / 30,268) after the first API run, but a
row count is not a value check -- two tables can agree on cardinality and
disagree on every observation. This compares the tables cell by cell.

The two loads do NOT have the same schema, so the diff is over the columns
they share rather than over `SELECT *`:

  shared (diffable): freq, wst_oper, [waste,] unit, geo, TIME_PERIOD,
                     OBS_VALUE, OBS_FLAG, CONF_STATUS
  _raw only:         STRUCTURE, STRUCTURE_ID, STRUCTURE_NAME, and the eight
                     human-readable label columns (time_frequency,
                     waste_management_operations, waste_label,
                     unit_of_measure, geo_label, time_label,
                     observation_value_label, obs_flag_label,
                     conf_status_label)
  _api only:         DATAFLOW, LAST UPDATE

The first six shared columns form the natural key (one row per
observation); the last three are the measures. Key uniqueness is asserted
rather than assumed -- a duplicated key would silently fan out the join and
turn a real mismatch into a passing diff.

CONF_STATUS is 100% NULL in all four tables, so its zero-diff is vacuous --
it agrees trivially and the negative control cannot move it. It is still
compared (a future reload could start populating it), but OBS_VALUE and
OBS_FLAG are the only measures carrying real signal here.

NEGATIVE CONTROL: a diff that reports zero differences is indistinguishable
from a diff that is not actually comparing anything (wrong join column,
all-NULL measure, empty table). So the script also runs the same comparison
against a deliberately corrupted copy of the API side (TIME_PERIOD shifted
by one year) and requires that it *does* report differences. If the control
comes back clean, the diff is broken and the run fails loudly instead of
reporting a false all-clear.
"""
import sys

from google.cloud import bigquery

PROJECT = "msbai-capstone-nb4603"
DATASET = "elv_bronze"
FQ = f"{PROJECT}.{DATASET}"

DATASETS = [
    ("env_waselvt", ["freq", "wst_oper", "unit", "geo", "TIME_PERIOD"]),
    ("env_waselv", ["freq", "wst_oper", "waste", "unit", "geo", "TIME_PERIOD"]),
]
MEASURES = ["OBS_VALUE", "OBS_FLAG", "CONF_STATUS"]


def assert_key_unique(bq, table, keycols):
    key = ", ".join(keycols)
    row = next(iter(bq.query(
        f"SELECT COUNT(*) n, COUNT(DISTINCT TO_JSON_STRING([{key}])) d "
        f"FROM `{FQ}.{table}`"
    ).result()))
    if row.n != row.d:
        raise RuntimeError(
            f"{table}: natural key is not unique ({row.n:,} rows, {row.d:,} "
            f"distinct keys) -- the join would fan out and the diff would be "
            f"meaningless"
        )
    print(f"  {table:20s} {row.n:>7,} rows, key unique")
    return row.n


def diff(bq, base, keycols, api_sql=None, label="diff"):
    """FULL OUTER JOIN _raw against _api on the natural key.

    api_sql lets the negative control substitute a corrupted API side while
    reusing this exact comparison logic -- the control has to exercise the
    real code path to prove anything about it.
    """
    api_src = api_sql or f"SELECT * FROM `{FQ}.{base}_api`"
    on = " AND ".join(f"r.{c} = a.{c}" for c in keycols)
    # geo is part of the key and never NULL within a row, so a NULL on one
    # side of the FULL OUTER JOIN means that side had no matching row.
    measure_counts = ",\n      ".join(
        f"COUNTIF(both_sides AND r_{m} IS DISTINCT FROM a_{m}) AS {m.lower()}_diff"
        for m in MEASURES
    )
    measure_sel = ",\n             ".join(
        f"r.{m} AS r_{m}, a.{m} AS a_{m}" for m in MEASURES
    )
    q = f"""
    WITH api AS ({api_src}),
    j AS (
      SELECT {measure_sel},
             r.geo IS NOT NULL AND a.geo IS NOT NULL AS both_sides,
             r.geo IS NULL AS only_api,
             a.geo IS NULL AS only_raw
      FROM `{FQ}.{base}_raw` r
      FULL OUTER JOIN api a ON {on}
    )
    SELECT
      COUNTIF(only_raw) AS keys_only_in_raw,
      COUNTIF(only_api) AS keys_only_in_api,
      COUNTIF(both_sides) AS keys_matched,
      {measure_counts},
      COUNTIF(both_sides
              AND SAFE_CAST(r_OBS_VALUE AS FLOAT64)
                  IS DISTINCT FROM SAFE_CAST(a_OBS_VALUE AS FLOAT64))
        AS obs_value_numeric_diff
    FROM j
    """
    row = next(iter(bq.query(q).result()))
    print(f"  [{label}] {base}_raw vs {base}_api")
    for field in row.keys():
        print(f"      {field:26s} {row[field]:>8,}")
    return row


def total_differences(row):
    return (row.keys_only_in_raw + row.keys_only_in_api
            + sum(row[f"{m.lower()}_diff"] for m in MEASURES)
            + row.obs_value_numeric_diff)


def main():
    bq = bigquery.Client(project=PROJECT)
    failures = []

    for base, keycols in DATASETS:
        print(f"\n=== {base} ===")

        print("  -- key uniqueness --")
        for suffix in ("raw", "api"):
            assert_key_unique(bq, f"{base}_{suffix}", keycols)

        print("  -- real diff --")
        real = diff(bq, base, keycols, label="real")
        if total_differences(real) != 0:
            failures.append(f"{base}: {total_differences(real):,} differences")

        # Shift TIME_PERIOD by one year on the API side. Every observation
        # then lines up against a different year's value, so a working diff
        # must report both unmatched keys and value mismatches.
        print("  -- negative control (API TIME_PERIOD shifted +1y) --")
        corrupted = (
            f"SELECT * EXCEPT(TIME_PERIOD), "
            f"CAST(CAST(TIME_PERIOD AS INT64) + 1 AS STRING) AS TIME_PERIOD "
            f"FROM `{FQ}.{base}_api`"
        )
        control = diff(bq, base, keycols, api_sql=corrupted, label="control")
        if total_differences(control) == 0:
            failures.append(
                f"{base}: NEGATIVE CONTROL PASSED CLEAN -- the diff is not "
                f"actually comparing anything; the all-clear above is void"
            )

    print()
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("All shared columns identical in both datasets; "
          "negative control confirmed the diff has teeth.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
