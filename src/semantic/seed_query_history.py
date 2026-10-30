"""Seed SQL-warehouse query history with representative analyst questions (serverless task).

Why: the Genie Ontology indexes query history as a usage/snippet signal (roadmap S7a). Running a curated set
of realistic analytical queries ON A SQL WAREHOUSE records them in system.query.history, teaching the ontology
the vocabulary and the common joins/measures for this domain. Queries hit the governed metric views and gold
tables, so they double as known-good example SQL.

Reproducible-by-code: the query set lives here and runs via the SQL Statement Execution API against
${var.warehouse_id}. Re-runnable (idempotent — read-only SELECTs). See resources/jobs.yml (seed_query_history).
"""
import argparse

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

# {cat}/{sch} are substituted at runtime. Each entry is one analyst question -> SQL recorded in query history.
QUERIES = [
    # --- headline rates via the governed metric views (MEASURE) ---
    "SELECT MEASURE(`GSD Compliance Rate`) AS gsd_rate FROM {cat}.{sch}.gsd_compliance_metrics",
    "SELECT MEASURE(`KED Compliance Rate`) AS ked_rate FROM {cat}.{sch}.ked_compliance_metrics",
    "SELECT MEASURE(`BPD Compliance Rate`) AS bpd_rate FROM {cat}.{sch}.bpd_compliance_metrics",
    "SELECT `Age Band`, MEASURE(`GSD Compliance Rate`) AS rate FROM {cat}.{sch}.gsd_compliance_metrics GROUP BY `Age Band` ORDER BY `Age Band`",
    "SELECT `Age Band`, MEASURE(`KED Compliance Rate`) AS rate FROM {cat}.{sch}.ked_compliance_metrics GROUP BY `Age Band` ORDER BY `Age Band`",
    "SELECT `Age Band`, MEASURE(`BPD Compliance Rate`) AS rate FROM {cat}.{sch}.bpd_compliance_metrics GROUP BY `Age Band` ORDER BY `Age Band`",
    "SELECT MEASURE(`eGFR Test Rate`) AS egfr_rate, MEASURE(`uACR Test Rate`) AS uacr_rate FROM {cat}.{sch}.ked_compliance_metrics",
    "SELECT `Compliance Status`, MEASURE(`Eligible Patients`) AS patients FROM {cat}.{sch}.gsd_compliance_metrics GROUP BY `Compliance Status`",
    "SELECT MEASURE(`Avg Systolic`) AS avg_systolic, MEASURE(`Avg Diastolic`) AS avg_diastolic FROM {cat}.{sch}.bpd_compliance_metrics",
    "SELECT MEASURE(`Poor Control Patients`) AS poorly_controlled FROM {cat}.{sch}.gsd_compliance_metrics",
    # --- how many patients are eligible / compliant / in a care gap ---
    "SELECT COUNT(*) AS gsd_eligible FROM {cat}.{sch}.gold_adherence_gsd",
    "SELECT COUNT(*) AS gsd_care_gaps FROM {cat}.{sch}.gold_adherence_gsd WHERE status = 'NOT_MET'",
    "SELECT COUNT(*) AS ked_care_gaps FROM {cat}.{sch}.gold_adherence_ked WHERE status = 'NOT_MET'",
    "SELECT COUNT(*) AS bpd_care_gaps FROM {cat}.{sch}.gold_adherence_bpd WHERE status = 'NOT_MET'",
    "SELECT measure_id, status, COUNT(*) AS n FROM {cat}.{sch}.gold_adherence_gsd GROUP BY measure_id, status",
    "SELECT COUNT(DISTINCT patient_id) AS diabetes_patients FROM {cat}.{sch}.silver_diabetes_cohort",
    # --- which patients have a kidney-evaluation care gap and why ---
    "SELECT patient_id, age, egfr_flag, uacr_flag FROM {cat}.{sch}.gold_adherence_ked WHERE status = 'NOT_MET' ORDER BY age DESC",
    "SELECT patient_id, age, systolic, diastolic FROM {cat}.{sch}.gold_adherence_bpd WHERE status = 'NOT_MET' ORDER BY systolic DESC",
    "SELECT patient_id, evidence_value AS a1c FROM {cat}.{sch}.gold_adherence_gsd WHERE a1c_gt9 ORDER BY evidence_value DESC",
    # --- terminology / ontology questions ---
    "SELECT descendant_code, descendant_name FROM {cat}.{sch_term}.icd10_closure WHERE ancestor_code = 'E11' ORDER BY descendant_code",
    "SELECT COUNT(*) AS e11_subtree_size FROM {cat}.{sch_term}.icd10_closure WHERE ancestor_code = 'E11'",
    "SELECT segment_id, COUNT(*) AS codes FROM {cat}.{sch_term}.value_set_segment GROUP BY segment_id ORDER BY segment_id",
    "SELECT code, code_system FROM {cat}.{sch_term}.value_set_segment WHERE segment_id = 'KED_EGFR'",
    "SELECT loinc_code, long_common_name FROM {cat}.{sch_term}.loinc WHERE concept = 'A1C'",
    # --- labs feeding the measures ---
    "SELECT loinc_code, COUNT(*) AS results, COUNT(DISTINCT patient_id) AS patients FROM {cat}.{sch}.silver_observation GROUP BY loinc_code ORDER BY results DESC LIMIT 15",
    "SELECT COUNT(*) AS a1c_results FROM {cat}.{sch}.silver_observation WHERE loinc_code = '4548-4' AND year(result_ts) = 2025",
    "SELECT icd10_code, COUNT(*) AS diagnoses FROM {cat}.{sch}.silver_condition GROUP BY icd10_code ORDER BY diagnoses DESC LIMIT 15",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--warehouse_id", required=True)
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--schema", default="care_protocol")
    ap.add_argument("--schema_term", default="care_protocol_terminology")
    args = ap.parse_args()

    w = WorkspaceClient()
    ok = fail = 0
    for q in QUERIES:
        sql = q.format(cat=args.catalog, sch=args.schema, sch_term=args.schema_term)
        try:
            r = w.statement_execution.execute_statement(warehouse_id=args.warehouse_id, statement=sql,
                                                         wait_timeout="30s")
            state = r.status.state if r.status else None
            if state == StatementState.SUCCEEDED:
                ok += 1
            else:
                fail += 1
                print(f"  non-success ({state}): {sql[:80]}")
        except Exception as e:  # noqa: BLE001 — seeding is best-effort
            fail += 1
            print(f"  ERROR: {sql[:80]} -> {e}")

    print(f"Seeded query history: {ok} succeeded, {fail} failed, {len(QUERIES)} total (warehouse {args.warehouse_id}).")


if __name__ == "__main__":
    main()
