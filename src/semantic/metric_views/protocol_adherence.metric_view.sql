-- Unity Catalog metric view: Protocol Step 3 adherence (the "A Monday with Genie" hero metric).
-- Process adherence: of A1c results above target (trigger), what share got a recheck/therapy change within 90 days?
-- This is the Metric View a scheduled Protocol Watch would monitor for drift. {catalog}/{schema}/{semantic_schema} substituted.
CREATE OR REPLACE VIEW {catalog}.{semantic_schema}.protocol_adherence_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: {catalog}.{schema}.gold_protocol_adherence
comment: "Diabetes care-protocol Step 3 adherence: after an A1c result >= 9% (poor control), was there a follow-up A1c within 90 days? The process-adherence layer that reveals WHICH step slipped. HEDIS-aligned demo, not NCQA-certified."
dimensions:
  - name: Measurement Year
    expr: measurement_year
    synonyms: [year, reporting year, MY]
    display_name: Measurement Year
  - name: Clinic
    expr: clinic_id
    comment: "Clinic (site) the patient belongs to. Protocol-step drift is a CLINIC-level signal (masked in the global/annual view), so slice by this to find which site slipped."
    synonyms: [clinic, site, location, facility]
    display_name: Clinic
  - name: Panel
    expr: panel_id
    comment: "PCP panel the patient belongs to."
    synonyms: [panel, pcp panel, provider panel, care team]
    display_name: Panel
  - name: Adherence Status
    expr: "CASE WHEN followup_within_90d THEN 'MET' WHEN window_closed THEN 'NOT_MET' ELSE 'OPEN' END"
    comment: "MET = a follow-up A1c within 90 days of the >= 9% result; NOT_MET = the 90-day window closed with none; OPEN = window still open (year-to-date) and no follow-up yet -- still closable."
    synonyms: [status, step status, protocol status, followed up]
    display_name: Adherence Status
  - name: Follow-up Type
    expr: COALESCE(followup_type, 'none')
    comment: "What satisfied the step: recheck (a follow-up A1c), or none."
    synonyms: [followup, follow up type, how followed up]
    display_name: Follow-up Type
measures:
  - name: Trigger Events
    expr: COUNT(1) FILTER (WHERE window_closed)
    comment: "Closed Step-3 obligations: A1c >= 9% results whose 90-day window has closed (the denominator). Open windows are excluded -- counting early successes but not yet-unknown misses would inflate recent rates."
    synonyms: [triggers, high a1c results, obligations, denominator]
    display_name: Trigger Events
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Followed Up In Time
    expr: COUNT(1) FILTER (WHERE window_closed AND followup_within_90d)
    comment: "Obligations met: a follow-up A1c within 90 days of the >= 9% result (the numerator)."
    synonyms: [followed up, met, on time followups, numerator]
    display_name: Followed Up In Time
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Protocol Step 3 Adherence Rate
    expr: "MEASURE(`Followed Up In Time`) / MEASURE(`Trigger Events`)"
    comment: "Share of closed Step-3 obligations followed up within 90 days. Drops when the step drifts."
    synonyms: [protocol adherence rate, step 3 adherence, followup rate, adherence rate]
    display_name: Protocol Step 3 Adherence Rate
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: Open Obligations
    expr: COUNT(1) FILTER (WHERE NOT followup_within_90d AND NOT window_closed)
    comment: "A1c >= 9% results whose 90-day follow-up window is still open and not yet met -- the members still closable this year."
    synonyms: [open, pending, closable, still closable, open gaps, due follow-ups]
    display_name: Open Obligations
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Avg Days To Follow-up
    expr: AVG(followup_days)
    comment: "Average days from the high A1c to the recheck/therapy change (among those followed up)."
    synonyms: [average followup days, time to followup, days to recheck]
    display_name: Avg Days To Follow-up
    format: {type: number, decimal_places: {type: max, places: 0}}
$$
