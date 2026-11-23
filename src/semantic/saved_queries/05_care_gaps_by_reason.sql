-- name: Care gaps by measure and reason, MY2026
-- description: Open care gaps for measurement year 2026 broken down by measure and by the governed gap reason each metric view assigns.
-- Gap reasons are the metric views' own Gap Reason dimension, so they match every dashboard and Genie answer.
SELECT 'GSD' AS measure, `Gap Reason` AS gap_reason, MEASURE(`Eligible Patients`) AS patients
FROM eli_test_classic_catalog.care_protocol_semantic.gsd_compliance_metrics WHERE `Measurement Year` = 2026 AND `Compliance Status` = 'NOT_MET' GROUP BY ALL
UNION ALL SELECT 'KED', `Gap Reason`, MEASURE(`Eligible Patients`)
FROM eli_test_classic_catalog.care_protocol_semantic.ked_compliance_metrics WHERE `Measurement Year` = 2026 AND `Compliance Status` = 'NOT_MET' GROUP BY ALL
UNION ALL SELECT 'BPD', `Gap Reason`, MEASURE(`Eligible Patients`)
FROM eli_test_classic_catalog.care_protocol_semantic.bpd_compliance_metrics WHERE `Measurement Year` = 2026 AND `Compliance Status` = 'NOT_MET' GROUP BY ALL
UNION ALL SELECT 'SPD', `Gap Reason`, MEASURE(`Eligible Patients`)
FROM eli_test_classic_catalog.care_protocol_semantic.spd_compliance_metrics WHERE `Measurement Year` = 2026 AND `Compliance Status` = 'NOT_MET' GROUP BY ALL
UNION ALL SELECT 'EED', `Gap Reason`, MEASURE(`Eligible Patients`)
FROM eli_test_classic_catalog.care_protocol_semantic.eed_compliance_metrics WHERE `Measurement Year` = 2026 AND `Compliance Status` = 'NOT_MET' GROUP BY ALL
ORDER BY patients DESC
