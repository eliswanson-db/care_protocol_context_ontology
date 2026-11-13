"""Driver-side KB closures: contract + agreement with the eligibility module's own is_a walk. No workspace."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinical_study.closure import closure_rows, validate  # noqa: E402
from clinical_study.eligibility import default_ontology  # noqa: E402

STD = ROOT / "src/standards/life_sciences"


def mondo_hier() -> list[dict]:
    with open(STD / "kb_concept.csv", encoding="utf-8") as f:
        by = {r["concept_id"]: r for r in csv.DictReader(f)}
    with open(STD / "kb_edge.csv", encoding="utf-8") as f:
        rows = [
            {
                "code": e["subject"],
                "parent_code": e["object"],
                "name": by[e["subject"]]["label"],
                "relationship": "is_a",
            }
            for e in csv.DictReader(f)
            if e["predicate"] == "rdfs:subClassOf" and by[e["subject"]]["scheme"] == "MONDO"
        ]
    parents = {r["parent_code"] for r in rows} - {r["code"] for r in rows}
    return rows + [
        {"code": p, "parent_code": None, "name": by[p]["label"], "relationship": "is_a"} for p in parents
    ]


def test_contract_and_agreement_with_ontology_walk():
    hier = mondo_hier()
    rows = closure_rows(hier)
    assert not validate(hier, rows)
    onto = default_ontology()
    depth = {(r["ancestor_code"], r["descendant_code"]): r["depth"] for r in rows}
    for t in ["MONDO:0005439", "MONDO:0008585", "MONDO:0007958", "MONDO:0001999", "MONDO:0012819"]:
        anc = set(onto.ancestors(t))
        got = {a for (a, d) in depth if d == t and a != t}
        assert got == anc, (t, got ^ anc)
        for a in anc:  # shortest distance equals the BFS path length
            assert depth[(a, t)] == len(onto.path_up(t, {a})) - 1


def test_validate_catches_a_broken_closure():
    hier = [
        {"code": "B", "parent_code": "A", "name": "b", "relationship": "is_a"},
        {"code": "A", "parent_code": None, "name": "a", "relationship": "is_a"},
    ]
    rows = [r for r in closure_rows(hier) if r["depth"] != 1]
    assert validate(hier, rows)


if __name__ == "__main__":
    test_contract_and_agreement_with_ontology_walk()
    test_validate_catches_a_broken_closure()
    print("PASS")
