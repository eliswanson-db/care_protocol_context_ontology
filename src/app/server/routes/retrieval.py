"""The consistent five-lens retrieval row — the SAME hero question answered five ways, one uniform shape.

Goal 2/4 of the demo (see docs/CONSISTENT_RETRIEVAL_PLAN.md): make the five retrieval approaches comparable
apples-to-apples. This endpoint returns the THREE deterministic lenses computed server-side from the governed
semantic layer:

  - metric_view  — the governed clinic rate this patient rolls into (build-time; one certified number).
  - closure      — the ICD-10 subsumption rows that earn cohort membership (query-time join; any depth).
  - graph        — the property path a graph traverses for this patient: the is-a edge the reasoner derives
                   (== closure) PLUS the cross-vocabulary care-protocol edges for the measures the patient is
                   eligible for. Modeled from the governed edge tables (protocol_edges + closures); the same
                   ABox Ontobricks imports from src/ontology. Labeled honestly as modeled, not a live SPARQL hit.

The two LIVE lenses (genie_ontology, rag) are slow LLM/DB calls with their own endpoints (/genie, /rag); they
are returned here as deferred descriptors so the UI can render all five cards in one consistent row and fill
the live two on demand. Every lens shares {id,label,resolves_at,question,answer_rows,provenance,good_at,
blind_to,latency_s} so the row reads as one exhibit, not five.
"""
import time

from fastapi import APIRouter, HTTPException

from ..config import CATALOG, MEASUREMENT_YEAR, SCHEMA, SCHEMA_SEMANTIC, SCHEMA_TERM
from ..warehouse import run_sql

router = APIRouter()

C, S, SM, ST = CATALOG, SCHEMA, SCHEMA_SEMANTIC, SCHEMA_TERM

# Known measures (server-side whitelist; used to build safe IN-lists for the graph lens — never request input).
_MEASURES = {
    "GSD": "gold_adherence_gsd", "SPD": "gold_adherence_spd", "KED": "gold_adherence_ked",
    "BPD": "gold_adherence_bpd", "EED": "gold_adherence_eed",
}


def _eligible_measures(pid: str, my: int) -> list[str]:
    union = " UNION ALL ".join(
        f"SELECT '{m}' AS m FROM {C}.{S}.{t} WHERE patient_id = :pid AND measurement_year = :my "
        f"AND eligible_flag = true"
        for m, t in _MEASURES.items()
    )
    rows = run_sql(union, {"pid": pid, "my": my})
    return [r["m"] for r in rows]


def _metric_view_lens(pid: str, my: int) -> dict:
    t0 = time.time()
    g = run_sql(
        f"SELECT clinic_id, "
        f"CASE WHEN evidence_datetime IS NOT NULL THEN 'MET' ELSE 'NOT_MET' END AS status, "
        f"CASE WHEN evidence_datetime IS NOT NULL THEN NULL ELSE 'No A1c test in measurement year' END AS gap_reason "
        f"FROM {C}.{S}.gold_adherence_gsd "
        f"WHERE patient_id = :pid AND measurement_year = :my LIMIT 1", {"pid": pid, "my": my})
    clinic = g[0]["clinic_id"] if g else None
    rows = []
    if clinic:
        rows = run_sql(
            f"""SELECT `Clinic` AS clinic, `Measurement Year` AS measurement_year,
                       MEASURE(`Eligible Patients`) AS eligible,
                       MEASURE(`Compliant Patients`) AS compliant,
                       MEASURE(`GSD Compliance Rate`) AS rate
                FROM {C}.{SM}.gsd_compliance_metrics
                WHERE `Clinic` = :clinic AND `Measurement Year` = :my
                GROUP BY `Clinic`, `Measurement Year` LIMIT 1""",
            {"clinic": clinic, "my": my})
    return {
        "id": "metric_view", "label": "Metric View",
        "resolves_at": "build-time (baked into the governed metric view)",
        "question": "the governed GSD rate this patient's verdict rolls into",
        "answer_rows": rows,
        "provenance": [{"kind": "metric_view", "detail": f"{SM}.gsd_compliance_metrics"}],
        "good_at": "One certified number, shared by BI + Genie; exact & auditable.",
        "blind_to": "Why THIS patient — it's a pre-modeled aggregate, not a record-level or cross-vocab answer.",
        "latency_s": round(time.time() - t0, 2),
    }


def _closure_lens(pid: str, my: int) -> dict:
    t0 = time.time()
    rows = run_sql(
        f"""SELECT DISTINCT cl.descendant_code, cl.descendant_name, cl.ancestor_code, cl.ancestor_name, cl.depth
            FROM {C}.{ST}.icd10_closure cl
            WHERE cl.descendant_code IN (
                SELECT DISTINCT icd10_code FROM {C}.{S}.bronze_pat_enc_dx
                WHERE patient_id = :pid AND icd10_code LIKE 'E1%')
              AND cl.ancestor_code IN ('E10','E11','E13')
            ORDER BY cl.depth DESC, cl.descendant_code LIMIT 10""", {"pid": pid, "my": my})
    return {
        "id": "closure", "label": "Closure table",
        "resolves_at": "query-time (one equality join on the closure)",
        "question": "why the patient is in the measure at all (diagnosis subsumption)",
        "answer_rows": rows,
        "provenance": [{"kind": "table", "detail": f"{ST}.icd10_closure"}],
        "good_at": "Correct cohort membership at ANY depth (E11.21 ⊑ E11) — a flat code list misses subcodes.",
        "blind_to": "No narrative/provenance; the hierarchy must be pre-built and rebuilt on code-set change.",
        "latency_s": round(time.time() - t0, 2),
    }


def _graph_lens(pid: str, my: int, measures: list[str]) -> dict:
    t0 = time.time()
    # (a) the is-a edge the reasoner derives — same subsumption the closure materializes (graph == closure here).
    subs = run_sql(
        f"""SELECT cl.descendant_code AS subject, 'rdfs:subClassOf*' AS predicate, cl.ancestor_code AS object,
                   CAST(NULL AS STRING) AS value, 'icd10_closure (reasoner-derivable)' AS source
            FROM {C}.{ST}.icd10_closure cl
            WHERE cl.descendant_code IN (
                SELECT DISTINCT icd10_code FROM {C}.{S}.bronze_pat_enc_dx
                WHERE patient_id = :pid AND icd10_code LIKE 'E1%')
              AND cl.ancestor_code IN ('E10','E11','E13') AND cl.depth > 0
            ORDER BY cl.depth DESC LIMIT 3""", {"pid": pid, "my": my})
    # (b) the cross-vocabulary care-protocol edges for THIS patient's eligible measures — the graph's lift.
    edges = []
    valid = [m for m in measures if m in _MEASURES]
    if valid:
        in_list = ", ".join(f"'{m}'" for m in valid)  # from server-side whitelist only
        edges = run_sql(
            f"""SELECT subject, predicate, object, value, source
                FROM {C}.{ST}.protocol_edges
                WHERE subject IN ({in_list}) OR object IN ({in_list})
                ORDER BY predicate, subject LIMIT 15""")
    return {
        "id": "graph", "label": "Ontobricks graph",
        "resolves_at": "graph traversal (modeled; Ontobricks ABox = src/ontology)",
        "question": "the clinical rationale linking the patient's codes, drugs and measures",
        "answer_rows": subs + edges,
        "provenance": [
            {"kind": "table", "detail": f"{ST}.protocol_edges"},
            {"kind": "table", "detail": f"{ST}.icd10_closure"},
            {"kind": "ontology", "detail": "src/ontology/care_protocol.owl.ttl + .r2rml.ttl"},
        ],
        "good_at": "Typed, multi-hop, cross-vocabulary paths & defined-classes (the one thing SQL can't shape).",
        "blind_to": "Overkill for a single is-a rollup; needs modeled edges + a live graph runtime to query.",
        "latency_s": round(time.time() - t0, 2),
    }


def _live_descriptors(pid: str) -> list[dict]:
    """The two slow LLM/DB lenses — rendered in the same row, filled on demand from their own endpoints."""
    return [
        {
            "id": "genie_ontology", "label": "Genie One + Ontology", "deferred": True,
            "endpoint": f"/api/patient/{pid}/genie",
            "resolves_at": "LLM at query-time (natural language → governed SQL + citations)",
            "question": "the whole question, in English, with citations",
            "good_at": "Anyone asks in English; grounds in Pages/metric views and cites them.",
            "blind_to": "Non-deterministic; quality tracks snippet/Page density; may write a wrong join.",
        },
        {
            "id": "rag", "label": "A4 Lakebase RAG", "deferred": True,
            "endpoint": f"/api/patient/{pid}/rag",
            "resolves_at": "retrieval at query-time (hybrid BM25 + vector; doc-level RLS)",
            "question": "what the rule is, and where the protocol states it",
            "good_at": "Returns the exact narrative passage + document/section provenance; row-secured.",
            "blind_to": "Prose, not computation; can't count a cohort or roll up a hierarchy.",
        },
        {
            "id": "graph", "label": "Ontobricks graph", "deferred": True,
            "endpoint": f"/api/patient/{pid}/ontobricks",
            "resolves_at": "live graph traversal (latest clinicaldomain triplestore)",
            "question": "the clinical rationale linking the patient's codes, drugs and measures",
            "good_at": "Typed, multi-hop, cross-vocabulary paths a closure join can't express.",
            "blind_to": "Overkill for a single is-a rollup; a full scan over ~55M triples.",
        },
    ]


@router.get("/patient/{patient_id}/retrieval")
def retrieval(patient_id: str):
    my = MEASUREMENT_YEAR
    # Guard: the patient must exist in the diabetes spine (same precondition as the journey endpoint).
    exists = run_sql(
        f"SELECT 1 FROM {C}.{S}.bronze_pat_enc_dx WHERE patient_id = :pid AND icd10_code LIKE 'E1%' LIMIT 1",
        {"pid": patient_id})
    if not exists:
        raise HTTPException(404, f"No diabetes-coded encounter for patient {patient_id}")

    lenses = [
        _metric_view_lens(patient_id, my),
        _closure_lens(patient_id, my),
    ]
    return {
        "patient_id": patient_id,
        "measurement_year": my,
        "eligible_measures": _eligible_measures(patient_id, my),
        "deterministic_lenses": lenses,
        "live_lenses": _live_descriptors(patient_id),
    }
