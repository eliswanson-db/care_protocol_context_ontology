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

-- gold_adherence_bpd: HEDIS BPD event log, one row per eligible diabetes patient (18-75).
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_bpd.patient_id IS 'Patient identifier (synthetic).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_bpd.measure_id IS 'HEDIS measure code. BPD = Blood Pressure control for Patients With Diabetes.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_bpd.age IS 'Patient age at the end of the measurement year. BPD eligibility requires 18-75.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_bpd.eligible_flag IS 'True when the patient is in the BPD denominator (diabetes cohort, aged 18-75).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_bpd.numerator_flag IS 'BPD numerator: true when the most recent measurement-year BP reading is controlled (systolic <140 AND diastolic <90).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_bpd.status IS 'Adherence status: MET (controlled) or NOT_MET (uncontrolled or no reading = care gap).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_bpd.bp_datetime IS 'Timestamp of the most recent paired BP reading in the measurement year. Record-level traceability.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_bpd.systolic IS 'Systolic blood pressure (LOINC 8480-6) of the latest measurement-year reading.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_bpd.diastolic IS 'Diastolic blood pressure (LOINC 8462-4) of the latest measurement-year reading.';

-- gold_adherence_spd: HEDIS SPD event log, one row per eligible diabetes patient (40-75).
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_spd.patient_id IS 'Patient identifier (synthetic).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_spd.measure_id IS 'HEDIS measure code. SPD = Statin Therapy for Patients With Diabetes.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_spd.age IS 'Patient age at the end of the measurement year. SPD eligibility requires 40-75.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_spd.eligible_flag IS 'True when the patient is in the SPD denominator (diabetes cohort, aged 40-75).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_spd.numerator_flag IS 'SPD numerator: true when a statin was dispensed in the measurement year (statins resolved via rxnorm_closure subsumption).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_spd.status IS 'Adherence status: MET (statin dispensed) or NOT_MET (no statin = care gap).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_spd.evidence_datetime IS 'Timestamp of the latest statin order in the measurement year. Record-level traceability.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_spd.evidence_code IS 'RxNorm clinical-drug code of the statin dispensed (e.g. 312961). Subsumed by a statin ingredient in rxnorm_closure.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_spd.evidence_drug IS 'Human-readable statin drug name of the latest order.';

-- gold_adherence_eed: HEDIS EED event log, one row per eligible diabetes patient (18-75).
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_eed.patient_id IS 'Patient identifier (synthetic).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_eed.measure_id IS 'HEDIS measure code. EED = Eye Exam for Patients With Diabetes.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_eed.age IS 'Patient age at the end of the measurement year. EED eligibility requires 18-75.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_eed.eligible_flag IS 'True when the patient is in the EED denominator (diabetes cohort, aged 18-75).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_eed.numerator_flag IS 'EED numerator: true when a retinal/diabetic eye exam (SNOMED procedure) is found in the measurement year.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_eed.status IS 'Adherence status: MET (eye exam found) or NOT_MET (no exam = care gap).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_eed.evidence_datetime IS 'Timestamp of the latest qualifying eye exam in the measurement year. Record-level traceability.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_eed.evidence_code IS 'SNOMED procedure code of the eye exam (e.g. 722161008 diabetic retinal eye exam).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_eed.evidence_exam IS 'Human-readable eye-exam procedure name of the latest exam.';

-- silver_procedure: conformed procedures (SNOMED) feeding EED.
COMMENT ON COLUMN {catalog}.care_protocol.silver_procedure.patient_id IS 'Patient the procedure belongs to.';
COMMENT ON COLUMN {catalog}.care_protocol.silver_procedure.proc_ts IS 'Timestamp the procedure was performed.';
COMMENT ON COLUMN {catalog}.care_protocol.silver_procedure.snomed_code IS 'SNOMED CT procedure code (e.g. 722161008 diabetic retinal eye exam). Code values only; no licensed SNOMED hierarchy shipped.';
COMMENT ON COLUMN {catalog}.care_protocol.silver_procedure.description IS 'Human-readable procedure description.';

-- icd10_closure comment also applies to rxnorm_closure (parallel subsumption structure).
COMMENT ON COLUMN {catalog}.care_protocol_terminology.rxnorm_closure.ancestor_code IS 'RxNorm ingredient rxcui (e.g. 36567 simvastatin). Join a value set of ingredients here to subsume all clinical drugs.';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.rxnorm_closure.descendant_code IS 'RxNorm clinical-drug rxcui (e.g. 312961 Simvastatin 20 MG) subsumed by the ingredient, matching prescription codes in bronze_order_med.';

-- gold_protocol_adherence: process-adherence (which protocol step slipped), one row per A1c trigger event.
COMMENT ON COLUMN {catalog}.care_protocol.gold_protocol_adherence.patient_id IS 'Patient the trigger belongs to.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_protocol_adherence.trigger_ts IS 'Timestamp of the A1c result at/above target that created the protocol-step obligation.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_protocol_adherence.trigger_a1c IS 'The A1c value that triggered the step (demo threshold >=7%; story uses >9%).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_protocol_adherence.followup_ts IS 'Timestamp of the earliest qualifying follow-up (recheck A1c or diabetes-therapy order) within 90 days; null if none.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_protocol_adherence.followup_type IS 'What satisfied the step: recheck (a later A1c) or therapy (a diabetes-med order).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_protocol_adherence.followup_days IS 'Days from the high A1c to the follow-up.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_protocol_adherence.followup_within_90d IS 'True if a qualifying follow-up occurred within 90 days (the protocol step was met).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_protocol_adherence.status IS 'MET = step followed in time; NOT_MET = the protocol step slipped (a care gap).';

-- gold_adherence_mad: Medication Adherence for Diabetes Medications (PDC), one row per eligible patient.
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_mad.patient_id IS 'Patient (diabetes cohort, 18+, >=2 diabetes-med fills).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_mad.fills IS 'Number of diabetes-med (biguanide) fills in the measurement year.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_mad.covered_days IS 'Days covered by medication in the measurement year (overlap-capped).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_mad.period_days IS 'Treatment-period days (first fill to year end).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_mad.pdc IS 'Proportion of days covered = covered_days / period_days. Adherent when >= 0.80.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_mad.numerator_flag IS 'True when PDC >= 0.80 (adherent).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_mad.status IS 'MET = PDC >= 80%; NOT_MET = refill/adherence gap.';

-- protocol_watch_findings: Weekly Protocol Watch output — one row per CLINIC-month drift (or a NO_DRIFT row), appended each run.
COMMENT ON COLUMN {catalog}.care_protocol.protocol_watch_findings.finding_type IS 'CLINIC_STEP_DRIFT = a clinic whose trailing-3-month Step-3 adherence fell below the peer baseline; NO_DRIFT = the watch ran and found nothing.';
COMMENT ON COLUMN {catalog}.care_protocol.protocol_watch_findings.severity IS 'HIGH (>=30 pts below baseline), MEDIUM (>=20), LOW (>=drift threshold), or NONE.';
COMMENT ON COLUMN {catalog}.care_protocol.protocol_watch_findings.clinic_id IS 'Clinic the finding concerns — the unit the watch scans. Clinic-level drift is masked in the global/annual view, so the watch scans per clinic.';
COMMENT ON COLUMN {catalog}.care_protocol.protocol_watch_findings.measure_id IS 'PROTO_STEP3 = the protocol Step-3 A1c-recheck follow-up.';
COMMENT ON COLUMN {catalog}.care_protocol.protocol_watch_findings.measurement_year IS 'HEDIS measurement year the watch scanned.';
COMMENT ON COLUMN {catalog}.care_protocol.protocol_watch_findings.month IS 'Last month of the trailing 3-month window this finding covers.';
COMMENT ON COLUMN {catalog}.care_protocol.protocol_watch_findings.t_trig IS 'Trigger events in the clinic''s trailing 3-month window (the denominator).';
COMMENT ON COLUMN {catalog}.care_protocol.protocol_watch_findings.t_follow IS 'Trailing-window triggers that got an A1c recheck within 90 days (the numerator).';
COMMENT ON COLUMN {catalog}.care_protocol.protocol_watch_findings.t_rate IS 'Trailing Step-3 adherence for the clinic = t_follow / t_trig.';
COMMENT ON COLUMN {catalog}.care_protocol.protocol_watch_findings.baseline IS 'The clinic''s OWN prior-period Step-3 adherence (the change reference). Drift means falling vs this, not merely being below peers; the peer baseline is cited in the narrative.';
COMMENT ON COLUMN {catalog}.care_protocol.protocol_watch_findings.baseline_n IS 'Trigger events in the clinic''s prior history (the baseline denominator).';
COMMENT ON COLUMN {catalog}.care_protocol.protocol_watch_findings.delta IS 'The clinic''s own prior baseline minus its trailing rate (the drift magnitude).';
COMMENT ON COLUMN {catalog}.care_protocol.protocol_watch_findings.censored IS 'True if the window is right-censored (its 90-day follow-up window is not fully inside the observed data); censored windows are excluded from detection.';
COMMENT ON COLUMN {catalog}.care_protocol.protocol_watch_findings.narrative IS 'Human-readable finding for the weekly summary (which clinic, how far below the peer baseline, what to investigate).';
COMMENT ON COLUMN {catalog}.care_protocol.protocol_watch_findings.as_of IS 'Timestamp this watch run executed. Append-only: each run is an as-of snapshot (the watch log).';
COMMENT ON COLUMN {catalog}.care_protocol.protocol_watch_findings.horizon_date IS 'Observation horizon used this run (latest trigger/follow-up date); drives the censoring cutoff.';
COMMENT ON COLUMN {catalog}.care_protocol.protocol_watch_findings.drift_threshold_pp IS 'Points-below-baseline threshold that defined a drift this run (demo default 0.15).';
COMMENT ON COLUMN {catalog}.care_protocol.protocol_watch_findings.min_triggers IS 'Small-N gate: clinic trailing windows with fewer triggers than this were not scored this run.';

-- Care-behavior model (ADR-0012): organizational dimensions + effective event layer + modeled attributes.
COMMENT ON COLUMN {catalog}.care_protocol.panel_roster.patient_id IS 'Cohort patient. One row per diabetes-cohort patient.';
COMMENT ON COLUMN {catalog}.care_protocol.panel_roster.clinic_id IS 'Clinic (site) the patient''s PCP belongs to. Clinics are ordered along a patient-complexity gradient; one clinic has a mid-year PCP handoff (see panel_pcp_transition).';
COMMENT ON COLUMN {catalog}.care_protocol.panel_roster.panel_id IS 'PCP panel the patient is attributed to (a PCP''s patient list).';
COMMENT ON COLUMN {catalog}.care_protocol.panel_roster.pcp_id IS 'Primary care provider for the panel.';
COMMENT ON COLUMN {catalog}.care_protocol.panel_roster.complexity IS 'Case-mix complexity = distinct ICD-10 codes the patient carries (a real confounder: the disrupted clinic is also the higher-complexity one).';
COMMENT ON COLUMN {catalog}.care_protocol.panel_roster.engagement IS 'Latent care-engagement propensity [0,1] (drives follow-up and adherence).';
COMMENT ON COLUMN {catalog}.care_protocol.panel_roster.provider_effect IS 'Panel/provider random effect (smooth spread of follow-up performance across panels).';
COMMENT ON COLUMN {catalog}.care_protocol.panel_roster.adherence_propensity IS 'Modeled medication-adherence propensity a_p (drives the PDC distribution).';
COMMENT ON COLUMN {catalog}.care_protocol.panel_roster.glycemic_poor IS 'Modeled poor-glycemic-control flag; GSD reads it as a1c_gt9 (keeps poor control decoupled from the observation stream).';
COMMENT ON COLUMN {catalog}.care_protocol.panel_roster.modeled_a1c IS 'Modeled latest A1c (%) for poor-control patients; GSD uses it as the evidence value for the control bands.';
COMMENT ON COLUMN {catalog}.care_protocol.panel_roster.is_handoff IS 'True if the patient''s clinic is the one with the mid-year PCP handoff (the drift source).';
COMMENT ON COLUMN {catalog}.care_protocol.panel_pcp_transition.clinic_id IS 'Clinic that experienced the mid-year PCP change.';
COMMENT ON COLUMN {catalog}.care_protocol.panel_pcp_transition.change_type IS 'Nature of the change (e.g. departure + locum coverage).';
COMMENT ON COLUMN {catalog}.care_protocol.panel_pcp_transition.transition_date IS 'Date the PCP change took effect (the drift onset).';
COMMENT ON COLUMN {catalog}.care_protocol.panel_pcp_transition.recovery_days IS 'Days over which the coverage gap recovers (the drift is gradual, not a cliff).';
COMMENT ON COLUMN {catalog}.care_protocol.panel_pcp_transition.narrative IS 'Plain-language account of the disruption — the root cause the watch / Genie can cite.';
COMMENT ON COLUMN {catalog}.care_protocol.care_order_results.loinc_code IS 'Effective observation layer = pristine bronze observations + model-generated MARKED A1c rechecks (ADR-0012). Feeds the silver/gold measures.';
COMMENT ON COLUMN {catalog}.care_protocol.care_order_med.rxnorm_code IS 'Effective medication layer = bronze meds with cohort diabetes-med orders replaced by modeled 30-day fills (realistic refill gaps -> continuous PDC).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_protocol_adherence.clinic_id IS 'Clinic the patient belongs to (join from panel_roster). The watch scans drift per clinic.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_protocol_adherence.panel_id IS 'PCP panel the patient belongs to.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_gsd.clinic_id IS 'Clinic the patient belongs to.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_gsd.panel_id IS 'PCP panel the patient belongs to.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_mad.clinic_id IS 'Clinic the patient belongs to.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_mad.panel_id IS 'PCP panel the patient belongs to.';

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

-- gold_lab_result: lab-observation fact grain enriched with LOINC multiaxial Parts (MV-2). Backs lab_result_metrics.
COMMENT ON COLUMN {catalog}.care_protocol.gold_lab_result.patient_id IS 'Patient the lab result belongs to.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_lab_result.encounter_id IS 'Encounter in which the lab was drawn.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_lab_result.result_ts IS 'Timestamp of the lab result.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_lab_result.measurement_year IS 'Calendar year of the result (YEAR(result_ts)); the grouping key for year-over-year lab volume.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_lab_result.loinc_code IS 'LOINC code of the specific test (e.g. 4548-4, 17856-6, 98979-8). Several codes can share one Component.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_lab_result.description IS 'Human-readable lab/test name as recorded on the observation.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_lab_result.component_code IS 'LOINC Component Part code (e.g. LP-HBA1C, LP-EGFR, LP-UACR) -- the multiaxial identity of WHAT is measured. Null when the LOINC code has no Part in the demo subset.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_lab_result.component IS 'LOINC Component Part name (e.g. Hemoglobin A1c/Hemoglobin.total). One Component spans every code/method measuring it -- the basis for "all A1c regardless of method".';
COMMENT ON COLUMN {catalog}.care_protocol.gold_lab_result.specimen_system IS 'LOINC System Part name -- the specimen/site (Blood, Serum or Plasma, Urine, Arterial system).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_lab_result.method IS 'LOINC Method Part name -- the assay/technique (HPLC, IFCC, MDRD, CKD-EPI). Same Component + different Method = same analyte, different measurement.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_lab_result.value_num IS 'Numeric result value (double). Comparable only within one Component/Code -- units differ across analytes.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_lab_result.units IS 'Result units of measure as recorded.';

-- Shared reporting-window columns on the remaining gold measures (GSD already documented above). Same
-- semantics across every HEDIS measure; kept identical so Genie reads one consistent definition.
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ked.period_start IS 'Start of the measurement-year reporting window (January 1).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ked.period_end IS 'End of the measurement-year reporting window (December 31). Age is evaluated at this date.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_bpd.measurement_year IS 'HEDIS measurement year the row is computed for (e.g. 2025).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_bpd.period_start IS 'Start of the measurement-year reporting window (January 1).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_bpd.period_end IS 'End of the measurement-year reporting window (December 31). Age is evaluated at this date.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_spd.measurement_year IS 'HEDIS measurement year the row is computed for (e.g. 2025).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_spd.period_start IS 'Start of the measurement-year reporting window (January 1).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_spd.period_end IS 'End of the measurement-year reporting window (December 31). Age is evaluated at this date.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_eed.measurement_year IS 'HEDIS measurement year the row is computed for (e.g. 2025).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_eed.period_start IS 'Start of the measurement-year reporting window (January 1).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_eed.period_end IS 'End of the measurement-year reporting window (December 31). Age is evaluated at this date.';

-- SSD: cross-domain behavioral-health measure (ADR-0017). care_ssd_cohort is synthesized; gold_adherence_ssd is the event log.
COMMENT ON TABLE {catalog}.care_protocol.care_ssd_cohort IS 'Synthesized SSD behavioral-health cohort (ADR-0017): SMI patients (F20/F25/F31) aged 18-64 on antipsychotics. Seeded/deterministic; screening is emergent, not injected. Synthetic; HEDIS-aligned (SSD-proxied); not NCQA-certified.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ssd.patient_id IS 'Patient identifier (synthetic). Member of the synthesized SSD behavioral-health cohort, not the diabetes cohort.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ssd.measure_id IS 'HEDIS measure code. SSD = Diabetes Screening for People With Schizophrenia or Bipolar Disorder Who Are Using Antipsychotic Medications.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ssd.measurement_year IS 'HEDIS measurement year the row is computed for (e.g. 2025).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ssd.age IS 'Patient age at the end of the measurement year. SSD eligibility requires 18-64.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ssd.eligible_flag IS 'True when the patient is in the SSD denominator: SMI diagnosis, antipsychotic dispensed, aged 18-64, and NOT excluded for pre-existing diabetes.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ssd.smi_dx IS 'True when the patient carries a serious-mental-illness diagnosis (schizophrenia F20 / schizoaffective F25 / bipolar F31). See smi_dx_code.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ssd.antipsychotic_dispensed IS 'True when an antipsychotic was dispensed in the measurement year. Re-derived through the RxNorm closure (ingredient -> clinical drug), like SPD resolves statins.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ssd.excluded_preexisting_dm IS 'HEDIS SSD exclusion flag. False on every eligible row (patients with pre-existing diabetes are already removed from the denominator). The exclusion is real diabetes-cohort (E10/E11/E13) overlap.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ssd.numerator_flag IS 'True when the patient meets the SSD numerator: a glucose or HbA1c screen (SSD_GLUCOSE_HBA1C) in the measurement year.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ssd.status IS 'Screening status: MET (glucose or HbA1c screen found in the measurement year) or NOT_MET (screening gap).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ssd.smi_dx_code IS 'ICD-10-CM SMI diagnosis code (F20.9 schizophrenia / F25.0 schizoaffective / F31.9 bipolar).';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ssd.antipsychotic_rxnorm IS 'RxNorm clinical-drug (SCD) code of the dispensed antipsychotic; subsumes to an antipsychotic ingredient via rxnorm_closure.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ssd.clinic_id IS 'Clinic (site) the SSD patient is seen at. Enables slicing the screening rate by site.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ssd.panel_id IS 'Care panel the SSD patient belongs to.';

-- gap_reason + site dimensions added to the 5 HEDIS measures (clinic breakdowns + care-gaps-by-reason).
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_gsd.gap_reason IS 'Reason the patient is a care gap (NULL when MET). GSD: "No A1c test in measurement year".';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ked.gap_reason IS 'Reason the patient is a care gap (NULL when MET). KED is compound: "No eGFR test" / "No uACR test" / "No eGFR or uACR test".';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_bpd.gap_reason IS 'Reason the patient is a care gap (NULL when MET). BPD: "No BP reading in measurement year" or "BP not controlled (>=140/90)".';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_spd.gap_reason IS 'Reason the patient is a care gap (NULL when MET). SPD: "No statin dispensed in measurement year".';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_eed.gap_reason IS 'Reason the patient is a care gap (NULL when MET). EED: "No diabetic eye exam in measurement year".';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_ked.clinic_id IS 'Clinic (site) the patient panel belongs to (joined from panel_roster). Enables KED care-gap rates by site.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_bpd.clinic_id IS 'Clinic (site) the patient panel belongs to (joined from panel_roster). Enables BPD control rates by site.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_spd.clinic_id IS 'Clinic (site) the patient panel belongs to (joined from panel_roster). Enables SPD care-gap rates by site.';
COMMENT ON COLUMN {catalog}.care_protocol.gold_adherence_eed.clinic_id IS 'Clinic (site) the patient panel belongs to (joined from panel_roster). Enables EED care-gap rates by site.';
