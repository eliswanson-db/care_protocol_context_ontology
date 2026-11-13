"""ADR-0025 knowledge parity + governed documents (no workspace).

- Every KB fact reaches the graph (a relationship view) AND the RAG reference corpus (an entry stating it).
- Generated graph artifacts (TBox, R2RML, views, checklist) are up to date with graph_spec.py.
- Documents agree with the executable rules; every review state is present; candidates never execute.

    python3 -I tests/test_ls_knowledge_parity.py   (or pytest)
"""

from __future__ import annotations

import collections
import copy
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinical_study import documents as docs_mod  # noqa: E402
from clinical_study import engine, graph_spec  # noqa: E402
from clinical_study.standardize import load_named, load_registry  # noqa: E402

CONCEPTS, EDGES = docs_mod.load_kb()
REG = load_registry()
DOCS = docs_mod.load_corpus()
ASSERTIONS = docs_mod.apply_reviews(
    docs_mod.extract(DOCS), ROOT / "src/clinical_study/rules/assertion_reviews.yaml"
)


def _gen():
    spec = importlib.util.spec_from_file_location("ls_graph_build", ROOT / "scripts/ls_graph_build.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_every_kb_fact_reaches_the_graph():
    groups = graph_spec.kb_rel_groups(CONCEPTS, EDGES)
    assert None not in {c for k in groups for c in k[1:]}, "a KB concept has no graph class"
    assert set(groups) == set(graph_spec.KB_RELS), {
        "missing_in_spec": set(groups) - set(graph_spec.KB_RELS),
        "unused_in_spec": set(graph_spec.KB_RELS) - set(groups),
    }


def test_every_kb_fact_reaches_the_rag_corpus_exactly_once():
    entries = docs_mod.reference_entries(CONCEPTS, EDGES)
    seen = collections.Counter(i for e in entries for i in e["edge_ids"])
    ids = {e["edge_id"] for e in EDGES}
    assert set(seen) == ids, len(ids - set(seen))
    assert max(seen.values()) == 1
    assert len(entries) == len(CONCEPTS)
    for e in entries:  # one forward sentence per stated edge (no derived or transitive statements)
        assert e["text"].count("\n") + 1 >= len(e["edge_ids"])


def test_registry_rules_and_classes_reach_rag_and_graph():
    entries = docs_mod.registry_entries(REG, CONCEPTS)
    kinds = collections.Counter(e["entry_id"].split("::")[1] for e in entries)
    n_rules = sum(len(ep["rule_versions"]) for ep in REG["endpoints"].values())
    assert kinds == {"class": len(REG["concept_classes"]), "rule": n_rules, "elig": len(REG["eligibility"])}
    graph_rel_props = {r.prop for r in graph_spec.DATA_RELS}
    assert {
        "hasRoot",
        "excludesRoot",
        "hasCriterion",
        "usesClass",
        "derivedUnder",
        "supportedBy",
    } <= graph_rel_props


def test_generated_graph_artifacts_are_current():
    g = _gen()
    out = ROOT / "src/ontology/life_sciences"
    assert (out / "graph_views.sql").read_text() == g.views_sql(), "rerun scripts/ls_graph_build.py"
    assert (out / "clinical_study.owl.ttl").read_text() == g.tbox(), "rerun scripts/ls_graph_build.py"
    assert (out / "clinical_study.r2rml.ttl").read_text() == g.r2rml("eli_test_classic_catalog")
    assert (ROOT / "docs/life_sciences/ONTOBRICKS_IMPORT.md").read_text() == g.checklist(
        "eli_test_classic_catalog"
    )


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


def test_all_review_states_present_and_the_draft_stays_a_candidate():
    states = collections.Counter(a.review_state for a in ASSERTIONS)
    assert set(states) == {"approved", "superseded", "rejected", "candidate"}, states
    cand = [a for a in ASSERTIONS if a.review_state == "candidate"]
    assert [(a.document_id, a.assertion_type, a.value) for a in cand] == [
        ("CSL-A-AMD3-DRAFT", "FOLLOWUP_WINDOW_HALF_WIDTH", "21")
    ]
    windows = {
        r["followup"]["window_half_width_days"]
        for ep in REG["endpoints"].values()
        for r in ep["rule_versions"].values()
    }
    assert 21 not in windows  # the candidate is not in the executable registry


def test_candidate_assertion_cannot_change_a_calculation():
    """FX-19 (+19 days) would qualify only under the draft ±21 window. The production result is unchanged; a
    rule built from the candidate refuses to execute."""
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
