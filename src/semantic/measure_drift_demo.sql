-- Measure-drift demo: the SAME measure logic over the SAME data under different VALUE-SET VERSIONS.
-- value_set_segment versions each value set by measurement_year. KED_EGFR:
--   MY2025: 98979-8 (CKD-EPI 2021) and 33914-3 (MDRD)
--   MY2026: 98979-8 only (MDRD retired)
-- The demo health system's lab switched its eGFR equation from MDRD to race-free CKD-EPI 2021 on 2022-07-01
-- (src/data_generation/epicize_map.py), as most US labs did in 2022. So retiring 33914-3 in MY2026 changes nothing
-- for MY2026 results, but applying the 2026 set to an older year silently drops every pre-switch result.
-- Measures apply the value set of their own measurement year (src/pipelines/measures.py _value_set).
-- Run on a SQL warehouse (read-only). Replace eli_test_classic_catalog if your catalog differs.

-- Patients with an eGFR result, per result year, under each value-set version:
WITH vs AS (
  SELECT measurement_year AS vs_version, code
  FROM eli_test_classic_catalog.care_protocol_terminology.value_set_segment
  WHERE segment_id = 'KED_EGFR'
),
egfr AS (
  SELECT patient_id, loinc_code, year(result_ts) AS result_year
  FROM eli_test_classic_catalog.care_protocol.silver_observation
  WHERE loinc_code IN ('33914-3', '98979-8') AND year(result_ts) >= 2021
)
SELECT
  e.result_year,
  v.vs_version                               AS value_set_version,
  COUNT(DISTINCT e.patient_id)               AS patients_with_egfr,
  concat_ws(', ', collect_set(e.loinc_code)) AS codes_matched
FROM egfr e
JOIN vs v ON v.code = e.loinc_code
GROUP BY e.result_year, v.vs_version
ORDER BY e.result_year, v.vs_version;
-- Read it as: for 2023-2026 both versions match the same patients (all 98979-8); for 2021 only the 2025 version
-- matches (all 33914-3); 2022 splits at the switch. Reproducing an old year needs that year's value set.
