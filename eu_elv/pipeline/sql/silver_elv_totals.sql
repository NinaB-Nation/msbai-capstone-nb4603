-- Silver: cleaned, typed, tidy view over env_waselvt_raw (ELV totals by
-- country/year/operation/unit). Eurostat's SDMX-CSV "linear" export is
-- already one row per (geo, year, wst_oper, unit) -- long/tidy -- so there
-- is no wide-year-columns layout to pivot here.
--
-- Nulls vs reported vs estimated are kept distinct via three independent
-- boolean flags (a row can be estimated AND low-reliability at once):
--   is_estimated        OBS_FLAG = 'e' (Eurostat/country estimate)
--   is_imputed          OBS_FLAG = 'i' (value imputed by Eurostat)
--   is_low_reliability  OBS_FLAG = 'u' (flagged low reliability)
-- A true missing value (no row at all for a geo/year/operation combo) is
-- surfaced by absence, not by a NULL obs_value -- every row in Bronze has a
-- non-null OBS_VALUE (verified: 0 blank OBS_VALUE rows in the raw extract).
CREATE OR REPLACE VIEW `msbai-capstone-nb4603.elv_silver.elv_totals` AS
SELECT
  r.geo AS country_code_eurostat,
  c.iso_alpha2 AS country_code_iso,
  c.country_name,
  c.is_eu_member,
  c.is_aggregate,
  CAST(r.TIME_PERIOD AS INT64) AS year,
  r.wst_oper AS operation_code,
  r.waste_management_operations AS operation_label,
  r.unit AS unit_code,
  r.unit_of_measure AS unit_label,
  SAFE_CAST(r.OBS_VALUE AS FLOAT64) AS obs_value,
  COALESCE(r.OBS_FLAG = 'e', FALSE) AS is_estimated,
  COALESCE(r.OBS_FLAG = 'i', FALSE) AS is_imputed,
  COALESCE(r.OBS_FLAG = 'u', FALSE) AS is_low_reliability,
  r.OBS_FLAG AS obs_flag_raw,
  r.obs_flag_label
FROM `msbai-capstone-nb4603.elv_bronze.env_waselvt_raw` r
LEFT JOIN `msbai-capstone-nb4603.elv_silver.country_reference` c
  ON r.geo = c.geo_code;
