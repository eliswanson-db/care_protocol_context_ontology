"""The three HEDIS traces (docs/CONTEXT_LAB_PLAN.md §3). Each follows one piece of information from its source
through the medallion layers into the retrieval modes, using the Tracer Journey's existing live stages.

Heroes are picked from the data by a fixed rule (lowest patient_id that qualifies), never by a hard-coded id, so
a data regeneration keeps the trace meaningful.

  a1c   one A1c result: raw lab -> bronze -> silver -> GSD evidence -> poor control (> 9%) + a Step-3 recheck
  dx    one diagnosis code, E11.22: ICD-10 hierarchy with two parents -> diabetes AND CKD -> measure cohorts
  rule  one care-protocol rule, metformin contraindicated at eGFR < 30 -> applied to a patient on metformin
"""

from __future__ import annotations

from .config import CATALOG, MEASUREMENT_YEAR, SCHEMA, SCHEMA_TERM

C, S, ST, MY = CATALOG, SCHEMA, SCHEMA_TERM, MEASUREMENT_YEAR
EGFR_CODES = "('98979-8', '33914-3')"
DX_CODE = "E11.22"

_PRIM = (f"SELECT patient_id, MIN(icd10_code) FILTER (WHERE onset_date <= DATE'{MY}-12-31') AS prim "
         f"FROM {C}.{S}.bronze_pat_enc_dx WHERE icd10_code LIKE 'E1%' GROUP BY patient_id")

TRACES: dict[str, dict] = {
    "a1c": {
        "title": "An A1c result",
        "summary": "One lab value becomes GSD poor control and a Protocol Step-3 recheck obligation.",
        "stages": ["protocol", "raw", "bronze", "silver", "gold", "metric", "page", "rag", "closure_ret",
                   "ontobricks"],
        # A GSD-eligible patient whose latest MY A1c is above 9% (an observed result and a Step-3 trigger).
        "hero_sql": f"""
            SELECT g.patient_id, g.clinic_id, g.age, CAST(g.evidence_value AS STRING) AS value,
                   CAST(g.evidence_datetime AS DATE) AS on_date
            FROM {C}.{S}.gold_adherence_gsd g
            JOIN {C}.{S}.gold_protocol_adherence p ON p.patient_id = g.patient_id AND p.trigger_ts = g.evidence_datetime
            WHERE g.measurement_year = {MY} AND g.evidence_value > 9.0 AND p.window_closed
            ORDER BY g.patient_id LIMIT 1""",
        "chips": lambda h: [f"A1c {h['value']}%", str(h["on_date"]), h["clinic_id"], f"age {h['age']}"],
        "question": lambda h: (f"Patient {h['patient_id'][:8]}'s latest A1c was {h['value']}% on {h['on_date']}. "
                               f"What does that mean for GSD and for the care protocol?"),
        "rag_question": ("What A1c level is poor glycemic control, and when must A1c be rechecked after a poorly "
                         "controlled result?"),
    },
    "dx": {
        "title": "A diagnosis code: E11.22",
        "summary": "One code sits under two parents, so it puts a patient in a diabetes cohort and a CKD cohort.",
        "stages": ["protocol", "raw", "bronze", "silver", "closure", "cohort", "page", "rag", "closure_ret",
                   "ontobricks"],
        # A patient whose primary diabetes code is E11.22 and who is in the KED and SPD denominators.
        "hero_sql": f"""
            WITH prim AS ({_PRIM})
            SELECT prim.patient_id, ked.clinic_id, ked.age, '{DX_CODE}' AS code
            FROM prim
            JOIN {C}.{S}.gold_adherence_ked ked ON ked.patient_id = prim.patient_id AND ked.measurement_year = {MY}
            JOIN {C}.{S}.gold_adherence_spd spd ON spd.patient_id = prim.patient_id AND spd.measurement_year = {MY}
            WHERE prim.prim = '{DX_CODE}'
            ORDER BY prim.patient_id LIMIT 1""",
        "chips": lambda h: [h["code"], "type 2 diabetes with diabetic CKD", h["clinic_id"], f"age {h['age']}"],
        "question": lambda h: (f"Patient {h['patient_id'][:8]} is coded {DX_CODE}. Which cohorts and measures does "
                               f"that one code put them in, and why?"),
        "rag_question": ("Which ICD-10 codes define the diabetes population, and which drug classes does the care "
                         "protocol recommend for diabetes with chronic kidney disease?"),
    },
    "rule": {
        "title": "A care-protocol rule: metformin at eGFR < 30",
        "summary": "One sentence in the protocol, followed into every mode and applied to a patient it affects.",
        "stages": ["protocol", "bronze", "silver", "closure_ret", "page", "rag", "ontobricks"],
        # A patient with a metformin order active in the MY whose latest eGFR (taken after that order) is below 30.
        "hero_sql": f"""
            WITH met AS (
              SELECT m.patient_id, max(m.start_ts) AS last_start, max_by(m.description, m.start_ts) AS drug
              FROM {C}.{S}.bronze_order_med m
              JOIN {C}.{ST}.rxnorm_closure c ON c.descendant_code = m.rxnorm_code AND c.ancestor_code = 'DRUGCLASS-BIGUANIDE'
              WHERE m.stop_ts IS NULL OR m.stop_ts >= TIMESTAMP'{MY}-01-01'
              GROUP BY m.patient_id),
            egfr AS (
              SELECT patient_id, max_by(value_num, result_ts) AS value, max(result_ts) AS ts
              FROM {C}.{S}.silver_observation WHERE loinc_code IN {EGFR_CODES} GROUP BY patient_id)
            SELECT met.patient_id, met.drug, CAST(egfr.value AS STRING) AS value, CAST(egfr.ts AS DATE) AS on_date
            FROM met JOIN egfr USING (patient_id)
            WHERE egfr.value < 30 AND year(egfr.ts) = {MY} AND egfr.ts > met.last_start
            ORDER BY met.patient_id LIMIT 1""",
        "chips": lambda h: [h["drug"][:40], f"eGFR {h['value']}", str(h["on_date"])],
        "question": lambda h: (f"Patient {h['patient_id'][:8]} is on metformin and their latest eGFR is {h['value']}. "
                               f"Does the care protocol allow that, and where is the rule written?"),
        "rag_question": "When is metformin contraindicated for a patient with diabetes and reduced kidney function?",
    },
}


def get(trace: str) -> dict:
    return TRACES.get(trace) or TRACES["a1c"]
