-- name: Lab result volume by LOINC component, MY2026
-- description: Lab results in measurement year 2026 grouped by the LOINC component they measure (e.g. HbA1c across assay methods), from the governed lab metric view.
-- A lab concept is identified by its LOINC multiaxial component, so 4548-4, 17856-6 and 59261-8 all count as HbA1c.
SELECT `Lab Concept`,
       MEASURE(`Observations`)   AS results,
       MEASURE(`Patients Tested`) AS patients
FROM eli_test_classic_catalog.care_protocol_semantic.lab_result_metrics
WHERE `Measurement Year` = 2026
GROUP BY ALL
ORDER BY results DESC
