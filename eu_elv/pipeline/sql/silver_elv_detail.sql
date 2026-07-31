-- Silver: cleaned, typed, tidy view over env_waselv_api (detailed ELV
-- breakdown by waste-management operation AND waste category, all in
-- tonnes). This is the dataset that carries the EXP ("End-of-life vehicles
-- exported") category.
--
-- EXP lives in the `waste` (waste category) dimension, not `wst_oper` --
-- confirmed by cross-tabulating: for a given country/year, DSP(EXP) +
-- RCV(EXP) = GEN(EXP) exactly (e.g. Germany 2006: 215 + 24644 = 24859
-- tonnes), i.e. Eurostat reports how the *exported* tonnage is itself
-- allocated across operations, not "export" as a same-level alternative to
-- "recycled"/"recovered"/"disposed". Concretely, this means a country's
-- reported recycling/recovery rate can include tonnage that left the EU as
-- an exported vehicle rather than being physically recycled domestically --
-- the operational fact that links to the export/leakage side of this
-- capstone. `is_export_lens` marks these rows so downstream queries can
-- filter to them without re-deriving the join logic.
CREATE OR REPLACE VIEW `msbai-capstone-nb4603.elv_silver.elv_detail` AS
SELECT
  r.geo AS country_code_eurostat,
  c.iso_alpha2 AS country_code_iso,
  c.country_name,
  c.is_eu_member,
  c.is_aggregate,
  CAST(r.TIME_PERIOD AS INT64) AS year,
  r.wst_oper AS operation_code,
  op.label AS operation_label,
  r.waste AS waste_category_code,
  wc.label AS waste_category_label,
  r.waste = 'EXP' AS is_export_lens,
  r.unit AS unit_code,
  un.label AS unit_label,
  SAFE_CAST(r.OBS_VALUE AS FLOAT64) AS obs_value_tonnes,
  COALESCE(r.OBS_FLAG = 'e', FALSE) AS is_estimated,
  COALESCE(r.OBS_FLAG = 'i', FALSE) AS is_imputed,
  COALESCE(r.OBS_FLAG = 'u', FALSE) AS is_low_reliability,
  COALESCE(r.OBS_FLAG = 'p', FALSE) AS is_provisional,
  r.OBS_FLAG AS obs_flag_raw,
  fl.label AS obs_flag_label
FROM `msbai-capstone-nb4603.elv_bronze.env_waselv_api` r
LEFT JOIN `msbai-capstone-nb4603.elv_silver.country_reference` c
  ON r.geo = c.geo_code
LEFT JOIN `msbai-capstone-nb4603.elv_silver.code_reference` op
  ON op.codelist_id = 'WST_OPER' AND op.code = r.wst_oper
LEFT JOIN `msbai-capstone-nb4603.elv_silver.code_reference` wc
  ON wc.codelist_id = 'WASTE' AND wc.code = r.waste
LEFT JOIN `msbai-capstone-nb4603.elv_silver.code_reference` un
  ON un.codelist_id = 'UNIT' AND un.code = r.unit
LEFT JOIN `msbai-capstone-nb4603.elv_silver.code_reference` fl
  ON fl.codelist_id = 'OBS_FLAG' AND fl.code = r.OBS_FLAG;
