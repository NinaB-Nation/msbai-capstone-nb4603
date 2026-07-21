-- Gold: one row per (country, year) -- the grain the dashboard reads
-- directly. EU27_2020 (is_aggregate = TRUE) is kept as its own row rather
-- than filtered out, since the dashboard's EU-aggregate trend view needs
-- it; country-level views filter on is_aggregate = FALSE.
--
-- target_met_recycling / target_met_recovery are NULL when the underlying
-- rate is NULL (no data), not FALSE -- "no data" and "target missed" are
-- different facts and collapsing them would misrepresent coverage gaps
-- (e.g. Croatia/Malta/Romania/Iceland's pre-accession or late-reporting
-- years, see country_reference / DECISIONS.md) as failures.
--
-- anomaly_type distinguishes two confidence levels:
--   'documented'          verified cause, see documented_anomalies table
--   'flagged_undiagnosed' rate > 100% or a >15-point year-over-year swing,
--                         noticed in the data but not independently
--                         investigated -- disclosed rather than silently
--                         presented at face value or silently dropped.
CREATE OR REPLACE TABLE `msbai-capstone-nb4603.elv_gold.elv_country_year` AS
WITH pivoted AS (
  SELECT
    country_code_eurostat,
    country_code_iso,
    country_name,
    is_eu_member,
    is_aggregate,
    year,
    MAX(IF(operation_code = 'RCY_REU' AND unit_code = 'PC', obs_value, NULL)) AS reuse_recycling_rate,
    MAX(IF(operation_code = 'RCV_REU' AND unit_code = 'PC', obs_value, NULL)) AS reuse_recovery_rate,
    MAX(IF(operation_code = 'GEN' AND unit_code = 'NR', obs_value, NULL)) AS elv_count,
    MAX(IF(operation_code = 'GEN' AND unit_code = 'T', obs_value, NULL)) AS elv_weight_tonnes,
    LOGICAL_OR(is_estimated) AS any_estimated,
    LOGICAL_OR(is_imputed) AS any_imputed,
    LOGICAL_OR(is_low_reliability) AS any_low_reliability
  FROM `msbai-capstone-nb4603.elv_silver.elv_totals`
  GROUP BY 1, 2, 3, 4, 5, 6
),
with_prev AS (
  SELECT
    p.*,
    LAG(reuse_recycling_rate) OVER (PARTITION BY country_code_eurostat ORDER BY year) AS prev_recycling_rate,
    LAG(reuse_recovery_rate) OVER (PARTITION BY country_code_eurostat ORDER BY year) AS prev_recovery_rate
  FROM pivoted p
),
flagged AS (
  SELECT
    w.*,
    (
      w.reuse_recycling_rate > 100 OR w.reuse_recovery_rate > 100
      OR ABS(w.reuse_recycling_rate - w.prev_recycling_rate) > 15
      OR ABS(w.reuse_recovery_rate - w.prev_recovery_rate) > 15
    ) AS looks_anomalous
  FROM with_prev w
)
SELECT
  f.country_code_eurostat,
  f.country_code_iso,
  f.country_name,
  f.is_eu_member,
  f.is_aggregate,
  f.year,
  f.reuse_recycling_rate,
  f.reuse_recovery_rate,
  f.reuse_recycling_rate >= 85 AS target_met_recycling,
  f.reuse_recovery_rate >= 95 AS target_met_recovery,
  (f.reuse_recycling_rate >= 85 AND f.reuse_recovery_rate >= 95) AS target_met,
  CAST(ROUND(f.elv_count) AS INT64) AS elv_count,
  f.elv_weight_tonnes,
  f.any_estimated,
  f.any_imputed,
  f.any_low_reliability,
  CASE
    WHEN d.country_code_iso IS NOT NULL THEN 'documented'
    WHEN f.looks_anomalous THEN 'flagged_undiagnosed'
    ELSE NULL
  END AS anomaly_type,
  COALESCE(
    d.cause_note,
    IF(f.looks_anomalous, 'Rate exceeds 100% or shows a large year-over-year swing; not independently investigated.', NULL)
  ) AS anomaly_note
FROM flagged f
LEFT JOIN `msbai-capstone-nb4603.elv_gold.documented_anomalies` d
  ON f.country_code_iso = d.country_code_iso AND f.year = d.year;
