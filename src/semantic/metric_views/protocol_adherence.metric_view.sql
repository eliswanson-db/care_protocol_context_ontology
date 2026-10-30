-- Unity Catalog metric view: Protocol Step 3 adherence (the "A Monday with Genie" hero metric).
-- Process adherence: of A1c results above target (trigger), what share got a recheck/therapy change within 90 days?
-- This is the Metric View a scheduled Protocol Watch would monitor for drift. {catalog}/{schema} substituted.
CREATE OR REPLACE VIEW {catalog}.{schema}.protocol_adherence_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: {catalog}.{schema}.gold_protocol_adherence
comment: "Diabetes care-protocol Step 3 adherence: after an A1c above target (demo >=7%, story >9%), was there a recheck A1c or diabetes-therapy change within 90 days? The process-adherence layer that reveals WHICH step slipped. HEDIS-aligned demo, not NCQA-certified."
dimensions:
  - name: Measurement Year
    expr: measurement_year
    synonyms: [year, reporting year, MY]
    display_name: Measurement Year
  - name: Adherence Status
    expr: status
    comment: "MET = a recheck or therapy change occurred within 90 days of the high A1c; NOT_MET = the step was missed."
    synonyms: [status, step status, protocol status, followed up]
    display_name: Adherence Status
  - name: Follow-up Type
    expr: COALESCE(followup_type, 'none')
    comment: "What satisfied the step: recheck (a later A1c), therapy (a diabetes-med order), or none."
    synonyms: [followup, follow up type, how followed up]
    display_name: Follow-up Type
measures:
  - name: Trigger Events
    expr: COUNT(1)
    comment: "A1c results at/above the trigger threshold -- each one a protocol-step obligation (the denominator)."
    synonyms: [triggers, high a1c results, obligations, denominator]
    display_name: Trigger Events
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Followed Up In Time
    expr: COUNT(1) FILTER (WHERE followup_within_90d)
    comment: "Trigger events with a recheck or therapy change within 90 days (the numerator)."
    synonyms: [followed up, met, on time followups, numerator]
    display_name: Followed Up In Time
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Protocol Step 3 Adherence Rate
    expr: "MEASURE(`Followed Up In Time`) / MEASURE(`Trigger Events`)"
    comment: "Share of above-target A1c results that got a timely recheck/therapy change. Drops when the step drifts."
    synonyms: [protocol adherence rate, step 3 adherence, followup rate, adherence rate]
    display_name: Protocol Step 3 Adherence Rate
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: Avg Days To Follow-up
    expr: AVG(followup_days)
    comment: "Average days from the high A1c to the recheck/therapy change (among those followed up)."
    synonyms: [average followup days, time to followup, days to recheck]
    display_name: Avg Days To Follow-up
    format: {type: number, decimal_places: {type: max, places: 0}}
$$
