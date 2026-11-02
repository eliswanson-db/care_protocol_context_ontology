"""Drift Lab — the "A Monday with Genie" operational story, live.

The hero signal of the demo (ADR-0011/0012): protocol Step-3 (A1c follow-up within 90 days) adherence that
DRIFTS at one clinic mid-year and is MASKED by the annual ranking. The narrative beats:
  1. the annual ranking points at the wrong clinic (lowest overall rate — a trap),
  2. the Weekly Protocol Watch flags the clinic whose rate dropped vs ITS OWN baseline ("nobody asked"),
  3. that clinic's monthly trajectory shows the mid-year cliff,
  4. the root cause is a PCP handoff (panel_pcp_transition), confounded with case-mix.

All live over the shared catalog (same data on both workspaces).
"""
from fastapi import APIRouter

from ..config import CATALOG, MEASUREMENT_YEAR, SCHEMA, SCHEMA_TERM
from ..warehouse import run_sql

router = APIRouter()
C, S, ST = CATALOG, SCHEMA, SCHEMA_TERM


@router.get("/drift")
def drift():
    my = MEASUREMENT_YEAR

    # 1. Annual ranking — the trap: lowest overall Step-3 rate.
    annual = run_sql(
        f"""SELECT clinic_id,
                   ROUND(AVG(CASE WHEN followup_within_90d THEN 1.0 ELSE 0.0 END), 3) AS rate,
                   COUNT(*) AS triggers
            FROM {C}.{S}.gold_protocol_adherence
            WHERE measurement_year = :my
            GROUP BY clinic_id ORDER BY rate ASC""", {"my": my})

    # 2. The watch findings — biggest drop vs each clinic's own baseline first.
    findings = run_sql(
        f"""SELECT clinic_id, severity, month,
                   ROUND(t_rate, 3)   AS trailing_rate,
                   ROUND(baseline, 3) AS baseline,
                   ROUND(delta, 3)    AS delta,
                   baseline_n, censored, narrative
            FROM {C}.{S}.protocol_watch_findings
            ORDER BY delta DESC""", {})

    worst = findings[0] if findings else None
    clinic = worst["clinic_id"] if worst else None
    annual_rank = next((i + 1 for i, r in enumerate(annual) if r["clinic_id"] == clinic), None)

    # 3. The drifted clinic's monthly trajectory (the cliff).
    traj = run_sql(
        f"""SELECT date_trunc('month', trigger_ts) AS month, COUNT(*) AS triggers,
                   ROUND(AVG(CASE WHEN followup_within_90d THEN 1.0 ELSE 0.0 END), 3) AS rate
            FROM {C}.{S}.gold_protocol_adherence
            WHERE measurement_year = :my AND clinic_id = :c AND trigger_ts IS NOT NULL
            GROUP BY date_trunc('month', trigger_ts) ORDER BY month""",
        {"my": my, "c": clinic}) if clinic else []

    # 4. Root cause — the PCP handoff.
    transition = run_sql(
        f"""SELECT clinic_id, change_type, transition_date, recovery_days, narrative
            FROM {C}.{S}.panel_pcp_transition WHERE clinic_id = :c""", {"c": clinic}) if clinic else []

    # 4b. Case-mix confound — complication burden by clinic (a naive reader blames this, not the handoff).
    casemix = run_sql(
        f"""WITH dm AS (SELECT DISTINCT patient_id, clinic_id FROM {C}.{S}.gold_protocol_adherence
                        WHERE measurement_year = :my),
                 comp AS (SELECT DISTINCT c.patient_id FROM {C}.{S}.silver_condition c
                          JOIN {C}.{ST}.icd10_closure cl ON cl.descendant_code = c.icd10_code
                          WHERE cl.ancestor_code IN ('E11.2','E10.2','E13.2','E11.3','E10.3','E13.3',
                                                     'E11.4','E10.4','E13.4'))
            SELECT dm.clinic_id,
                   ROUND(AVG(CASE WHEN comp.patient_id IS NOT NULL THEN 1.0 ELSE 0.0 END), 3) AS complication_share,
                   COUNT(*) AS patients
            FROM dm LEFT JOIN comp USING (patient_id)
            GROUP BY dm.clinic_id ORDER BY complication_share DESC""", {"my": my})

    return {
        "measurement_year": my,
        "annual_ranking": annual,
        "annual_worst": annual[0] if annual else None,
        "findings": findings,
        "worst": worst,
        "worst_clinic": clinic,
        "worst_annual_rank": annual_rank,
        "trajectory": traj,
        "transition": transition[0] if transition else None,
        "casemix": casemix,
    }
