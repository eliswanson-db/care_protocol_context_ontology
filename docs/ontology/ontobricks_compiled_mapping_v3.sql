WITH
  src_0 AS (
    SELECT code AS icd_code FROM eli_test_classic_catalog.care_protocol_terminology.icd10_hier WHERE code IS NOT NULL
  ),
  src_1 AS (
    SELECT DISTINCT subject AS drug_class FROM eli_test_classic_catalog.care_protocol_terminology.protocol_edges WHERE subject LIKE 'DRUGCLASS-%'
  ),
  src_2 AS (
    SELECT p.`patient_id` AS ID, concat(p.`first_name`, ' ', p.`last_name`) AS Label, g.`age` AS age FROM eli_test_classic_catalog.care_protocol.bronze_patient p LEFT JOIN eli_test_classic_catalog.care_protocol.gold_adherence_gsd g ON p.`patient_id` = g.`patient_id` WHERE p.`patient_id` IS NOT NULL
  ),
  src_3 AS (
    SELECT DISTINCT `icd10_code` AS ID, `description` AS Label, `icd10_code` AS icd10_code FROM eli_test_classic_catalog.care_protocol.bronze_pat_enc_dx WHERE `icd10_code` IS NOT NULL AND `icd10_code` LIKE 'N18%'
  ),
  src_4 AS (
    SELECT DISTINCT `icd10_code` AS ID, `description` AS Label, `icd10_code` AS icd10_code FROM eli_test_classic_catalog.care_protocol.bronze_pat_enc_dx WHERE `icd10_code` IS NOT NULL AND (`icd10_code` LIKE 'E10%' OR `icd10_code` LIKE 'E11%' OR `icd10_code` LIKE 'E13%')
  ),
  src_5 AS (
    SELECT DISTINCT `icd10_code` AS ID, `description` AS Label, `icd10_code` AS icd10_code FROM eli_test_classic_catalog.care_protocol.bronze_pat_enc_dx WHERE `icd10_code` IS NOT NULL AND `icd10_code` LIKE 'I50%'
  ),
  src_6 AS (
    SELECT DISTINCT `icd10_code` AS ID, `description` AS Label, `icd10_code` AS icd10_code FROM eli_test_classic_catalog.care_protocol.bronze_pat_enc_dx WHERE `icd10_code` IS NOT NULL AND (`icd10_code` LIKE 'K70%' OR `icd10_code` LIKE 'K71%' OR `icd10_code` LIKE 'K72%' OR `icd10_code` LIKE 'K73%' OR `icd10_code` LIKE 'K74%' OR `icd10_code` LIKE 'K75%' OR `icd10_code` LIKE 'K76%' OR `icd10_code` LIKE 'K77%' OR `icd10_code` LIKE 'B18%')
  ),
  src_7 AS (
    SELECT `patient_id` AS ID, `description` AS Label, `icd10_code` AS icd10_code FROM eli_test_classic_catalog.care_protocol.bronze_pat_enc_dx WHERE `patient_id` IS NOT NULL AND (`icd10_code` LIKE 'O%' OR `icd10_code` IN ('Z33','Z34'))
  ),
  src_8 AS (
    SELECT DISTINCT `loinc_code` AS ID, `description` AS Label, `loinc_code` AS loinc_code FROM eli_test_classic_catalog.care_protocol.silver_observation WHERE `loinc_code` IS NOT NULL
  ),
  src_9 AS (
    SELECT DISTINCT parent_code AS ing_code FROM eli_test_classic_catalog.care_protocol_terminology.rxnorm_hier WHERE parent_code IS NOT NULL
  ),
  src_10 AS (
    SELECT DISTINCT part AS part_code FROM eli_test_classic_catalog.care_protocol_terminology.loinc_parts WHERE part IS NOT NULL
  ),
  src_11 AS (
    SELECT 'GSD' AS measure_id UNION SELECT 'BPD' UNION SELECT 'KED' UNION SELECT 'EED' UNION SELECT 'SPD'
  ),
  src_12 AS (
    SELECT DISTINCT code AS rx_code FROM eli_test_classic_catalog.care_protocol_terminology.rxnorm_hier WHERE code IS NOT NULL
  ),
  src_13 AS (
    SELECT patient_id, loinc_code, value_num, CONCAT_WS('_', patient_id, loinc_code, CAST(result_ts AS STRING)) AS obs_id FROM eli_test_classic_catalog.care_protocol.silver_observation WHERE loinc_code IS NOT NULL
  ),
  src_14 AS (
    SELECT object AS thr, MAX(value) AS thr_value FROM eli_test_classic_catalog.care_protocol_terminology.protocol_edges WHERE predicate IN ('contraindicatedWhen','definedBy','hasThreshold') GROUP BY object
  ),
  src_15 AS (
    SELECT DISTINCT vs_id FROM (SELECT segment_id AS vs_id FROM eli_test_classic_catalog.care_protocol_terminology.value_set_segment UNION SELECT object AS vs_id FROM eli_test_classic_catalog.care_protocol_terminology.protocol_edges WHERE predicate IN ('recommendedFor','contraindicatedWith','firstLineFor') UNION SELECT subject AS vs_id FROM eli_test_classic_catalog.care_protocol_terminology.protocol_edges WHERE predicate = 'definedBy') v WHERE vs_id <> 'SPD'
  ),
  src_16 AS (
    SELECT DISTINCT v.segment_id AS vs_id, v.code AS icd_code FROM eli_test_classic_catalog.care_protocol_terminology.value_set_segment v JOIN eli_test_classic_catalog.care_protocol_terminology.icd10_hier h ON v.code = h.code WHERE v.code_system = 'ICD10CM'
  ),
  src_17 AS (
    SELECT subject AS drug_class, object AS thr FROM eli_test_classic_catalog.care_protocol_terminology.protocol_edges WHERE predicate = 'contraindicatedWhen'
  ),
  src_18 AS (
    SELECT subject AS drug_class, object AS vs_id FROM eli_test_classic_catalog.care_protocol_terminology.protocol_edges WHERE predicate = 'contraindicatedWith'
  ),
  src_19 AS (
    SELECT subject AS vs_id, object AS thr FROM eli_test_classic_catalog.care_protocol_terminology.protocol_edges WHERE predicate = 'definedBy'
  ),
  src_20 AS (
    SELECT `patient_id` AS source_id, `measure_id` AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_gsd WHERE `eligible_flag` = true AND `patient_id` IS NOT NULL AND `measure_id` IS NOT NULL
UNION
SELECT `patient_id` AS source_id, `measure_id` AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_eed WHERE `eligible_flag` = true AND `patient_id` IS NOT NULL AND `measure_id` IS NOT NULL
UNION
SELECT `patient_id` AS source_id, `measure_id` AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_bpd WHERE `eligible_flag` = true AND `patient_id` IS NOT NULL AND `measure_id` IS NOT NULL
UNION
SELECT `patient_id` AS source_id, `measure_id` AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_ked WHERE `eligible_flag` = true AND `patient_id` IS NOT NULL AND `measure_id` IS NOT NULL
UNION
SELECT `patient_id` AS source_id, `measure_id` AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_mad WHERE `eligible_flag` = true AND `patient_id` IS NOT NULL AND `measure_id` IS NOT NULL
UNION
SELECT `patient_id` AS source_id, `measure_id` AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_spd WHERE `eligible_flag` = true AND `patient_id` IS NOT NULL AND `measure_id` IS NOT NULL
  ),
  src_21 AS (
    SELECT subject AS drug_class, object AS vs_id FROM eli_test_classic_catalog.care_protocol_terminology.protocol_edges WHERE predicate = 'firstLineFor'
  ),
  src_22 AS (
    SELECT `patient_id` AS source_id, `measure_id` AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_gsd WHERE `eligible_flag` = true AND `evidence_code` IS NULL AND `patient_id` IS NOT NULL AND `measure_id` IS NOT NULL
UNION
SELECT `patient_id` AS source_id, `measure_id` AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_eed WHERE `eligible_flag` = true AND `evidence_code` IS NULL AND `patient_id` IS NOT NULL AND `measure_id` IS NOT NULL
UNION
SELECT `patient_id` AS source_id, `measure_id` AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_bpd WHERE `eligible_flag` = true AND (`bp_datetime` IS NULL OR `systolic` >= 140 OR `diastolic` >= 90) AND `patient_id` IS NOT NULL AND `measure_id` IS NOT NULL
UNION
SELECT `patient_id` AS source_id, `measure_id` AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_ked WHERE `eligible_flag` = true AND (`egfr_code` IS NULL OR `uacr_code` IS NULL) AND `patient_id` IS NOT NULL AND `measure_id` IS NOT NULL
UNION
SELECT `patient_id` AS source_id, `measure_id` AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_mad WHERE `eligible_flag` = true AND `pdc` < 0.80 AND `patient_id` IS NOT NULL AND `measure_id` IS NOT NULL
UNION
SELECT `patient_id` AS source_id, `measure_id` AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_spd WHERE `eligible_flag` = true AND `evidence_code` IS NULL AND `patient_id` IS NOT NULL AND `measure_id` IS NOT NULL
  ),
  src_23 AS (
    SELECT loinc_code, part AS part_code FROM eli_test_classic_catalog.care_protocol_terminology.loinc_parts WHERE predicate = 'has_component'
  ),
  src_24 AS (
    SELECT patient_id, icd10_code AS icd_code FROM eli_test_classic_catalog.care_protocol.silver_condition WHERE icd10_code IS NOT NULL
  ),
  src_25 AS (
    SELECT code AS rx_code, parent_code AS ing_code FROM eli_test_classic_catalog.care_protocol_terminology.rxnorm_hier WHERE parent_code IS NOT NULL
  ),
  src_26 AS (
    SELECT loinc_code, part AS part_code FROM eli_test_classic_catalog.care_protocol_terminology.loinc_parts WHERE predicate = 'has_method'
  ),
  src_27 AS (
    SELECT patient_id, CONCAT_WS('_', patient_id, loinc_code, CAST(result_ts AS STRING)) AS obs_id FROM eli_test_classic_catalog.care_protocol.silver_observation WHERE loinc_code IS NOT NULL
  ),
  src_28 AS (
    SELECT loinc_code, part AS part_code FROM eli_test_classic_catalog.care_protocol_terminology.loinc_parts WHERE predicate = 'has_system'
  ),
  src_29 AS (
    SELECT subject AS measure_id, object AS thr FROM eli_test_classic_catalog.care_protocol_terminology.protocol_edges WHERE predicate = 'hasThreshold'
  ),
  src_30 AS (
    SELECT DISTINCT s.rxcui AS ing_code, 'DRUGCLASS-STATIN' AS drug_class FROM eli_test_classic_catalog.care_protocol_terminology.rxnorm_statin s JOIN (SELECT DISTINCT parent_code FROM eli_test_classic_catalog.care_protocol_terminology.rxnorm_hier WHERE parent_code IS NOT NULL) h ON s.rxcui = h.parent_code
  ),
  src_31 AS (
    SELECT subject AS measure_id, object AS part_code FROM eli_test_classic_catalog.care_protocol_terminology.protocol_edges WHERE predicate = 'monitoredBy'
  ),
  src_32 AS (
    SELECT patient_id, rxnorm_code AS rx_code FROM eli_test_classic_catalog.care_protocol.bronze_order_med WHERE rxnorm_code IS NOT NULL
  ),
  src_33 AS (
    SELECT subject AS drug_class, object AS vs_id FROM eli_test_classic_catalog.care_protocol_terminology.protocol_edges WHERE predicate = 'recommendedFor' AND object <> 'SPD'
  ),
  src_34 AS (
    SELECT subject AS drug_class, object AS measure_id FROM eli_test_classic_catalog.care_protocol_terminology.protocol_edges WHERE predicate = 'recommendedFor' AND object = 'SPD'
  ),
  src_35 AS (
    SELECT code AS icd_code, parent_code AS icd_parent FROM eli_test_classic_catalog.care_protocol_terminology.icd10_hier WHERE parent_code IS NOT NULL
  )
SELECT DISTINCT subject, predicate, object FROM (
            
                    SELECT CONCAT('https://care-protocol.example/ontology/Condition/', TRY_CAST(icd_code AS STRING)) AS subject, stack(2, 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', 'https://care-protocol.example/ontology#Condition', 'https://care-protocol.example/ontology/icd10Code', COALESCE(TRY_CAST(icd_code AS STRING), '')) AS (predicate, object)
                FROM src_0
                 UNION ALL 
                    SELECT CONCAT('https://care-protocol.example/ontology/DrugClass/', TRY_CAST(drug_class AS STRING)) AS subject, stack(1, 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', 'https://care-protocol.example/ontology#DrugClass') AS (predicate, object)
                FROM src_1
                 UNION ALL 
                    SELECT CONCAT('https://care-protocol.example/ontology/Patient/', TRY_CAST(ID AS STRING)) AS subject, stack(3, 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', 'https://care-protocol.example/ontology#Patient', 'http://www.w3.org/2000/01/rdf-schema#label', COALESCE(TRY_CAST(Label AS STRING), ''), 'https://care-protocol.example/ontology/ageAtPeriodEnd', COALESCE(TRY_CAST(age AS STRING), '')) AS (predicate, object)
                FROM src_2
                 UNION ALL 
                    SELECT CONCAT('https://care-protocol.example/ontology/ChronicKidneyDisease/', TRY_CAST(ID AS STRING)) AS subject, stack(3, 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', 'https://care-protocol.example/ontology#ChronicKidneyDisease', 'http://www.w3.org/2000/01/rdf-schema#label', COALESCE(TRY_CAST(Label AS STRING), ''), 'https://care-protocol.example/ontology/icd10Code', COALESCE(TRY_CAST(icd10_code AS STRING), '')) AS (predicate, object)
                FROM src_3
                 UNION ALL 
                    SELECT CONCAT('https://care-protocol.example/ontology/DiabetesDiagnosis/', TRY_CAST(ID AS STRING)) AS subject, stack(3, 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', 'https://care-protocol.example/ontology#DiabetesDiagnosis', 'http://www.w3.org/2000/01/rdf-schema#label', COALESCE(TRY_CAST(Label AS STRING), ''), 'https://care-protocol.example/ontology/icd10Code', COALESCE(TRY_CAST(icd10_code AS STRING), '')) AS (predicate, object)
                FROM src_4
                 UNION ALL 
                    SELECT CONCAT('https://care-protocol.example/ontology/HeartFailure/', TRY_CAST(ID AS STRING)) AS subject, stack(3, 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', 'https://care-protocol.example/ontology#HeartFailure', 'http://www.w3.org/2000/01/rdf-schema#label', COALESCE(TRY_CAST(Label AS STRING), ''), 'https://care-protocol.example/ontology/icd10Code', COALESCE(TRY_CAST(icd10_code AS STRING), '')) AS (predicate, object)
                FROM src_5
                 UNION ALL 
                    SELECT CONCAT('https://care-protocol.example/ontology/HepaticDisease/', TRY_CAST(ID AS STRING)) AS subject, stack(3, 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', 'https://care-protocol.example/ontology#HepaticDisease', 'http://www.w3.org/2000/01/rdf-schema#label', COALESCE(TRY_CAST(Label AS STRING), ''), 'https://care-protocol.example/ontology/icd10Code', COALESCE(TRY_CAST(icd10_code AS STRING), '')) AS (predicate, object)
                FROM src_6
                 UNION ALL 
                    SELECT CONCAT('https://care-protocol.example/ontology/Pregnancy/', TRY_CAST(ID AS STRING)) AS subject, stack(3, 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', 'https://care-protocol.example/ontology#Pregnancy', 'http://www.w3.org/2000/01/rdf-schema#label', COALESCE(TRY_CAST(Label AS STRING), ''), 'https://care-protocol.example/ontology/icd10Code', COALESCE(TRY_CAST(icd10_code AS STRING), '')) AS (predicate, object)
                FROM src_7
                 UNION ALL 
                    SELECT CONCAT('https://care-protocol.example/ontology/LabTest/', TRY_CAST(ID AS STRING)) AS subject, stack(3, 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', 'https://care-protocol.example/ontology#LabTest', 'http://www.w3.org/2000/01/rdf-schema#label', COALESCE(TRY_CAST(Label AS STRING), ''), 'https://care-protocol.example/ontology/loincCode', COALESCE(TRY_CAST(loinc_code AS STRING), '')) AS (predicate, object)
                FROM src_8
                 UNION ALL 
                    SELECT CONCAT('https://care-protocol.example/ontology/Ingredient/', TRY_CAST(ing_code AS STRING)) AS subject, stack(1, 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', 'https://care-protocol.example/ontology#Ingredient') AS (predicate, object)
                FROM src_9
                 UNION ALL 
                    SELECT CONCAT('https://care-protocol.example/ontology/LoincPart/', TRY_CAST(part_code AS STRING)) AS subject, stack(1, 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', 'https://care-protocol.example/ontology#LoincPart') AS (predicate, object)
                FROM src_10
                 UNION ALL 
                    SELECT CONCAT('https://care-protocol.example/ontology/Measure/', TRY_CAST(measure_id AS STRING)) AS subject, stack(1, 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', 'https://care-protocol.example/ontology#Measure') AS (predicate, object)
                FROM src_11
                 UNION ALL 
                    SELECT CONCAT('https://care-protocol.example/ontology/Medication/', TRY_CAST(rx_code AS STRING)) AS subject, stack(2, 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', 'https://care-protocol.example/ontology#Medication', 'https://care-protocol.example/ontology/rxnormCode', COALESCE(TRY_CAST(rx_code AS STRING), '')) AS (predicate, object)
                FROM src_12
                 UNION ALL 
                    SELECT CONCAT('https://care-protocol.example/ontology/Observation/', TRY_CAST(obs_id AS STRING)) AS subject, stack(2, 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', 'https://care-protocol.example/ontology#Observation', 'https://care-protocol.example/ontology/resultValue', COALESCE(TRY_CAST(value_num AS STRING), '')) AS (predicate, object)
                FROM src_13
                 UNION ALL 
                    SELECT CONCAT('https://care-protocol.example/ontology/Threshold/', TRY_CAST(thr AS STRING)) AS subject, stack(2, 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', 'https://care-protocol.example/ontology#Threshold', 'https://care-protocol.example/ontology/thresholdValue', COALESCE(TRY_CAST(thr_value AS STRING), '')) AS (predicate, object)
                FROM src_14
                 UNION ALL 
                    SELECT CONCAT('https://care-protocol.example/ontology/ValueSet/', TRY_CAST(vs_id AS STRING)) AS subject, stack(2, 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', 'https://care-protocol.example/ontology#ValueSet', 'https://care-protocol.example/ontology/valueSetId', COALESCE(TRY_CAST(vs_id AS STRING), '')) AS (predicate, object)
                FROM src_15
                 UNION ALL 
                SELECT 
                    CONCAT('https://care-protocol.example/ontology/ValueSet/', TRY_CAST(vs_id AS STRING)) AS subject,
                    'https://care-protocol.example/ontology/contains' AS predicate,
                    CONCAT('https://care-protocol.example/ontology/icd/', TRY_CAST(icd_code AS STRING)) AS object
                FROM src_16 AS rel_subquery
             UNION ALL 
                SELECT 
                    CONCAT('https://care-protocol.example/ontology/DrugClass/', TRY_CAST(drug_class AS STRING)) AS subject,
                    'https://care-protocol.example/ontology/contraindicatedWhen' AS predicate,
                    CONCAT('https://care-protocol.example/ontology/Threshold/', TRY_CAST(thr AS STRING)) AS object
                FROM src_17 AS rel_subquery
             UNION ALL 
                SELECT 
                    CONCAT('https://care-protocol.example/ontology/DrugClass/', TRY_CAST(drug_class AS STRING)) AS subject,
                    'https://care-protocol.example/ontology/contraindicatedWith' AS predicate,
                    CONCAT('https://care-protocol.example/ontology/ValueSet/', TRY_CAST(vs_id AS STRING)) AS object
                FROM src_18 AS rel_subquery
             UNION ALL 
                SELECT 
                    CONCAT('https://care-protocol.example/ontology/ValueSet/', TRY_CAST(vs_id AS STRING)) AS subject,
                    'https://care-protocol.example/ontology/definedBy' AS predicate,
                    CONCAT('https://care-protocol.example/ontology/Threshold/', TRY_CAST(thr AS STRING)) AS object
                FROM src_19 AS rel_subquery
             UNION ALL 
                SELECT 
                    CONCAT('https://care-protocol.example/ontology/Patient/', TRY_CAST(source_id AS STRING)) AS subject,
                    'https://care-protocol.example/ontology/eligibleFor' AS predicate,
                    CONCAT('https://care-protocol.example/ontology/Measure/', TRY_CAST(target_id AS STRING)) AS object
                FROM src_20 AS rel_subquery
             UNION ALL 
                SELECT 
                    CONCAT('https://care-protocol.example/ontology/DrugClass/', TRY_CAST(drug_class AS STRING)) AS subject,
                    'https://care-protocol.example/ontology/firstLineFor' AS predicate,
                    CONCAT('https://care-protocol.example/ontology/ValueSet/', TRY_CAST(vs_id AS STRING)) AS object
                FROM src_21 AS rel_subquery
             UNION ALL 
                SELECT 
                    CONCAT('https://care-protocol.example/ontology/Patient/', TRY_CAST(source_id AS STRING)) AS subject,
                    'https://care-protocol.example/ontology/hasCareGap' AS predicate,
                    CONCAT('https://care-protocol.example/ontology/Measure/', TRY_CAST(target_id AS STRING)) AS object
                FROM src_22 AS rel_subquery
             UNION ALL 
                SELECT 
                    CONCAT('https://care-protocol.example/ontology/loinc/', TRY_CAST(loinc_code AS STRING)) AS subject,
                    'https://care-protocol.example/ontology/hasComponent' AS predicate,
                    CONCAT('https://care-protocol.example/ontology/part/', TRY_CAST(part_code AS STRING)) AS object
                FROM src_23 AS rel_subquery
             UNION ALL 
                SELECT 
                    CONCAT('https://care-protocol.example/ontology/Patient/', TRY_CAST(patient_id AS STRING)) AS subject,
                    'https://care-protocol.example/ontology/hasDiagnosis' AS predicate,
                    CONCAT('https://care-protocol.example/ontology/icd/', TRY_CAST(icd_code AS STRING)) AS object
                FROM src_24 AS rel_subquery
             UNION ALL 
                SELECT 
                    CONCAT('https://care-protocol.example/ontology/rx/', TRY_CAST(rx_code AS STRING)) AS subject,
                    'https://care-protocol.example/ontology/hasIngredient' AS predicate,
                    CONCAT('https://care-protocol.example/ontology/ing/', TRY_CAST(ing_code AS STRING)) AS object
                FROM src_25 AS rel_subquery
             UNION ALL 
                SELECT 
                    CONCAT('https://care-protocol.example/ontology/loinc/', TRY_CAST(loinc_code AS STRING)) AS subject,
                    'https://care-protocol.example/ontology/hasMethod' AS predicate,
                    CONCAT('https://care-protocol.example/ontology/part/', TRY_CAST(part_code AS STRING)) AS object
                FROM src_26 AS rel_subquery
             UNION ALL 
                SELECT 
                    CONCAT('https://care-protocol.example/ontology/Patient/', TRY_CAST(patient_id AS STRING)) AS subject,
                    'https://care-protocol.example/ontology/hasObservation' AS predicate,
                    CONCAT('https://care-protocol.example/ontology/obs/', TRY_CAST(obs_id AS STRING)) AS object
                FROM src_27 AS rel_subquery
             UNION ALL 
                SELECT 
                    CONCAT('https://care-protocol.example/ontology/loinc/', TRY_CAST(loinc_code AS STRING)) AS subject,
                    'https://care-protocol.example/ontology/hasSystem' AS predicate,
                    CONCAT('https://care-protocol.example/ontology/part/', TRY_CAST(part_code AS STRING)) AS object
                FROM src_28 AS rel_subquery
             UNION ALL 
                SELECT 
                    CONCAT('https://care-protocol.example/ontology/Measure/', TRY_CAST(measure_id AS STRING)) AS subject,
                    'https://care-protocol.example/ontology/hasThreshold' AS predicate,
                    CONCAT('https://care-protocol.example/ontology/Threshold/', TRY_CAST(thr AS STRING)) AS object
                FROM src_29 AS rel_subquery
             UNION ALL 
                SELECT 
                    CONCAT('https://care-protocol.example/ontology/ing/', TRY_CAST(ing_code AS STRING)) AS subject,
                    'https://care-protocol.example/ontology/inDrugClass' AS predicate,
                    CONCAT('https://care-protocol.example/ontology/DrugClass/', TRY_CAST(drug_class AS STRING)) AS object
                FROM src_30 AS rel_subquery
             UNION ALL 
                SELECT 
                    CONCAT('https://care-protocol.example/ontology/Measure/', TRY_CAST(measure_id AS STRING)) AS subject,
                    'https://care-protocol.example/ontology/monitoredBy' AS predicate,
                    CONCAT('https://care-protocol.example/ontology/part/', TRY_CAST(part_code AS STRING)) AS object
                FROM src_31 AS rel_subquery
             UNION ALL 
                SELECT 
                    CONCAT('https://care-protocol.example/ontology/obs/', TRY_CAST(obs_id AS STRING)) AS subject,
                    'https://care-protocol.example/ontology/ofTest' AS predicate,
                    CONCAT('https://care-protocol.example/ontology/loinc/', TRY_CAST(loinc_code AS STRING)) AS object
                FROM src_13 AS rel_subquery
             UNION ALL 
                SELECT 
                    CONCAT('https://care-protocol.example/ontology/Patient/', TRY_CAST(patient_id AS STRING)) AS subject,
                    'https://care-protocol.example/ontology/prescribed' AS predicate,
                    CONCAT('https://care-protocol.example/ontology/rx/', TRY_CAST(rx_code AS STRING)) AS object
                FROM src_32 AS rel_subquery
             UNION ALL 
                SELECT 
                    CONCAT('https://care-protocol.example/ontology/DrugClass/', TRY_CAST(drug_class AS STRING)) AS subject,
                    'https://care-protocol.example/ontology/recommendedFor' AS predicate,
                    CONCAT('https://care-protocol.example/ontology/ValueSet/', TRY_CAST(vs_id AS STRING)) AS object
                FROM src_33 AS rel_subquery
             UNION ALL 
                SELECT 
                    CONCAT('https://care-protocol.example/ontology/DrugClass/', TRY_CAST(drug_class AS STRING)) AS subject,
                    'https://care-protocol.example/ontology/recommendedFor' AS predicate,
                    CONCAT('https://care-protocol.example/ontology/Measure/', TRY_CAST(measure_id AS STRING)) AS object
                FROM src_34 AS rel_subquery
             UNION ALL 
                SELECT 
                    CONCAT('https://care-protocol.example/ontology/icd/', TRY_CAST(icd_code AS STRING)) AS subject,
                    'https://care-protocol.example/ontology/subClassOf' AS predicate,
                    CONCAT('https://care-protocol.example/ontology/icd/', TRY_CAST(icd_parent AS STRING)) AS object
                FROM src_35 AS rel_subquery
            
        ) AS triples
        WHERE object IS NOT NULL AND TRIM(object) != ''