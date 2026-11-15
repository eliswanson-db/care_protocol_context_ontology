-- Clinical Study lab: screening, eligibility and analysis populations (SYNTHETIC).
-- Measures are NULL unless exactly one study is in scope (CSL-A and CSL-B have different eligibility rules).
CREATE OR REPLACE VIEW {catalog}.{semantic_schema}.participant_population_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: {catalog}.{schema}.gold_participant_population
comment: "One row per screened participant: rule-based eligibility at the protocol version in force at screening, randomization, FAS/PPS membership, and EDC-vs-rule reconciliation (SYNTHETIC). Measures are NULL unless exactly one `Study` is in scope."
dimensions:
  - name: Study
    expr: STUDYID
    comment: "Study identifier (CSL-A or CSL-B)."
    synonyms: [study, trial]
  - name: Protocol Version At Screening
    expr: protocol_version
    comment: "Protocol version in force on the screening date; decides which eligibility rule applies."
    synonyms: [protocol version, screening protocol version]
  - name: Eligibility Rule
    expr: eligibility_rule_id
    comment: "Approved eligibility rule version applied (ELIG-A-V1, ELIG-A-V2, ELIG-B-V1)."
    synonyms: [eligibility rule, criteria version]
  - name: Arm
    expr: ARMCD
    comment: "Randomized arm (CSL101 or PBO); empty for screen failures."
    synonyms: [arm, treatment arm]
  - name: Site
    expr: SITEID
    comment: "Investigational site."
    synonyms: [site, center]
  - name: Reconciliation
    expr: reconciliation
    comment: "CONSISTENT, ENROLLED_BUT_RULE_INELIGIBLE (enrolled in error) or RULE_ELIGIBLE_BUT_NOT_ENROLLED (non-protocol screen failure)."
    synonyms: [reconciliation, eligibility reconciliation, enrolled in error]
measures:
  - name: Screened Participants
    expr: CASE WHEN COUNT(DISTINCT STUDYID) = 1 THEN COUNT(1) END
    comment: "Participants screened."
    synonyms: [screened, screening count]
  - name: Rule Eligible Participants
    expr: CASE WHEN COUNT(DISTINCT STUDYID) = 1 THEN COUNT_IF(rule_eligible) END
    comment: "Participants who meet every criterion of the applicable eligibility rule, as derived from the ontology (not as recorded by the site)."
    synonyms: [eligible, rule eligible, meets criteria]
  - name: Randomized Participants
    expr: CASE WHEN COUNT(DISTINCT STUDYID) = 1 THEN COUNT_IF(randomized) END
    comment: "Participants randomized."
    synonyms: [randomized, enrolled]
  - name: FAS Participants
    expr: CASE WHEN COUNT(DISTINCT STUDYID) = 1 THEN COUNT_IF(FASFL = 'Y') END
    comment: "Full analysis set: randomized and dosed."
    synonyms: [fas, full analysis set]
  - name: PPS Participants
    expr: CASE WHEN COUNT(DISTINCT STUDYID) = 1 THEN COUNT_IF(PPSFL = 'Y') END
    comment: "Per-protocol set: FAS without a major protocol deviation."
    synonyms: [pps, per protocol set]
  - name: Enrolled In Error
    expr: CASE WHEN COUNT(DISTINCT STUDYID) = 1 THEN COUNT_IF(reconciliation = 'ENROLLED_BUT_RULE_INELIGIBLE') END
    comment: "Randomized although the applicable eligibility rule is not met (an eligibility-violation deviation)."
    synonyms: [enrolled in error, eligibility violations, ineligible enrolled]
  - name: Participants With Major Deviation
    expr: CASE WHEN COUNT(DISTINCT STUDYID) = 1 THEN COUNT_IF(FASFL = 'Y' AND PPSFL = 'N') END
    comment: "FAS participants excluded from the PPS by a major protocol deviation (eligibility violation or prohibited medication on treatment)."
    synonyms: [major deviations, protocol deviations, pps exclusions]
$$
