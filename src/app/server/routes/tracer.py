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
    """Hero patients for the journey picker: GSD-eligible diabetics with a real ICD-10 diabetes dx.

    Deliberately STRATIFIED so the throughline lights up differently per patient instead of showing twelve
    copies of the same gap. We take one patient per (status x gap_reason x complication subtree) cell, so the
    picker spans MET and every NOT_MET reason (no A1c test / poor control / etc.) AND every diabetes
    complication branch (kidney E1x.2 / retinopathy E1x.3 / neuropathy E1x.4 / circulatory E1x.5 /
    uncomplicated) — each of which resolves through a different ICD-10 closure path at the subsumption hop.
    (The old query ordered NOT_MET-first by patient_id, which just returned the dominant 'no A1c test' gap.)"""
    rows = run_sql(
        f"""
        WITH dx AS (
          -- primary dx = lowest diabetes code already present by the end of the measurement year (onset <= MY end);
          -- the label is the description OF THAT code (min_by), not an independent MIN(description).
          SELECT patient_id, MIN(icd10_code) AS dx_code, min_by(description, icd10_code) AS dx_desc
          FROM {C}.{S}.bronze_pat_enc_dx
          WHERE (icd10_code LIKE 'E11%' OR icd10_code LIKE 'E10%' OR icd10_code LIKE 'E13%')
            AND onset_date <= DATE'{MEASUREMENT_YEAR}-12-31'
          GROUP BY patient_id
        ),
        elig AS (
          -- status / gap_reason are DERIVED from evidence (the rule now lives in the semantic layer, not gold).
          SELECT g.patient_id,
                 CASE WHEN g.evidence_datetime IS NOT NULL THEN 'MET' ELSE 'NOT_MET' END AS status,
                 CASE WHEN g.evidence_datetime IS NOT NULL THEN NULL ELSE 'No A1c test in measurement year' END AS gap_reason,
                 g.clinic_id, g.age, dx.dx_code, dx.dx_desc,
                 CASE
                   WHEN dx.dx_code LIKE 'E1_.2%' THEN 'kidney'
                   WHEN dx.dx_code LIKE 'E1_.3%' THEN 'retinopathy'
                   WHEN dx.dx_code LIKE 'E1_.4%' THEN 'neuropathy'
                   WHEN dx.dx_code LIKE 'E1_.5%' THEN 'circulatory'
                   ELSE 'uncomplicated'
                 END AS cx_bucket
          FROM {C}.{S}.gold_adherence_gsd g JOIN dx USING (patient_id)
          WHERE g.measurement_year = :my AND g.eligible_flag = true
        ),
        ranked AS (
          SELECT *,
            ROW_NUMBER() OVER (
              PARTITION BY status, COALESCE(gap_reason, '(met)'), cx_bucket
              ORDER BY patient_id
            ) AS rn
          FROM elig
        )
        SELECT patient_id, status, gap_reason, clinic_id, age, dx_code, dx_desc, cx_bucket
        FROM ranked
        WHERE rn = 1
        ORDER BY CASE WHEN status='NOT_MET' THEN 0 ELSE 1 END, cx_bucket, gap_reason
        LIMIT 12
        """,
        {"my": MEASUREMENT_YEAR},
    )
    return {"measurement_year": MEASUREMENT_YEAR, "tracers": rows}


@router.get("/patient/{patient_id}/journey")
def patient_journey(patient_id: str):
    my = MEASUREMENT_YEAR
    p = {"pid": patient_id, "my": my}

    prim = run_sql(
        f"""SELECT MIN(icd10_code) AS dx FROM {C}.{S}.bronze_pat_enc_dx WHERE patient_id = :pid
            AND (icd10_code LIKE 'E10%' OR icd10_code LIKE 'E11%' OR icd10_code LIKE 'E13%')
            AND onset_date <= DATE'{my}-12-31'""", {"pid": patient_id})
    p["prim"] = (prim[0]["dx"] if prim and prim[0]["dx"] else "")

    bronze = run_sql(
        f"""SELECT icd10_code, snomed_code, description, onset_date, encounter_id
            FROM {C}.{S}.bronze_pat_enc_dx
            WHERE patient_id = :pid AND (icd10_code LIKE 'E1%')
            ORDER BY (icd10_code = :prim) DESC, icd10_code, onset_date LIMIT 5""", p)
    if not bronze:
        raise HTTPException(404, f"No diabetes-coded encounter for patient {patient_id}")

    silver = run_sql(
        f"""SELECT icd10_code, snomed_code, description, onset_date
            FROM {C}.{S}.silver_condition
            WHERE patient_id = :pid AND icd10_code LIKE 'E1%'
            ORDER BY (icd10_code = :prim) DESC, icd10_code, onset_date LIMIT 5""", p)

    # The subsumption path that puts this patient in the cohort: their coded dx as a descendant of the
    # diabetes value-set roots (E10/E11/E13) via the ICD-10 closure. THIS is the semantic work.
    closure = run_sql(
        f"""SELECT DISTINCT cl.descendant_code, cl.descendant_name, cl.ancestor_code, cl.ancestor_name, cl.depth
            FROM {C}.{ST}.icd10_closure cl
            WHERE cl.descendant_code IN (
                SELECT DISTINCT icd10_code FROM {C}.{S}.bronze_pat_enc_dx
                WHERE patient_id = :pid AND icd10_code LIKE 'E1%')
              AND cl.ancestor_code IN ('E10','E11','E13')
            ORDER BY (cl.descendant_code = :prim) DESC, cl.descendant_code, cl.depth LIMIT 10""", p)

    raw_n = run_sql(f"SELECT count(*) AS n FROM {C}.{S}.raw_synthea_conditions WHERE PATIENT = :pid",
                    {"pid": patient_id})[0]["n"]

    in_cohort = run_sql(
        f"SELECT patient_id FROM {C}.{S}.silver_diabetes_cohort WHERE patient_id = :pid", p)

    # Gold is now EVIDENCE only; status / gap_reason / bands are derived here (the rule lives in the metric view).
    gold = run_sql(
        f"""SELECT CASE WHEN evidence_datetime IS NOT NULL THEN 'MET' ELSE 'NOT_MET' END AS status,
                   CASE WHEN evidence_datetime IS NOT NULL THEN NULL ELSE 'No A1c test in measurement year' END AS gap_reason,
                   evidence_code, evidence_value, evidence_datetime,
                   evidence_value < 8.0 AS a1c_lt8, evidence_value > 9.0 AS a1c_gt9, clinic_id, panel_id, age
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
        stage("protocol", "Source — care-protocol document", "CP-DM-2025.1 · §2 Quality Measure Specifications",
              "doc",
              {"document": "CP-DM-2025.1 — Comprehensive Diabetes Management (v2025.1)",
               "section": "2. Quality Measure Specifications — GSD",
               "excerpt": "GSD — Glycemic Status Assessment. Eligible ages 18–75. Numerator (compliant when): "
                          "≥1 HbA1c test in the measurement year. Thresholds: good control < 8.0%; poor control "
                          "> 9.0%; general target < 7.0%.",
               "eligible_population": "ICD-10-CM E10 / E11 / E13 and ALL descendant codes — membership is by the "
                                      "diagnosis hierarchy, not an enumerated code list (§1 Scope)."},
              "The source of meaning: the actual care-protocol document (the PDF/HTML in a UC Volume, also the A4 "
              "RAG corpus). This excerpt DEFINES who is eligible and what 'compliant' means; every datum downstream "
              "is an instance of these definitions."),
        stage("raw", "Source — raw EHR extract", "Synthea CSV: SNOMED-coded conditions + LOINC observations",
              "live", {"raw_rows": raw_n},
              "The extract as generated, before epicize maps SNOMED to ICD-10 and reshapes it into Clarity tables."),
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
        stage("gold", "Gold — per-patient evidence", "One evidence row per eligible patient (no verdict)",
              "live", {k: gold0.get(k) for k in ("evidence_datetime", "evidence_code", "evidence_value",
                                                  "clinic_id", "panel_id", "age")},
              "Gold assembles the facts (latest A1c in the measurement year). The MET/NOT_MET rule is applied "
              "downstream, in the certified metric view."),
        stage("metric", "Semantic — governed metric view", "care_protocol_semantic.gsd_compliance_metrics",
              "live", {**(metric[0] if metric else {}), "patient_status": gold0.get("status")},
              f"The one governed GSD rate this patient rolls into (clinic {clinic}) — the number Genie cites."),
        stage("page", "Ontology — Genie Ontology Page", "GSD Page (highest-authority ontology snippet)",
              "page", {"page": "GSD — Glycemic Status Assessment for Patients With Diabetes"},
              "The human-modeled definition Genie One prioritizes and cites as an Ontology Reference."),
        stage("rag", "Retrieval — RAG index", "Protocol passages in Lakebase (hybrid search, doc-level RLS)",
              "page", {"corpus": "rag.chunks"},
              "Unstructured context: the protocol text, retrieved by meaning + keywords."),
        stage("closure_ret", "Retrieval — closure + edge tables", "icd10/rxnorm closures + protocol_edges",
              "page", {"tables": 5},
              "Structured context: pre-materialized hierarchies and typed edge tables, queried with fixed-shape SQL."),
        stage("ontobricks", "Ontology — Ontobricks graph", "Cross-vocabulary OWL mapping over the governed tables (clinicaldomain)",
              "page",
              {"graph": "clinicaldomain_v2 (live triplestore)"},
              "The explicit OWL graph: typed, cross-vocabulary edges (recommendedFor / contraindicatedWith / "
              "monitoredBy / subClassOf*) mapped from the governed tables via R2RML. Eli-owned Ontobricks deployment "
              "(ADR-0005); surfaced here as the modeled mapping, a live traversal is the next step."),
    ]

    # --- The modeled answer: the question a visitor asks at the end of the flow, answered from THIS patient's
    # real data. Each claim carries (a) the spine path to highlight back to source, and (b) the retrieval
    # modes that can produce it — so clicking a claim shows both "where it came from" and "which tool gets it".
    status = gold0.get("status") or "UNKNOWN"
    met = status == "MET"
    gap = gold0.get("gap_reason")
    ev_dt = gold0.get("evidence_datetime")
    dx_code = bronze[0].get("icd10_code") if bronze else None

    subs = next((r for r in closure if r.get("ancestor_code") in ("E10", "E11", "E13")), None)
    subs_chip = f'{subs.get("descendant_code")} ⊑ {subs.get("ancestor_code")}' if subs else None

    rate_chip = None
    if metric:
        m0 = metric[0]
        try:
            rf = float(m0.get("rate"))
            rate_str = f"{rf * 100:.0f}%" if rf <= 1 else f"{rf:.0f}%"
        except (TypeError, ValueError):
            rate_str = str(m0.get("rate"))
        rate_chip = f'{m0.get("clinic")} GSD rate {rate_str}'

    short = patient_id[:8]
    claims = [
        {"id": "verdict", "before": f"Patient {short} is ",
         "chip": ("meeting GSD (MET)" if met else "NOT_MET for GSD"), "kind": "verdict",
         "stage_path": ["metric", "gold", "cohort", "closure", "silver", "bronze", "protocol"],
         "modes": ["metric_view", "genie_ontology"]},
        {"id": "evidence", "before": " because ",
         "chip": ("the most recent A1c is in control" if met else (gap or "the care-gap evidence rule is unmet")),
         "kind": "evidence", "stage_path": ["gold", "protocol"], "modes": ["rag", "genie_ontology"]},
    ]
    if ev_dt:
        claims.append({"id": "evidence_dt", "before": " (A1c recorded ", "chip": str(ev_dt)[:10], "suffix": ")",
                       "kind": "evidence", "stage_path": ["gold"], "modes": ["metric_view"]})
    if dx_code:
        claims.append({"id": "code", "before": ". They enter the measure because diagnosis ", "chip": dx_code,
                       "kind": "code", "stage_path": ["bronze"], "modes": []})
    if subs_chip:
        claims.append({"id": "subsumption", "before": " is a form of diabetes — ", "chip": subs_chip,
                       "kind": "subsumption", "stage_path": ["closure", "silver", "bronze"],
                       "modes": ["closure", "graph", "genie_ontology"]})
    if rate_chip:
        claims.append({"id": "rate", "before": ", so they roll into ", "chip": rate_chip, "kind": "rate",
                       "stage_path": ["metric", "gold"], "modes": ["metric_view", "genie_ontology"]})
    claims.append({"id": "definition", "before": ". All of this is defined by the ", "chip": "GSD care-protocol spec",
                   "suffix": ".", "kind": "definition", "stage_path": ["protocol"], "modes": ["rag", "genie"]})

    answer = {"question": f"Is patient {short} compliant with GSD for MY {my}, and why?", "claims": claims}
    return {"patient_id": patient_id, "measurement_year": my, "stages": stages, "answer": answer}
