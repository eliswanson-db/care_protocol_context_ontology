-- Measure-drift demo: the SAME measure logic, the SAME data, different VALUE-SET VERSIONS -> different result.
-- The value_set_segment table versions each value set by measurement_year. KED_EGFR changed between years:
--   MY2025: accepts 98979-8 (CKD-EPI) AND 33914-3 (MDRD)
--   MY2026: "modernized" to 98979-8 (CKD-EPI) only
-- Synthea records eGFR as 33914-3 (MDRD). So the 2026 value-set change silently drops most eGFR coverage,
-- even though the underlying lab data is identical. This is measure drift from terminology, not from data.
-- Run on a SQL warehouse (read-only). Replace eli_test_classic_catalog if your catalog differs.

-- eGFR coverage (distinct patients with a matching eGFR test in 2025) under each value-set VERSION.
-- LEFT JOIN from the versions so a version that matches nothing still shows as 0 (not an absent row):
WITH versions AS (
  SELECT DISTINCT measurement_year AS vs_year
  FROM eli_test_classic_catalog.care_protocol_terminology.value_set_segment
  WHERE segment_id = 'KED_EGFR'
),
vs AS (
  SELECT measurement_year AS vs_year, code
  FROM eli_test_classic_catalog.care_protocol_terminology.value_set_segment
  WHERE segment_id = 'KED_EGFR'
),
egfr_obs AS (
  SELECT patient_id, loinc_code
  FROM eli_test_classic_catalog.care_protocol.silver_observation
  WHERE year(result_ts) = 2025
)
SELECT
  v.vs_year                                  AS value_set_version,
  COUNT(DISTINCT o.patient_id)               AS patients_with_egfr,
  concat_ws(', ', collect_set(o.loinc_code)) AS codes_matched
FROM versions v
LEFT JOIN vs      ON vs.vs_year = v.vs_year
LEFT JOIN egfr_obs o ON o.loinc_code = vs.code
GROUP BY v.vs_year
ORDER BY v.vs_year;
-- Observed: 2025 -> 79 patients (matches 33914-3); 2026 -> 0 (only 98979-8, which the data never uses).
-- Takeaway: a governed value set with a measurement_year lets you reproduce a measure exactly as it was
-- defined in any year, and makes drift explicit and auditable instead of a silent code-list edit.
