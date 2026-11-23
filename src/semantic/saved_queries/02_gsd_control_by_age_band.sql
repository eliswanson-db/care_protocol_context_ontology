-- name: GSD glycemic control by age band, MY2026
-- description: HEDIS GSD indicators by age band for measurement year 2026: the < 8.0% (good control) rate, the compliance (Blood Sugar Controlled) rate, and A1c testing coverage.
-- HEDIS GSD reports two rates over ALL eligible patients: last A1c of the year < 8.0% (good control) and > 9.0% or no
-- test (poor control, lower is better). Compliance here = last A1c 9.0% or below. Tested Patients is coverage only.
SELECT `Age Band`,
       MEASURE(`Eligible Patients`)     AS eligible,
       MEASURE(`Good Control Rate`)     AS good_control_rate,
       MEASURE(`GSD Compliance Rate`)   AS blood_sugar_controlled_rate,
       MEASURE(`Tested Patients`) / MEASURE(`Eligible Patients`) AS a1c_testing_coverage
FROM eli_test_classic_catalog.care_protocol_semantic.gsd_compliance_metrics
WHERE `Measurement Year` = 2026
GROUP BY ALL
ORDER BY `Age Band`
