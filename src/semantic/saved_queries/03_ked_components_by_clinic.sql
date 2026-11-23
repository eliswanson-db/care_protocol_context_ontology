-- name: KED components by clinic, MY2026
-- description: Kidney Health Evaluation by clinic for measurement year 2026: the compliance rate and its two components (eGFR test rate, uACR test rate), to see which test limits each clinic.
-- KED compliance needs BOTH an eGFR and a uACR test in the measurement year (diabetics 18-85). uACR is usually the
-- limiting component.
SELECT `Clinic`,
       MEASURE(`Eligible Patients`)   AS eligible,
       MEASURE(`KED Compliance Rate`) AS ked_rate,
       MEASURE(`eGFR Test Rate`)      AS egfr_test_rate,
       MEASURE(`uACR Test Rate`)      AS uacr_test_rate
FROM eli_test_classic_catalog.care_protocol_semantic.ked_compliance_metrics
WHERE `Measurement Year` = 2026
GROUP BY ALL
ORDER BY ked_rate
