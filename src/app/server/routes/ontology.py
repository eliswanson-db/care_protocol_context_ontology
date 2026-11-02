"""Ontology Explorer — the modeled clinical graph (license-clean: ICD-10 + LOINC + RxNorm + protocol).

`care_protocol_terminology.protocol_edges` is a small typed triple store (subject-predicate-object) that links
measures <-> drug classes <-> LOINC Part concepts <-> conditions <-> thresholds — the cross-domain edges that a
closure table alone can't express (BENCHMARK_CHARTER.md class 8). We serve the whole graph (it's tiny) and the
app renders an ego-network per concept. is-a within a vocabulary (ICD/RxNorm) and LOINC multiaxial identity are
resolved by the closures/Part table; a formal OWL graph with inference is the A5 Ontobricks hop (future).
"""
from fastapi import APIRouter

from ..config import CATALOG, SCHEMA_TERM
from ..warehouse import run_sql

router = APIRouter()
C, ST = CATALOG, SCHEMA_TERM

_MEASURES = {"GSD", "KED", "BPD", "SPD", "EED", "MAD", "SSD"}
_CONDITIONS = {"ALBUMINURIA", "COMORBID_CKD", "COMORBID_HF", "GLYCEMIC", "BP"}


def _kind(x: str) -> str:
    if x in _MEASURES:
        return "measure"
    if x.startswith("DRUGCLASS-"):
        return "drug_class"
    if x.startswith("LP-"):
        return "loinc_part"
    if x.startswith("CONTRA_"):
        return "contraindication"
    if x in _CONDITIONS:
        return "condition"
    return "threshold"


@router.get("/ontology/graph")
def ontology_graph():
    rows = run_sql(
        f"SELECT subject, predicate, object, value, source FROM {C}.{ST}.protocol_edges ORDER BY subject, predicate")
    nodes: dict[str, dict] = {}
    deg: dict[str, int] = {}
    for r in rows:
        for x in (r["subject"], r["object"]):
            nodes.setdefault(x, {"id": x, "label": x, "kind": _kind(x)})
            deg[x] = deg.get(x, 0) + 1
    for n in nodes.values():
        n["degree"] = deg.get(n["id"], 0)
    return {
        "nodes": sorted(nodes.values(), key=lambda n: (n["kind"], n["id"])),
        "edges": rows,
        "predicates": sorted({r["predicate"] for r in rows}),
    }
