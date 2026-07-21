-- Hand-authored reference table of anomalies with a verified, documented
-- cause (as opposed to Gold's generic "flagged_undiagnosed" bucket, which
-- catches other >100%/large-swing rows nobody has investigated). Every
-- (country, year, rate) pair here was checked against the loaded Eurostat
-- data before being written -- see DECISIONS.md for the verification trail
-- (in particular, an initial claim about Greece 2022 was checked against
-- this table and found to actually be the EU27 aggregate, not Greece, and
-- was dropped rather than included).
CREATE OR REPLACE TABLE `msbai-capstone-nb4603.elv_gold.documented_anomalies` AS
SELECT * FROM UNNEST([
  STRUCT(
    'MT' AS country_code_iso, 2023 AS year,
    'Reuse+recycling rate dropped from 84.1% (2022) to 62.8% (2023). Cause: material was stockpiled pending export while awaiting more favorable export pricing, rather than a genuine collapse in processing capacity.' AS cause_note
  ),
  (
    'PL', 2019,
    'Reuse+recycling (118.8%) and reuse+recovery (122.2%) rates exceeded 100%. Cause: backlog clearing -- processing of previously stockpiled end-of-life vehicles pushed the year\'s processed tonnage above the year\'s newly generated tonnage.'
  ),
  (
    'PL', 2020,
    'Reuse+recycling (106.8%) and reuse+recovery (109.0%) rates exceeded 100% again, a smaller continuation of 2019\'s backlog-clearing pattern.'
  ),
  (
    'DK', 2019,
    'Reuse+recovery rate reached 102.6% (recycling rate stayed normal at 94.6%). Cause: the same backlog-clearing mechanism as Poland 2019-2020, at much smaller scale.'
  ),
  (
    'DK', 2020,
    'Reuse+recovery rate reached 102.3% (recycling rate stayed normal at 94.8%), a continuation of 2019\'s backlog-clearing pattern.'
  ),
  (
    'GR', 2015,
    'Reuse+recycling (64.5%) and reuse+recovery (68.9%) rates dropped sharply. Cause, per Eurostat\'s End-of-life vehicle statistics Statistics Explained article: low scrap-metal prices caused temporary stockpiling of material at dismantling facility sites rather than processing it -- the same stockpiling-for-favorable-pricing mechanism as Malta\'s 2023 anomaly, here triggered by metal prices rather than export timing.'
  ),
  (
    'GR', 2019,
    'Reuse+recycling (69.7%) and reuse+recovery (77.2%) rates dropped sharply again. Same documented cause as 2015: low scrap-metal prices triggering temporary stockpiling at dismantling sites.'
  )
]);
