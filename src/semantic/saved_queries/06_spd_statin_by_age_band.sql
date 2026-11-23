-- name: SPD statin therapy by age band, MY2026
-- description: Statin therapy for diabetics aged 40-75 by age band for measurement year 2026.
-- SPD is met when a statin is dispensed in the measurement year. Statins are resolved by subsumption: the SPD_STATIN
-- value set lists RxNorm ingredients, and rxnorm_closure maps each ingredient to the clinical drugs that are ordered.
SELECT `Age Band`,
       MEASURE(`Eligible Patients`)   AS eligible,
       MEASURE(`On Statin Patients`)  AS on_statin,
       MEASURE(`SPD Compliance Rate`) AS spd_rate
FROM eli_test_classic_catalog.care_protocol_semantic.spd_compliance_metrics
WHERE `Measurement Year` = 2026
GROUP BY ALL
ORDER BY `Age Band`
