-- name: MAD medication adherence by clinic, MY2026
-- description: Medication Adherence for Diabetes (metformin) by clinic for measurement year 2026: the adherence rate (PDC 0.80 or more) and the average PDC.
-- PDC = days covered by metformin fills / days in the treatment period (first fill of the year to the data horizon).
-- Eligible = 18+ with at least 2 fills. Fills come from the effective medication layer (care_order_med).
SELECT `Clinic`,
       MEASURE(`Eligible Patients`)  AS eligible,
       MEASURE(`MAD Adherence Rate`) AS mad_rate,
       MEASURE(`Avg PDC`)            AS avg_pdc
FROM eli_test_classic_catalog.care_protocol_semantic.mad_compliance_metrics
WHERE `Measurement Year` = 2026
GROUP BY ALL
ORDER BY mad_rate
