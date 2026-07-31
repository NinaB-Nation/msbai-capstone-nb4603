-- Silver: code -> label lookup, sourced from Eurostat's own SDMX codelists
-- (elv_bronze.codelists_api, loaded by fetch_bronze_api.py from the DSD).
--
-- Why this exists: the SDMX data endpoint returns codes and never labels.
-- Four probe rounds against the live API confirmed no parameter changes
-- that -- format=SDMX-CSV2.0 is rejected outright, labels/label/lang are
-- silently ignored, and dropping the format param yields SDMX-ML rather
-- than labelled CSV (see DECISIONS.md). The manual databrowser export
-- inlined labels; the API expects the consumer to resolve them.
--
-- So labels are resolved here instead, which is the better shape anyway:
-- one row per (codelist, code) rather than a label string repeated across
-- all 30,268 observations, and the same pattern country_reference already
-- uses for geo.
--
-- Verified before cutover: all 29 distinct codes actually used by the ELV
-- datasets resolve to labels byte-identical to the ones the databrowser
-- export carried -- no casing or punctuation drift.
--
-- DISTINCT is load-bearing, not defensive tidiness: a duplicated
-- (codelist_id, code) would fan out every joining row in elv_totals and
-- elv_detail and silently inflate the observation counts.
CREATE OR REPLACE VIEW `msbai-capstone-nb4603.elv_silver.code_reference` AS
SELECT DISTINCT
  codelist_id,
  code,
  label
FROM `msbai-capstone-nb4603.elv_bronze.codelists_api`;
