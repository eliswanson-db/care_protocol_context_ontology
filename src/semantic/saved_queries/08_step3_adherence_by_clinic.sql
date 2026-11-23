-- name: Protocol Step 3 adherence by clinic, MY2026
-- description: Care-protocol Step 3 (recheck A1c within 90 days of a result above 9%) by clinic for measurement year 2026, with open obligations and the average days to the recheck.
-- A trigger is every A1c result above 9.0% in the year. MET = a later A1c within 90 days. A trigger whose 90-day window
-- has not closed yet is OPEN: counted in Open Obligations, not in the adherence rate.
SELECT `Clinic`,
       MEASURE(`Trigger Events`)                  AS closed_triggers,
       MEASURE(`Protocol Step 3 Adherence Rate`)  AS step3_adherence_rate,
       MEASURE(`Open Obligations`)                AS open_obligations,
       MEASURE(`Avg Days To Follow-up`)           AS avg_days_to_recheck
FROM eli_test_classic_catalog.care_protocol_semantic.protocol_adherence_metrics
WHERE `Measurement Year` = 2026
GROUP BY ALL
ORDER BY step3_adherence_rate
