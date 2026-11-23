-- name: EED diabetic eye exam by clinic, MY2026
-- description: Diabetic eye exam rate by clinic for measurement year 2026.
-- EED is met by a retinal or dilated diabetic eye exam recorded in the measurement year.
SELECT `Clinic`,
       MEASURE(`Eligible Patients`)   AS eligible,
       MEASURE(`Eye Exam Patients`)   AS eye_exam_patients,
       MEASURE(`EED Compliance Rate`) AS eed_rate
FROM eli_test_classic_catalog.care_protocol_semantic.eed_compliance_metrics
WHERE `Measurement Year` = 2026
GROUP BY ALL
ORDER BY eed_rate
