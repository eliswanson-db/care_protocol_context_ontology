"""The throughline (Tracer Journey) API — one patient's data as it passes through every semantic layer.

Spine: raw code (bronze) -> conformed condition (silver) -> ICD-10 subsumption (closure) -> cohort ->
HEDIS measure (gold) -> governed metric view (semantic) -> ontology Page -> Genie / RAG / graph.

Each stage returns the patient's ACTUAL data at that hop + the semantic concept it binds to, so a visitor
can follow one record end to end (the P13 gate). Stages 1-6 are live SQL; Genie/RAG/graph are marked
status='wired_next' until those arms are plumbed into the app.
"""
from fastapi import APIRouter, HTTPException

from ..config import CATALOG, MEASUREMENT_YEAR, SCHEMA, SCHEMA_SEMANTIC, SCHEMA_TERM
from ..warehouse import run_sql

router = APIRouter()

C, S, SM, ST = CATALOG, SCHEMA, SCHEMA_SEMANTIC, SCHEMA_TERM


@router.get("/tracers")
def list_tracers():
    """Hero patients for the journey picker: GSD-eligible diabetics with a real ICD-10 diabetes dx, mixing
    care gaps (NOT_MET) and compliant (MET) so the throughline has both outcomes."""
    rows = run_sql(
        f"""
        WITH dx AS (
          SELECT patient_id, MIN(icd10_code) AS dx_code, MIN(description) AS dx_desc
          FROM {C}.{S}.bronze_pat_enc_dx
          WHERE icd10_code LIKE 'E11%' OR icd10_code LIKE 'E10%' OR icd10_code LIKE 'E13%'
          GROUP BY patient_id
        )
        SELECT g.patient_id, g.status, g.gap_reason, g.clinic_id, g.age, dx.dx_code, dx.dx_desc
        FROM {C}.{S}.gold_adherence_gsd g JOIN dx USING (patient_id)
        WHERE g.measurement_year = :my AND g.eligible_flag = true
        ORDER BY CASE WHEN g.status='NOT_MET' THEN 0 ELSE 1 END, g.patient_id
        LIMIT 12
        """,
        {"my": MEASUREMENT_YEAR},
    )
    return {"measurement_year": MEASUREMENT_YEAR, "tracers": rows}


@router.get("/patient/{patient_id}/journey")
def patient_journey(patient_id: str):
    my = MEASUREMENT_YEAR
    p = {"pid": patient_id, "my": my}

    bronze = run_sql(
        f"""SELECT icd10_code, snomed_code, description, onset_date, encounter_id
            FROM {C}.{S}.bronze_pat_enc_dx
            WHERE patient_id = :pid AND (icd10_code LIKE 'E1%')
            ORDER BY onset_date LIMIT 5""", p)
    if not bronze:
        raise HTTPException(404, f"No diabetes-coded encounter for patient {patient_id}")

    silver = run_sql(
        f"""SELECT icd10_code, snomed_code, description, onset_date
            FROM {C}.{S}.silver_condition
            WHERE patient_id = :pid AND icd10_code LIKE 'E1%' ORDER BY onset_date LIMIT 5""", p)

    # The subsumption path that puts this patient in the cohort: their coded dx as a descendant of the
    # diabetes value-set roots (E10/E11/E13) via the ICD-10 closure. THIS is the semantic work.
    closure = run_sql(
        f"""SELECT DISTINCT cl.descendant_code, cl.descendant_name, cl.ancestor_code, cl.ancestor_name, cl.depth
            FROM {C}.{ST}.icd10_closure cl
            WHERE cl.descendant_code IN (
                SELECT DISTINCT icd10_code FROM {C}.{S}.bronze_pat_enc_dx
                WHERE patient_id = :pid AND icd10_code LIKE 'E1%')
              AND cl.ancestor_code IN ('E10','E11','E13')
            ORDER BY cl.depth LIMIT 10""", p)

    in_cohort = run_sql(
        f"SELECT patient_id FROM {C}.{S}.silver_diabetes_cohort WHERE patient_id = :pid", p)

    gold = run_sql(
        f"""SELECT status, gap_reason, evidence_code, evidence_value, evidence_datetime,
                   a1c_lt8, a1c_gt9, clinic_id, panel_id, age
            FROM {C}.{S}.gold_adherence_gsd
            WHERE patient_id = :pid AND measurement_year = :my LIMIT 1""", p)
    gold0 = gold[0] if gold else {}
    clinic = gold0.get("clinic_id")

    # The governed metric view this patient rolls into — the clinic-level GSD rate they are one row of.
    metric = run_sql(
        f"""SELECT `Clinic` AS clinic, `Measurement Year` AS my,
                   MEASURE(`Eligible Patients`) AS eligible,
                   MEASURE(`Compliant Patients`) AS compliant,
                   MEASURE(`GSD Compliance Rate`) AS rate
            FROM {C}.{SM}.gsd_compliance_metrics
            WHERE `Clinic` = :clinic AND `Measurement Year` = :my
            GROUP BY `Clinic`, `Measurement Year` LIMIT 1""",
        {"clinic": clinic, "my": my}) if clinic else []

    def stage(key, title, concept, status, data, note=""):
        return {"key": key, "title": title, "semantic_concept": concept,
                "status": status, "data": data, "note": note}

    stages = [
        stage("bronze", "Bronze — raw EHR code", "Source ICD-10-CM / SNOMED as coded at the encounter",
              "live", bronze,
              "The diagnosis exactly as it arrived from Epic/Clarity — a flat code, no meaning attached yet."),
        stage("silver", "Silver — conformed condition", "Mapped & deduplicated clinical condition",
              "live", silver, "Bronze codes conformed into one clean condition record per patient."),
        stage("closure", "Terminology — ICD-10 subsumption", "is-a hierarchy: E11.x ⊑ E11 (diabetes value set)",
              "live", closure,
              "Why this patient is a diabetic: their specific code resolves to a diabetes root by subsumption "
              "over the ICD-10 closure — a flat code list would miss subcodes (tracer T3)."),
        stage("cohort", "Cohort — diabetes denominator", "HEDIS eligible population (GSD denominator)",
              "live", {"in_cohort": bool(in_cohort)},
              "Membership earned by the subsumption above, not a hand-maintained list."),
        stage("gold", "Gold — HEDIS GSD measure", "Deterministic measure status + care gap + evidence",
              "live", gold0,
              "The measure engine's verdict for this patient: MET or a NOT_MET care gap with its reason."),
        stage("metric", "Semantic — governed metric view", "care_protocol_semantic.gsd_compliance_metrics",
              "live", (metric[0] if metric else {}),
              f"The one governed GSD rate this patient rolls into (clinic {clinic}) — the number Genie cites."),
        stage("page", "Ontology — Discover Page", "GSD Page (highest-authority ontology snippet)",
              "page", {"page": "GSD — Glycemic Status Assessment for Patients With Diabetes"},
              "The human-modeled definition Genie One prioritizes and cites as an Ontology Reference."),
        stage("genie", "Genie One — natural language", "Ontology-grounded answer over the whole chain",
              "wired_next", {},
              "Ask 'is this patient compliant and why?' — Genie reasons over the metric view + Page above."),
        stage("rag", "A4 — Lakebase hybrid RAG", "Document evidence w/ doc-level RLS",
              "wired_next", {}, "Retrieve the care-protocol passage that defines the accepted A1c evidence."),
        stage("graph", "A5 — Ontobricks graph", "Explicit OWL/SNOMED subsumption graph",
              "wired_next", {}, "The same subsumption, as a navigable graph — the final semantic hop."),
    ]
    return {"patient_id": patient_id, "measurement_year": my, "stages": stages}
