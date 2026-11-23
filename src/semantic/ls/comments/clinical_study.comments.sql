-- Column comments for the Clinical Study lab (SYNTHETIC). Applied by src/semantic/apply_comments.py --strict.
-- {catalog} substituted. One statement per line.
-- gold_endpoint_result
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.STUDYID IS 'Study identifier (CSL-A or CSL-B). Synthetic studies of the fictional compound CSL-101.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.USUBJID IS 'Unique participant identifier (CSL-<study>-<site>-<seq>; named fixtures use -FX-NN).';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.PARAMCD IS 'Analysis parameter code: WTPCHG24 = percent change in body weight from baseline to Week 24.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.endpoint_id IS 'Endpoint definition (EP-A-WT24 for CSL-A, EP-B-WT24 for CSL-B).';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.endpoint_version IS 'Executable rule version that produced this row (e.g. EP-A-WT24.R2). Never pool rows across rule versions.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.rule_version IS 'Rule version code within the endpoint (R1, R2).';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.protocol_version IS 'Protocol version the rule implements.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.sap_version IS 'Statistical analysis plan version the rule implements.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.analysis_population_status IS 'IN_FAS (randomized and dosed) or NOT_IN_FAS.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.reference_date IS 'First-dose date (study day 1) used as the time reference; NULL if the first-dose date is incomplete.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.followup_target_date IS 'Week 24 target date = reference date + the rule''s target offset.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.baseline_method IS 'last (CSL-A: last valid pre-treatment weight) or mean (CSL-B: mean of valid pre-treatment weights).';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.baseline_observation_id IS 'Observation id(s) used as baseline (comma-separated for the mean method). Joins silver_vs.CPL_OBS_ID.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.followup_observation_id IS 'Observation id used as the Week 24 follow-up. Joins silver_vs.CPL_OBS_ID.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.BASE IS 'Baseline body weight in kg.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.AVAL_FU IS 'Week 24 follow-up body weight in kg.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.PCHG IS 'Percent change in body weight from baseline, UNROUNDED: 100 * (AVAL_FU - BASE) / BASE. Negative = weight loss.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.PCHG_DISPLAY IS 'PCHG rounded to one decimal (half away from zero) for display only.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.result_status IS 'DERIVED, NO_VALID_BASELINE, NO_QUALIFYING_FOLLOWUP, NO_REFERENCE_DATE or NOT_IN_POPULATION.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.exclusion_reason IS 'Why no value was derived, e.g. NO_OBSERVATION_IN_WINDOW:closest_+10d.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.terminology_version IS 'CDISC Controlled Terminology release the units and test codes were checked against.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.engine_version IS 'Version of the deterministic endpoint engine.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_result.execution_run_id IS 'Content-addressed run id: the same rules, standards and data always give the same id.';
-- gold_endpoint_candidate
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_candidate.obs_id IS 'Standardized observation id (joins silver_vs.CPL_OBS_ID).';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_candidate.source_record_id IS 'Raw EDC source record id (bronze_edc_vs.record_id) the observation came from.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_candidate.role IS 'BASELINE (on or before study day 1) or FOLLOWUP (after study day 1).';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_candidate.decision IS 'SELECTED, ELIGIBLE_NOT_SELECTED or EXCLUDED under this rule version.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_candidate.reason IS 'Reason for the decision (e.g. OUTSIDE_FOLLOWUP_WINDOW, DUPLICATE_RECORD, FOLLOWUP_TIE_LOST, BASELINE_LAST_VALID).';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_candidate.days_from_target IS 'Follow-up date minus the Week 24 target date, in days (negative = before target).';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_candidate.study_day IS 'Study day of the observation (no day 0).';
COMMENT ON COLUMN {catalog}.clinical_study.gold_endpoint_candidate.weight_kg IS 'Weight converted to kg; NULL when the value or unit is invalid.';
-- gold_participant_population
COMMENT ON COLUMN {catalog}.clinical_study.gold_participant_population.rule_eligible IS 'True when every criterion of the applicable eligibility rule is met, derived from MH/CM records and the ontology.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_participant_population.edc_eligible IS 'Eligibility as recorded by the site in EDC (Y/N). Compare with rule_eligible.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_participant_population.protocol_version IS 'Protocol version in force on the screening date (decides the eligibility rule).';
COMMENT ON COLUMN {catalog}.clinical_study.gold_participant_population.eligibility_rule_id IS 'Approved eligibility rule version applied (ELIG-A-V1, ELIG-A-V2, ELIG-B-V1).';
COMMENT ON COLUMN {catalog}.clinical_study.gold_participant_population.FASFL IS 'Full analysis set flag (Y = randomized and dosed).';
COMMENT ON COLUMN {catalog}.clinical_study.gold_participant_population.PPSFL IS 'Per-protocol set flag (Y = FAS without a major protocol deviation).';
COMMENT ON COLUMN {catalog}.clinical_study.gold_participant_population.reconciliation IS 'CONSISTENT, ENROLLED_BUT_RULE_INELIGIBLE or RULE_ELIGIBLE_BUT_NOT_ENROLLED.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_participant_population.deviations IS 'Major protocol deviations with evidence record and ontology path (eligibility violation, prohibited medication on treatment).';
-- gold_eligibility_criterion
COMMENT ON COLUMN {catalog}.clinical_study.gold_eligibility_criterion.criterion_id IS 'Criterion code (INC-AGE, INC-BMI, INC-T2D, EXC-MH, EXC-CI, EXC-CM).';
COMMENT ON COLUMN {catalog}.clinical_study.gold_eligibility_criterion.outcome IS 'MET / NOT_MET (inclusion) or TRIGGERED / NOT_TRIGGERED (exclusion); NOT_EVALUABLE if data are missing.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_eligibility_criterion.evidence IS 'Source record ids (MH, CM, VS) the decision used.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_eligibility_criterion.path IS 'Ontology path that decided it, e.g. a MONDO is_a chain to a class root, or MONDO -> MeSH -> MED-RT CI_with -> drug.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_eligibility_criterion.path_labels IS 'Human-readable labels for each step of path.';
-- gold_amendment_impact
COMMENT ON COLUMN {catalog}.clinical_study.gold_amendment_impact.endpoint_became_derivable IS 'True if no endpoint under R1 but derived under R2 (Amendment 1 widened the window).';
COMMENT ON COLUMN {catalog}.clinical_study.gold_amendment_impact.selected_followup_changed IS 'True if the follow-up observation used differs between R1 and R2 (including none -> one).';
COMMENT ON COLUMN {catalog}.clinical_study.gold_amendment_impact.endpoint_value_changed IS 'True if the percent change differs between R1 and R2 (including NULL -> value).';
COMMENT ON COLUMN {catalog}.clinical_study.gold_amendment_impact.eligible_candidates_changed IS 'True if R2 admits additional eligible follow-up candidates.';
COMMENT ON COLUMN {catalog}.clinical_study.gold_amendment_impact.explanation IS 'Plain-language reason for the change for this participant.';
-- silver_vs
COMMENT ON COLUMN {catalog}.clinical_study.silver_vs.VSTESTCD IS 'CDISC CT vital-signs test code (WEIGHT, HEIGHT, WSTCIR, SYSBP, DIABP, PULSE). HEIGHT is recorded once, at screening. BMI is not collected; it is calculated as weight (kg) / height (m) squared.';
COMMENT ON COLUMN {catalog}.clinical_study.silver_vs.VSORRES IS 'Result as collected.';
COMMENT ON COLUMN {catalog}.clinical_study.silver_vs.VSORRESU IS 'Unit as collected, mapped to a CDISC CT VSRESU submission value (kg, LB, g, cm, in, mmHg, beats/min); unmapped raw units are kept as recorded.';
COMMENT ON COLUMN {catalog}.clinical_study.silver_vs.VSSTRESN IS 'Numeric result in the standard unit (weight in kg: LB x 0.45359237, g x 0.001; height and waist circumference in cm: in x 2.54).';
COMMENT ON COLUMN {catalog}.clinical_study.silver_vs.VSDY IS 'Study day (no day 0).';
COMMENT ON COLUMN {catalog}.clinical_study.silver_vs.CPL_OBS_ID IS 'Demo-extension observation id (USUBJID.VSTESTCD.VSSEQ).';
COMMENT ON COLUMN {catalog}.clinical_study.silver_vs.CPL_RAW_UNIT IS 'Demo extension: the unit string exactly as keyed at the site.';
COMMENT ON COLUMN {catalog}.clinical_study.silver_vs.CPL_UNIT_MAPPING_STATUS IS 'Demo extension: MAPPED, UNMAPPED_RAW_UNIT or MISSING.';
COMMENT ON COLUMN {catalog}.clinical_study.silver_vs.CPL_SOURCE_RECORD_ID IS 'Demo extension: raw EDC record id for lineage.';
