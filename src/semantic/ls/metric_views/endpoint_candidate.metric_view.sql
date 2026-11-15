-- Clinical Study lab: candidate observations and why they were selected or excluded (SYNTHETIC).
-- Measures are NULL unless exactly one rule version is in scope (each observation is evaluated once per version).
CREATE OR REPLACE VIEW {catalog}.{semantic_schema}.endpoint_candidate_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: >-
  SELECT c.*, concat(c.endpoint_id, '.', c.rule_version) AS endpoint_version
  FROM {catalog}.{schema}.gold_endpoint_candidate c
comment: "Every body-weight observation of every randomized participant, evaluated under each endpoint rule version, with its role (BASELINE/FOLLOWUP), decision (SELECTED / ELIGIBLE_NOT_SELECTED / EXCLUDED) and reason (SYNTHETIC). Measures are NULL unless exactly one `Rule Version` is in scope."
dimensions:
  - name: Study
    expr: STUDYID
    comment: "Study identifier (CSL-A or CSL-B)."
    synonyms: [study, trial]
  - name: Rule Version
    expr: endpoint_version
    comment: "Endpoint rule version the observation was evaluated under (EP-A-WT24.R1, EP-A-WT24.R2, EP-B-WT24.R1)."
    synonyms: [rule version, endpoint version, R1, R2]
  - name: Role
    expr: role
    comment: "BASELINE (on or before study day 1) or FOLLOWUP (after study day 1)."
    synonyms: [role, observation role]
  - name: Decision
    expr: decision
    comment: "SELECTED, ELIGIBLE_NOT_SELECTED or EXCLUDED."
    synonyms: [decision, selection, outcome]
  - name: Reason
    expr: reason
    comment: "Decision reason, e.g. OUTSIDE_FOLLOWUP_WINDOW, DUPLICATE_RECORD, UNSUPPORTED_UNIT, SAME_DAY_NO_TIME, FOLLOWUP_CLOSEST_TO_TARGET, FOLLOWUP_TIE_LOST."
    synonyms: [reason, exclusion reason, why excluded, why selected]
  - name: Visit
    expr: visit
    comment: "Visit label as recorded (dates decide qualification, not labels)."
    synonyms: [visit, visit name, visit label]
measures:
  - name: Observations
    expr: CASE WHEN COUNT(DISTINCT endpoint_version) = 1 THEN COUNT(1) END
    comment: "Weight observations evaluated under the rule version in scope."
    synonyms: [observations, records, weight records]
  - name: Excluded Observations
    expr: CASE WHEN COUNT(DISTINCT endpoint_version) = 1 THEN COUNT_IF(decision = 'EXCLUDED') END
    comment: "Observations excluded from the endpoint (invalid, duplicate, outside the window, etc.)."
    synonyms: [excluded, excluded observations, rejected records]
  - name: Selected Observations
    expr: CASE WHEN COUNT(DISTINCT endpoint_version) = 1 THEN COUNT_IF(decision = 'SELECTED') END
    comment: "Observations used as baseline or follow-up."
    synonyms: [selected, used observations]
  - name: Participants
    expr: CASE WHEN COUNT(DISTINCT endpoint_version) = 1 THEN COUNT(DISTINCT USUBJID) END
    comment: "Distinct participants with at least one observation in the group."
    synonyms: [participants, subjects]
$$
