-- name: BPD blood-pressure control by clinic, MY2026
-- description: Blood pressure control for diabetics by clinic for measurement year 2026, with the average systolic and diastolic of each patient's last reading.
-- BPD is met when the last reading of the year is controlled: systolic < 140 AND diastolic < 90, both from the
-- same reading. No reading in the year is a care gap.
SELECT `Clinic`,
       MEASURE(`Eligible Patients`)   AS eligible,
       MEASURE(`BPD Compliance Rate`) AS bpd_rate,
       MEASURE(`Avg Systolic`)        AS avg_systolic,
       MEASURE(`Avg Diastolic`)       AS avg_diastolic
FROM eli_test_classic_catalog.care_protocol_semantic.bpd_compliance_metrics
WHERE `Measurement Year` = 2026
GROUP BY ALL
ORDER BY bpd_rate
