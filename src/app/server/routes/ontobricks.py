"""A5 Ontobricks — LIVE graph traversal against the published OWL triplestore (Eli-owned, ADR-0005).

Queries the asserted-triple table `{catalog}.{schema}.{table}_graph` (subject/predicate/object) directly —
this is the real clinical-domain graph (~55M triples), NOT a model of the edge tables. Two reads:

  * /patient/{id}/ontobricks — the patient's own edges (hasDiagnosis / eligibleFor / prescribed / hasCareGap)
    PLUS the cross-vocabulary care-protocol knowledge edges (recommendedFor / inDrugClass / contraindicatedWith
    / monitoredBy / hasThreshold / contraindicatedWhen) that a closure join can't express — the graph's lift.
  * /ontobricks/care_edges — just those knowledge edges (patient-agnostic), for the Arena.

IRIs are shortened for display (the namespace prefix is stripped). Latency is real (a scan over the triplestore),
so the UI calls these lazily behind a button.
"""
import time

from fastapi import APIRouter, HTTPException

from ..config import ONTOBRICKS_CATALOG, ONTOBRICKS_NS, ONTOBRICKS_SCHEMA, get_ontobricks_table
from ..warehouse import run_sql

router = APIRouter()

NS = ONTOBRICKS_NS


def _graph() -> tuple[str, str]:
    t = get_ontobricks_table()
    return t, f"{ONTOBRICKS_CATALOG}.{ONTOBRICKS_SCHEMA}.{t}_graph"

_PATIENT_PREDS = ["hasDiagnosis", "eligibleFor", "prescribed", "hasCareGap"]
# The cross-vocabulary GUIDELINE edges — the graph's lift over a closure join (not ABox plumbing like hasIngredient).
_CARE_PREDS = ["recommendedFor", "inDrugClass", "contraindicatedWith", "monitoredBy",
               "hasThreshold", "contraindicatedWhen"]


def _iri_list(locals_: list[str]) -> str:
    return ", ".join(f"'{NS}{p}'" for p in locals_)  # server-side constants only, never request input


def _short(iri: str | None) -> str:
    """Strip the ontology namespace + common prefixes to a readable local name."""
    if not iri:
        return ""
    s = iri
    if s.startswith(NS):
        s = s[len(NS):]
    else:
        s = s.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
    # shorten a patient UUID for display
    if s.startswith("Patient/") and len(s) > 16:
        s = "Patient/" + s[len("Patient/"):][:8]
    return s


def _triples(rows: list[dict]) -> list[dict]:
    return [{"subject": _short(r.get("subject")), "predicate": _short(r.get("predicate")),
             "object": _short(r.get("object"))} for r in rows]


@router.get("/patient/{patient_id}/ontobricks")
def patient_graph(patient_id: str):
    subj = f"{NS}Patient/{patient_id}"
    ONTOBRICKS_TABLE, GRAPH = _graph()
    t0 = time.time()
    try:
        rows = run_sql(
            f"""SELECT subject, predicate, object FROM {GRAPH}
                WHERE (subject = :s AND predicate IN ({_iri_list(_PATIENT_PREDS)}))
                   OR (predicate IN ({_iri_list(_CARE_PREDS)}))
                ORDER BY predicate, subject
                LIMIT 80""",
            {"s": subj})
    except Exception as e:  # noqa: BLE001 — surface the real failure to the UI
        raise HTTPException(502, f"Ontobricks query failed: {type(e).__name__}: {str(e)[:260]}")
    patient_edges = [r for r in rows if r.get("subject") == subj]
    care_edges = [r for r in rows if r.get("subject") != subj]
    return {
        "patient_id": patient_id,
        "source": f"{ONTOBRICKS_TABLE}_graph (live Ontobricks triplestore)",
        "table": GRAPH,
        "patient_triples": _triples(patient_edges),
        "care_triples": _triples(care_edges),
        "latency_s": round(time.time() - t0, 1),
    }


@router.get("/ontobricks/care_edges")
def care_edges():
    ONTOBRICKS_TABLE, GRAPH = _graph()
    t0 = time.time()
    try:
        rows = run_sql(
            f"""SELECT subject, predicate, object FROM {GRAPH}
                WHERE predicate IN ({_iri_list(_CARE_PREDS)})
                ORDER BY predicate, subject LIMIT 60""")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Ontobricks query failed: {type(e).__name__}: {str(e)[:260]}")
    return {
        "source": f"{ONTOBRICKS_TABLE}_graph (live Ontobricks triplestore)",
        "table": GRAPH,
        "triples": _triples(rows),
        "latency_s": round(time.time() - t0, 1),
    }
