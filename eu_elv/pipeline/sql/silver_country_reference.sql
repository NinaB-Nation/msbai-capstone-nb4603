-- Hand-built reference table, not derived from Eurostat data. Eurostat's
-- `geo` codes match ISO 3166-1 alpha-2 for every country in this dataset
-- except Greece (Eurostat: EL, ISO: GR) -- the one real reconciliation case.
-- EU27_2020 is a Eurostat supranational aggregate, not a country: it has no
-- ISO code and is tagged is_aggregate so downstream country-level views can
-- exclude it without a hardcoded filter list. IS/LI/NO are EEA/EFTA members
-- bound by the ELV Directive via the EEA Agreement, not EU members --
-- tagged is_eu_member = false so the dashboard can distinguish them.
CREATE OR REPLACE TABLE `msbai-capstone-nb4603.elv_silver.country_reference` AS
SELECT * FROM UNNEST([
  STRUCT('AT' AS geo_code, 'AT' AS iso_alpha2, 'Austria' AS country_name, TRUE AS is_eu_member, FALSE AS is_aggregate),
  ('BE', 'BE', 'Belgium', TRUE, FALSE),
  ('BG', 'BG', 'Bulgaria', TRUE, FALSE),
  ('CY', 'CY', 'Cyprus', TRUE, FALSE),
  ('CZ', 'CZ', 'Czechia', TRUE, FALSE),
  ('DE', 'DE', 'Germany', TRUE, FALSE),
  ('DK', 'DK', 'Denmark', TRUE, FALSE),
  ('EE', 'EE', 'Estonia', TRUE, FALSE),
  ('EL', 'GR', 'Greece', TRUE, FALSE),
  ('ES', 'ES', 'Spain', TRUE, FALSE),
  ('EU27_2020', CAST(NULL AS STRING), 'European Union - 27 countries (from 2020)', CAST(NULL AS BOOL), TRUE),
  ('FI', 'FI', 'Finland', TRUE, FALSE),
  ('FR', 'FR', 'France', TRUE, FALSE),
  ('HR', 'HR', 'Croatia', TRUE, FALSE),
  ('HU', 'HU', 'Hungary', TRUE, FALSE),
  ('IE', 'IE', 'Ireland', TRUE, FALSE),
  ('IS', 'IS', 'Iceland', FALSE, FALSE),
  ('IT', 'IT', 'Italy', TRUE, FALSE),
  ('LI', 'LI', 'Liechtenstein', FALSE, FALSE),
  ('LT', 'LT', 'Lithuania', TRUE, FALSE),
  ('LU', 'LU', 'Luxembourg', TRUE, FALSE),
  ('LV', 'LV', 'Latvia', TRUE, FALSE),
  ('MT', 'MT', 'Malta', TRUE, FALSE),
  ('NL', 'NL', 'Netherlands', TRUE, FALSE),
  ('NO', 'NO', 'Norway', FALSE, FALSE),
  ('PL', 'PL', 'Poland', TRUE, FALSE),
  ('PT', 'PT', 'Portugal', TRUE, FALSE),
  ('RO', 'RO', 'Romania', TRUE, FALSE),
  ('SE', 'SE', 'Sweden', TRUE, FALSE),
  ('SI', 'SI', 'Slovenia', TRUE, FALSE),
  ('SK', 'SK', 'Slovakia', TRUE, FALSE)
]);
