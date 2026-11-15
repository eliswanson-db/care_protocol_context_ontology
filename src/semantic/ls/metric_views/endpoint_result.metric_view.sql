-- Clinical Study lab: governed Week 24 endpoint metrics (SYNTHETIC). {catalog}/{schema}/{semantic_schema} are
-- substituted by apply_metric_views.py (schema=clinical_study, semantic_schema=clinical_study_semantic).
-- NEVER POOLED: every measure returns NULL unless the query is grouped/filtered to exactly ONE endpoint rule
-- version (which also fixes the study). Pooling R1 with R2 would count each participant twice; pooling CSL-A with
-- CSL-B would mix different endpoint definitions. NULL is the answer, not a silent average.
CREATE OR REPLACE VIEW {catalog}.{semantic_schema}.endpoint_result_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: >-
  SELECT r.*, p.ARMCD, p.SITEID, p.COUNTRY, p.FASFL, p.PPSFL
  FROM {catalog}.{schema}.gold_endpoint_result r
  JOIN {catalog}.{schema}.gold_participant_population p USING (USUBJID)
comment: "Week 24 percent change in body weight from baseline, one row per randomized participant x endpoint rule version (SYNTHETIC; ADaM-shaped, not submission-ready). Every measure is NULL unless exactly one rule version is in scope: always filter or group by `Rule Version`. Descriptive only; not evidence of efficacy."
dimensions:
  - name: Study
    expr: STUDYID
    comment: "Study identifier: CSL-A (72-week obesity study) or CSL-B (52-week type 2 diabetes study)."
    synonyms: [study, study id, trial, protocol]
  - name: Rule Version
    expr: endpoint_version
    comment: "Executable endpoint rule version: EP-A-WT24.R1 (±7 days), EP-A-WT24.R2 (±14 days, Amendment 1), EP-B-WT24.R1 (mean baseline, ±10 days). Required for every measure."
    synonyms: [rule version, endpoint version, definition version, R1, R2, analysis window version]
  - name: Protocol Version
    expr: protocol_version
    comment: "Protocol version the rule version implements (1.0, 2.0)."
    synonyms: [protocol version, amendment]
  - name: SAP Version
    expr: sap_version
    comment: "Statistical analysis plan version the rule version implements."
    synonyms: [sap version, analysis plan version]
  - name: Arm
    expr: ARMCD
    comment: "Randomized arm: CSL101 (CSL-101 10 mg once weekly) or PBO (placebo)."
    synonyms: [arm, treatment arm, treatment group, randomized arm]
  - name: Site
    expr: SITEID
    comment: "Investigational site."
    synonyms: [site, center, investigator site]
  - name: Country
    expr: COUNTRY
    comment: "Site country (ISO 3166 alpha-2)."
    synonyms: [country, region]
  - name: Result Status
    expr: result_status
    comment: "DERIVED, NO_VALID_BASELINE, NO_QUALIFYING_FOLLOWUP, NO_REFERENCE_DATE or NOT_IN_POPULATION."
    synonyms: [status, result status, derivation status, evaluable]
  - name: Exclusion Reason
    expr: exclusion_reason
    comment: "Why no endpoint was derived, e.g. NO_OBSERVATION_IN_WINDOW:closest_+10d (the closest follow-up was 10 days after the target)."
    synonyms: [reason, exclusion reason, missing reason, why not derived]
  - name: In FAS
    expr: FASFL
    comment: "Y if the participant is in the full analysis set (randomized and dosed)."
    synonyms: [fas, full analysis set, fas flag]
  - name: In PPS
    expr: PPSFL
    comment: "Y if the participant is in the per-protocol set (FAS without a major protocol deviation)."
    synonyms: [pps, per protocol, per-protocol set]
measures:
  - name: Participants Evaluated
    expr: CASE WHEN COUNT(DISTINCT endpoint_version) = 1 THEN COUNT(1) END
    comment: "Randomized participants with a result row under the rule version in scope."
    synonyms: [participants, randomized participants, n]
  - name: Participants In FAS
    expr: CASE WHEN COUNT(DISTINCT endpoint_version) = 1 THEN COUNT_IF(FASFL = 'Y') END
    comment: "Participants in the full analysis set (the endpoint population)."
    synonyms: [fas count, analysis population count, population size]
  - name: Participants With Valid Baseline
    expr: CASE WHEN COUNT(DISTINCT endpoint_version) = 1 THEN COUNT_IF(FASFL = 'Y' AND baseline_observation_id IS NOT NULL) END
    comment: "FAS participants with a valid baseline weight under the rule version."
    synonyms: [valid baseline, has baseline, baseline available]
  - name: Participants With Qualifying Week 24 Observation
    expr: CASE WHEN COUNT(DISTINCT endpoint_version) = 1 THEN COUNT_IF(FASFL = 'Y' AND followup_observation_id IS NOT NULL) END
    comment: "FAS participants with a follow-up weight inside the rule version's Week 24 analysis window."
    synonyms: [qualifying week 24, week 24 observation, in window, evaluable week 24]
  - name: Participants With Derived Endpoint
    expr: CASE WHEN COUNT(DISTINCT endpoint_version) = 1 THEN COUNT_IF(FASFL = 'Y' AND result_status = 'DERIVED') END
    comment: "FAS participants with a derived percent change (valid baseline AND qualifying follow-up)."
    synonyms: [derived, evaluable, with result, completers at week 24]
  - name: Endpoint Missingness Rate
    expr: CASE WHEN COUNT(DISTINCT endpoint_version) = 1 THEN 1 - COUNT_IF(FASFL = 'Y' AND result_status = 'DERIVED') / NULLIF(COUNT_IF(FASFL = 'Y'), 0) END
    comment: "Share of FAS participants with no derived endpoint (no imputation is done)."
    synonyms: [missingness, missing rate, missing data rate, percent missing]
  - name: Mean Percent Change
    expr: CASE WHEN COUNT(DISTINCT endpoint_version) = 1 THEN AVG(CASE WHEN FASFL = 'Y' THEN PCHG END) END
    comment: "Mean percent change in body weight among FAS participants with a derived result (unrounded; negative = weight loss). Descriptive; synthetic."
    synonyms: [mean change, average percent change, mean weight change, mean pchg]
  - name: Median Percent Change
    expr: CASE WHEN COUNT(DISTINCT endpoint_version) = 1 THEN PERCENTILE_APPROX(CASE WHEN FASFL = 'Y' THEN PCHG END, 0.5) END
    comment: "Median percent change among FAS participants with a derived result."
    synonyms: [median change, median percent change]
$$
