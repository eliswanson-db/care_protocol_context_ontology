-- Clinical Study lab: Amendment 1 impact on the CSL-A Week 24 endpoint, R1 (±7 d) -> R2 (±14 d). SYNTHETIC.
CREATE OR REPLACE VIEW {catalog}.{semantic_schema}.amendment_impact_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: >-
  SELECT a.*, d.SITEID, d.ARMCD, concat('EP-A-WT24.', a.from_rule_version, ' -> EP-A-WT24.', a.to_rule_version) AS comparison
  FROM {catalog}.{schema}.gold_amendment_impact a
  JOIN {catalog}.{schema}.silver_dm d USING (USUBJID)
comment: "CSL-A Amendment 1 impact, one row per randomized CSL-A participant comparing endpoint rule version R1 (±7-day Week 24 window) with R2 (±14-day window): whether the endpoint became derivable, the selected follow-up observation changed, the eligible candidate set changed, or the value changed (SYNTHETIC). Nothing else in the rule changed between versions."
dimensions:
  - name: Comparison
    expr: comparison
    comment: "The two rule versions compared (EP-A-WT24.R1 -> EP-A-WT24.R2)."
    synonyms: [comparison, amendment, rule change]
  - name: Site
    expr: SITEID
    comment: "Investigational site. Most participants recovered by Amendment 1 are at one site whose Week 24 visits ran 8 to 13 days late."
    synonyms: [site, center]
  - name: Arm
    expr: ARMCD
    comment: "Randomized arm (CSL101 or PBO)."
    synonyms: [arm, treatment arm]
  - name: Status Under R1
    expr: status_from
    comment: "Result status under the original rule version."
    synonyms: [status before, original status, R1 status]
  - name: Status Under R2
    expr: status_to
    comment: "Result status under the amended rule version."
    synonyms: [status after, amended status, R2 status]
  - name: Explanation
    expr: explanation
    comment: "Plain-language reason for the change for this participant."
    synonyms: [why, explanation, reason for change]
measures:
  - name: Participants Compared
    expr: COUNT(1)
    comment: "Randomized CSL-A participants compared across the two rule versions."
    synonyms: [participants compared, n]
  - name: Participants Became Derivable
    expr: COUNT_IF(endpoint_became_derivable)
    comment: "No derived endpoint under R1, derived under R2."
    synonyms: [recovered, became evaluable, newly derived, gained a result]
  - name: Participants With Changed Selected Observation
    expr: COUNT_IF(selected_followup_changed)
    comment: "The follow-up observation used for the endpoint differs between R1 and R2 (includes none -> some)."
    synonyms: [changed selection, different follow-up record, changed selected observation]
  - name: Participants With Changed Endpoint Value
    expr: COUNT_IF(endpoint_value_changed)
    comment: "The percent change differs between R1 and R2 (includes NULL -> value)."
    synonyms: [changed value, changed result, value changed]
  - name: Participants With Changed Eligible Candidates
    expr: COUNT_IF(eligible_candidates_changed)
    comment: "R2 admits at least one additional eligible follow-up candidate (the selected one may not change)."
    synonyms: [more candidates, candidate set changed, affected by amendment]
$$
