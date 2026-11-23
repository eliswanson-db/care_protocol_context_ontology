-- name: Value sets and their code counts by measurement year
-- description: Every HEDIS value set with its code system and the number of codes in each measurement-year version.
-- Value sets are versioned by measurement_year; a measure uses the latest version on or before its own year.
SELECT segment_id, segment_name, code_system, measurement_year, COUNT(*) AS codes
FROM eli_test_classic_catalog.care_protocol_terminology.value_set_segment
GROUP BY ALL
ORDER BY segment_id, measurement_year
