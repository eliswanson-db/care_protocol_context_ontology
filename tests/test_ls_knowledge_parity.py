"""ADR-0025 knowledge parity + governed documents (no workspace).

- The Ontobricks mapping (hand-maintained OWL + R2RML) reads the real tables, maps every OWL class and every KB
  predicate, and keeps Ontobricks' endpoint-by-column-name rule.
- Documents agree with the executable rules; every review state is present; candidates never execute.

    python3 -I tests/test_ls_knowledge_parity.py   (or pytest)
"""

from __future__ import annotations

import collections
import copy
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinical_study import documents as docs_mod  # noqa: E402
from clinical_study import engine  # noqa: E402
from clinical_study.standardize import load_named, load_registry  # noqa: E402

CONCEPTS, EDGES = docs_mod.load_kb()
REG = load_registry()
DOCS = docs_mod.load_corpus()
ASSERTIONS = docs_mod.apply_reviews(
    docs_mod.extract(DOCS), ROOT / "src/clinical_study/rules/assertion_reviews.yaml"
)


OWL = ROOT / "src/ontology/life_sciences/clinical_study.owl.ttl"
R2RML = ROOT / "src/ontology/life_sciences/clinical_study.r2rml.ttl"
TPL = re.compile(r"/ontology/(\w+)/\{(\w+)\}$")


def _maps() -> list[dict]:
    """Every TriplesMap in the hand-maintained R2RML: subject class + id column, objects, logical-table SQL."""
    import rdflib
    from rdflib.namespace import RDF

    rr = rdflib.Namespace("http://www.w3.org/ns/r2rml#")
    g = rdflib.Graph().parse(R2RML)
    out = []
    for tm in g.subjects(RDF.type, rr.TriplesMap):
        sm, lt = g.value(tm, rr.subjectMap), g.value(tm, rr.logicalTable)
        cls, col = TPL.search(str(g.value(sm, rr.template))).groups()
        objs = []
        for pom in g.objects(tm, rr.predicateObjectMap):
            t = g.value(g.value(pom, rr.objectMap), rr.template)
            if t is not None:
                objs.append(TPL.search(str(t)).groups())
        out.append({"cls": cls, "col": col, "entity": g.value(sm, rr["class"]) is not None, "objs": objs,
                    "table": g.value(lt, rr.tableName), "sql": str(g.value(lt, rr.sqlQuery) or "")})
    return out


def test_mapping_reads_the_real_tables_only():
    """The HEDIS pattern: inline SQL over clinical_study / clinical_study_standards; no staging views, no metric
    views (they abort the Ontobricks scan)."""
    for m in _maps():
        assert m["table"] is None and m["sql"], m["cls"]
        schemas = set(re.findall(r"eli_test_classic_catalog\.(\w+)\.", m["sql"]))
        assert schemas and schemas <= {"clinical_study", "clinical_study_standards"}, (m["cls"], schemas)


def test_every_owl_class_has_an_entity_map():
    import rdflib
    from rdflib.namespace import OWL as O
    from rdflib.namespace import RDF

    classes = {str(c).rsplit("#", 1)[-1] for c in rdflib.Graph().parse(OWL).subjects(RDF.type, O.Class)
               if isinstance(c, rdflib.URIRef)}
    mapped = {m["cls"] for m in _maps() if m["entity"]}
    assert classes == mapped, {"unmapped": classes - mapped, "not_in_owl": mapped - classes}


def test_relationship_endpoints_resolve_by_column_name():
    """Ontobricks binds a relationship endpoint to the entity whose id column has the same NAME (HEDIS rev 2; the
    first ClinicalStudyLab import failed all 72 relationships on generic source_id/target_id)."""
    ms = _maps()
    ids = {m["cls"]: m["col"] for m in ms if m["entity"]}
    assert len(set(ids.values())) == len(ids), "two entities share an id column"
    for m in ms:
        if m["entity"]:
            continue
        assert m["col"] == ids[m["cls"]], (m["cls"], m["col"])
        for o, oc in m["objs"]:
            want = ids[o] if o != m["cls"] else ids[o].removesuffix("_id") + "_target_id"
            assert oc == want, (m["cls"], o, oc)


def test_every_kb_fact_reaches_the_graph():
    """Every knowledge-base predicate (MONDO, MED-RT, MeSH, CDISC CT, COSMoS edges) has a relationship map."""
    sql = " ".join(m["sql"] for m in _maps())
    used = {e["predicate"] if isinstance(e, dict) else e.predicate for e in EDGES}
    missing = {p for p in used if f"e.predicate = '{p}'" not in sql}
    assert not missing, missing


def test_registry_rules_and_classes_reach_the_graph():
    text = R2RML.read_text()
    for prop in ("hasRoot", "excludesRoot", "hasCriterion", "usesClass", "derivedUnder", "supportedBy"):
        assert f"/ontology/{prop}>" in text, prop


def test_every_rule_cites_a_real_section_and_every_version_a_real_document():
    sections = {(s.document_id, s.section_number) for d in DOCS for s in d.sections}
    doc_ids = {d.meta["document_id"] for d in DOCS}
    for ep in REG["endpoints"].values():
        for r in ep["rule_versions"].values():
            assert (r["source_section"]["document"], r["source_section"]["section"]) in sections, r[
                "source_section"
            ]
    for r in REG["eligibility"].values():
        assert (r["source_section"]["document"], r["source_section"]["section"]) in sections, r[
            "source_section"
        ]
    for st in REG["studies"].values():
        for v in st["study_versions"]:
            assert set(v["documents"]) <= doc_ids, v["documents"]


def test_documents_agree_with_approved_rules():
    approved = [a for a in ASSERTIONS if a.review_state == "approved"]
    for a in approved:
        assert docs_mod.registry_value(REG, a.rule_ref, a.assertion_type) == a.value, (
            a.assertion_id,
            a.value,
        )
    need = {
        "FOLLOWUP_WINDOW_HALF_WIDTH",
        "TARGET_OFFSET_DAYS",
        "BASELINE_WINDOW",
        "BASELINE_METHOD",
        "TIE_BREAKER",
    }
    for ep_id, ep in REG["endpoints"].items():
        for rv, r in ep["rule_versions"].items():
            src = r["source_section"]
            got = {
                a.assertion_type
                for a in approved
                if a.rule_ref == f"{ep_id}.{rv}"
                and a.document_id == src["document"]
                and a.section_number == src["section"]
            }
            assert got == need, (ep_id, rv, need - got)


def test_every_extracted_assertion_is_reviewed():
    """Every rule statement extracted from an approved document carries a review decision (approved / superseded /
    rejected). Nothing is left a candidate, and no executable window exists without an approved assertion."""
    states = collections.Counter(a.review_state for a in ASSERTIONS)
    assert set(states) <= {"approved", "superseded", "rejected"}, states
    assert states["approved"] and states["superseded"] and states["rejected"], states
    windows = {
        r["followup"]["window_half_width_days"]
        for ep in REG["endpoints"].values()
        for r in ep["rule_versions"].values()
    }
    approved = {int(a.value) for a in ASSERTIONS
                if a.review_state == "approved" and a.assertion_type == "FOLLOWUP_WINDOW_HALF_WIDTH"}
    assert windows <= approved, (windows, approved)


def test_candidate_assertion_cannot_change_a_calculation():
    """An unreviewed rule never executes: FX-19 (+19 days) would qualify only under a hypothetical, unreviewed
    ±21-day window. The production result is unchanged, and a rule in review_state candidate refuses to run."""
    n = next(x for x in load_named() if x["participant"]["usubjid"] == "CSL-A-FX-19")
    ep = copy.deepcopy(REG["endpoints"]["EP-A-WT24"])
    res = engine.derive(
        n["participant"],
        n["observations"],
        n["exposures"],
        endpoint_id="EP-A-WT24",
        endpoint=ep,
        rule_version="R2",
        terminology_version="t",
    )
    assert res.result_status == engine.NO_QUALIFYING_FOLLOWUP
    ep["rule_versions"]["R3-CANDIDATE"] = {
        **copy.deepcopy(ep["rule_versions"]["R2"]),
        "review_state": "candidate",
    }
    ep["rule_versions"]["R3-CANDIDATE"]["followup"]["window_half_width_days"] = 21
    try:
        engine.derive(
            n["participant"],
            n["observations"],
            n["exposures"],
            endpoint_id="EP-A-WT24",
            endpoint=ep,
            rule_version="R3-CANDIDATE",
            terminology_version="t",
        )
        raise AssertionError("candidate rule executed")
    except ValueError:
        pass


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                fails += 1
                print(f"FAIL {name}: {e}")
    sys.exit(1 if fails else 0)
