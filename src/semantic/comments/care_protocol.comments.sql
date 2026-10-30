-- Column-level UC comments for the care_protocol (silver/gold) schema. Ontology fuel: Genie indexes these.
-- {catalog} substituted by apply_comments.py. One statement per line, ';'-terminated. Idempotent (COMMENT ON overwrites).

-- gold_adherence_gsd: HEDIS GSD event log, one row per eligible diabetes patient (18-75).
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_gsd.patient_id IS 'Patient identifier (synthetic, Synthea-generated). Joins to bronze_patient and the silver layer.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_gsd.measure_id IS 'HEDIS measure code. GSD = Glycemic Status Assessment for Patients With Diabetes.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_gsd.measurement_year IS 'HEDIS measurement year the row is computed for (e.g. 2025).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_gsd.period_start IS 'Start of the measurement-year reporting window (January 1).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_gsd.period_end IS 'End of the measurement-year reporting window (December 31). Age is evaluated at this date.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_gsd.age IS 'Patient age at the end of the measurement year. GSD eligibility requires 18-75.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_gsd.eligible_flag IS 'True when the patient is in the GSD denominator (diabetes cohort, aged 18-75).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_gsd.numerator_flag IS 'True when the patient meets the GSD numerator: at least one A1c (HbA1c) test in the measurement year.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_gsd.status IS 'Adherence status: MET (A1c test found in the measurement year) or NOT_MET (care gap).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_gsd.evidence_datetime IS 'Timestamp of the latest qualifying A1c result in the measurement year. Record-level traceability for the numerator.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_gsd.evidence_code IS 'LOINC code of the A1c test that satisfied the numerator (e.g. 4548-4). Links to the terminology layer.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_gsd.evidence_value IS 'Numeric A1c result (%) of the latest measurement-year test. Basis for the glycemic-control bands.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_gsd.a1c_lt8 IS 'Good glycemic control: latest measurement-year A1c is below 8.0%.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_gsd.a1c_gt9 IS 'Poor glycemic control: latest measurement-year A1c is above 9.0%.';

-- gold_adherence_ked: HEDIS KED event log, one row per eligible diabetes patient (18-85). Compound numerator.
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ked.patient_id IS 'Patient identifier (synthetic). Joins to bronze_patient and the silver layer.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ked.measure_id IS 'HEDIS measure code. KED = Kidney Health Evaluation for Patients With Diabetes.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ked.measurement_year IS 'HEDIS measurement year the row is computed for.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ked.age IS 'Patient age at the end of the measurement year. KED eligibility requires 18-85.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ked.eligible_flag IS 'True when the patient is in the KED denominator (diabetes cohort, aged 18-85).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ked.egfr_flag IS 'True when the patient has an eGFR (estimated glomerular filtration rate) test in the measurement year.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ked.uacr_flag IS 'True when the patient has a uACR (urine albumin-creatinine ratio) test in the measurement year.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ked.numerator_flag IS 'KED numerator: true only when BOTH egfr_flag AND uacr_flag are true (complete kidney health evaluation).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ked.status IS 'Adherence status: MET (both eGFR and uACR found) or NOT_MET (one or both missing = care gap).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ked.egfr_datetime IS 'Timestamp of the latest eGFR result in the measurement year. Record-level traceability.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ked.egfr_code IS 'LOINC code of the eGFR test (e.g. 33914-3 MDRD, or 98979-8). The value set spans code vintages.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ked.egfr_value IS 'Numeric eGFR result (mL/min/1.73m2) of the latest measurement-year test.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ked.uacr_datetime IS 'Timestamp of the latest uACR result in the measurement year. Record-level traceability.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ked.uacr_code IS 'LOINC code of the uACR test (e.g. 14959-1 Microalbumin/Creatinine ratio).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ked.uacr_value IS 'Numeric uACR result of the latest measurement-year test.';

-- silver_condition: conformed diabetes diagnoses, ICD-10-CM mapped from SNOMED.
COMMENT ON COLUMN {catalog}.care_protocol.silver_condition.patient_id IS 'Patient identifier the diagnosis belongs to.';
COMMENT ON COLUMN {catalog}.care_protocol.silver_condition.encounter_id IS 'Encounter in which the diagnosis was recorded.';
COMMENT ON COLUMN {catalog}.care_protocol.silver_condition.onset_date IS 'Date the condition was first recorded.';
COMMENT ON COLUMN {catalog}.care_protocol.silver_condition.snomed_code IS 'Source SNOMED CT concept from Synthea (pre-crosswalk).';
COMMENT ON COLUMN {catalog}.care_protocol.silver_condition.icd10_code IS 'ICD-10-CM code crosswalked from SNOMED. Drives cohort membership via the ICD-10 hierarchy closure.';
COMMENT ON COLUMN {catalog}.care_protocol.silver_condition.description IS 'Human-readable diagnosis description.';

-- silver_observation: conformed lab observations (LOINC) with numeric value.
COMMENT ON COLUMN {catalog}.care_protocol.silver_observation.patient_id IS 'Patient the observation belongs to.';
COMMENT ON COLUMN {catalog}.care_protocol.silver_observation.encounter_id IS 'Encounter in which the observation was taken.';
COMMENT ON COLUMN {catalog}.care_protocol.silver_observation.result_ts IS 'Timestamp of the lab result.';
COMMENT ON COLUMN {catalog}.care_protocol.silver_observation.loinc_code IS 'LOINC code identifying the lab test (e.g. 4548-4 = Hemoglobin A1c).';
COMMENT ON COLUMN {catalog}.care_protocol.silver_observation.description IS 'Human-readable lab/test name.';
COMMENT ON COLUMN {catalog}.care_protocol.silver_observation.value_num IS 'Numeric result value (cast to double).';
COMMENT ON COLUMN {catalog}.care_protocol.silver_observation.units IS 'Result units of measure.';

-- silver_diabetes_cohort: patients with a diabetes diagnosis under E10/E11/E13 via the ICD-10 closure.
COMMENT ON COLUMN {catalog}.care_protocol.silver_diabetes_cohort.patient_id IS 'Distinct patients in the diabetes cohort, resolved by subsumption over the ICD-10-CM hierarchy (E10/E11/E13 and all descendants).';
