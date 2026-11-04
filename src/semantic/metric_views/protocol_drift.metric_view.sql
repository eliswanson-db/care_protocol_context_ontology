-- Unity Catalog metric view: Protocol Step-3 DRIFT (the "nobody asked, Genie noticed" signal, computed LIVE).
-- Experimental window measures (version 0.1): each clinic's TRAILING-3-month adherence vs its OWN all-time
-- baseline, so a recent drop surfaces even when the annual ranking hides it mid-pack. This replaces the need for
-- a precomputed watch-findings table -- the drift is a live metric-view query. {catalog}/{schema}/{semantic_schema} substituted.
CREATE OR REPLACE VIEW {catalog}.{semantic_schema}.protocol_drift_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 0.1
source: {catalog}.{schema}.gold_protocol_adherence
dimensions:
  - name: Clinic
    expr: clinic_id
  - name: Month
    expr: "date_trunc('MONTH', trigger_ts)"
measures:
  - name: Triggers (trailing 3mo)
    expr: COUNT(1)
    window:
      - order: Month
        range: trailing 3 month
        semiadditive: last
  - name: Followed (trailing 3mo)
    expr: COUNT(1) FILTER (WHERE followup_within_90d)
    window:
      - order: Month
        range: trailing 3 month
        semiadditive: last
  - name: Adherence (trailing 3mo)
    expr: "try_divide(MEASURE(`Followed (trailing 3mo)`), MEASURE(`Triggers (trailing 3mo)`))"
  - name: Triggers (all-time)
    expr: COUNT(1)
    window:
      - order: Month
        range: all
        semiadditive: last
  - name: Followed (all-time)
    expr: COUNT(1) FILTER (WHERE followup_within_90d)
    window:
      - order: Month
        range: all
        semiadditive: last
  - name: Adherence (baseline)
    expr: "try_divide(MEASURE(`Followed (all-time)`), MEASURE(`Triggers (all-time)`))"
  - name: Drift (trailing vs baseline)
    expr: "MEASURE(`Adherence (trailing 3mo)`) - MEASURE(`Adherence (baseline)`)"
$$
