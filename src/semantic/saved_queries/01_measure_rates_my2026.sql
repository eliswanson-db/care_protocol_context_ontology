-- name: HEDIS measure compliance rates, MY2026
-- description: One row per diabetes quality measure with its governed compliance rate and eligible population for measurement year 2026, read from the certified metric views.
-- Each rate is the metric view's own definition (numerator / eligible). GSD = last A1c of the year 9.0% or below
-- (Blood Sugar Controlled; no test is not compliant). KED = an eGFR AND a uACR test. BPD = last reading below 140/90.
-- SPD = a statin dispensed in the year. EED = a diabetic eye exam in the year.
SELECT 'GSD' AS measure, MEASURE(`GSD Compliance Rate`) AS rate, MEASURE(`Eligible Patients`) AS eligible
FROM eli_test_classic_catalog.care_protocol_semantic.gsd_compliance_metrics WHERE `Measurement Year` = 2026
UNION ALL SELECT 'KED', MEASURE(`KED Compliance Rate`), MEASURE(`Eligible Patients`)
FROM eli_test_classic_catalog.care_protocol_semantic.ked_compliance_metrics WHERE `Measurement Year` = 2026
UNION ALL SELECT 'BPD', MEASURE(`BPD Compliance Rate`), MEASURE(`Eligible Patients`)
FROM eli_test_classic_catalog.care_protocol_semantic.bpd_compliance_metrics WHERE `Measurement Year` = 2026
UNION ALL SELECT 'SPD', MEASURE(`SPD Compliance Rate`), MEASURE(`Eligible Patients`)
FROM eli_test_classic_catalog.care_protocol_semantic.spd_compliance_metrics WHERE `Measurement Year` = 2026
UNION ALL SELECT 'EED', MEASURE(`EED Compliance Rate`), MEASURE(`Eligible Patients`)
FROM eli_test_classic_catalog.care_protocol_semantic.eed_compliance_metrics WHERE `Measurement Year` = 2026
