"""The vendored life-sciences KB must keep the multi-hop paths the demo depends on (ADR-0022 gate, G1-G5).

Deterministic, no workspace. Runs on src/standards/life_sciences/kb_{concept,edge}.csv.
    python3 -I tests/test_ls_kb_paths.py      # or: pytest tests/test_ls_kb_paths.py
"""

from __future__ import annotations

import collections
import csv
from functools import lru_cache
from pathlib import Path

STD = Path(__file__).resolve().parents[1] / "src" / "standards" / "life_sciences"
GLP1_MOA = "MEDRT:N0000020058"  # Glucagon-like Peptide-1 (GLP-1) Agonists [MoA]
GLP1_EPC = "MEDRT:N0000178480"  # GLP-1 Receptor Agonist [EPC]


@lru_cache(maxsize=1)
def kb():
    concepts = {r["concept_id"]: r for r in csv.DictReader(open(STD / "kb_concept.csv", encoding="utf-8"))}
    out, inv = collections.defaultdict(list), collections.defaultdict(list)
    for e in csv.DictReader(open(STD / "kb_edge.csv", encoding="utf-8")):
        out[(e["subject"], e["predicate"])].append(e["object"])
        inv[(e["object"], e["predicate"])].append(e["subject"])
    return concepts, out, inv


def ancestors(c: str) -> set[str]:
    _, out, _ = kb()
    seen, st = set(), [c]
    while st:
        for p in out.get((st.pop(), "rdfs:subClassOf"), []):
            if p not in seen:
                seen.add(p)
                st.append(p)
    return seen


def descendants(c: str) -> set[str]:
    _, _, inv = kb()
    seen, st = set(), [c]
    while st:
        for k in inv.get((st.pop(), "rdfs:subClassOf"), []):
            if k not in seen:
                seen.add(k)
                st.append(k)
    return seen


EQUIV = ("skos:exactMatch", "oboInOwl:hasDbXref", "cpl:curatedEquivalent")


def broader_mesh(x: str) -> list[str]:
    """A MeSH record and everything BROADER than it (SCR -> mapped descriptor -> tree ancestors)."""
    _, out, _ = kb()
    seen, st = [x], [x]
    while st:
        cur = st.pop()
        for p in ("mesh:headingMappedTo", "mesh:broaderDescriptor"):
            for y in out.get((cur, p), []):
                if y not in seen:
                    seen.append(y)
                    st.append(y)
    return seen


def contraindicated_drugs(disease: str) -> dict[str, list[str]]:
    """Sound walk, BROADENING ONLY: MONDO disease -> is_a* ancestor -> equivalent MeSH record -> broader MeSH
    records -> MeSH concept <- CI_with <- drug. (Never step down to a narrower record: a sibling disease would
    inherit contraindications it doesn't have.) Returns drug -> the first path found."""
    _, out, inv = kb()
    hits: dict[str, list[str]] = {}
    for d in [disease, *sorted(ancestors(disease))]:
        for pred in EQUIV:
            for x in out.get((d, pred), []):
                if not x.startswith("MESH:"):
                    continue
                for rec in broader_mesh(x):
                    for m in inv.get((rec, "mesh:conceptOf"), []):
                        for drug in inv.get((m, "medrt:CI_with"), []):
                            hits.setdefault(drug, [disease, d, x, rec, m, drug])
    return hits


def is_glp1(drug: str) -> bool:
    _, out, _ = kb()
    return GLP1_MOA in out.get((drug, "medrt:has_MoA"), []) or GLP1_EPC in out.get(
        (drug, "medrt:memberOf"), []
    )


def label(c: str) -> str:
    return kb()[0].get(c, {}).get("label", "")


def test_g2_men2a_contraindicates_glp1_ras_directly():
    hits = {d for d in contraindicated_drugs("MONDO:0008234") if is_glp1(d)}
    names = {label(d) for d in hits}
    assert {"dulaglutide", "liraglutide"} <= names, names


def test_g2_mtc_reaches_glp1_ras_only_through_the_curated_bridge():
    """A participant coded at MTC (MONDO:0015277) reaches GLP-1 RA contraindications only through the
    namespaced curated equivalence to MeSH SCR C536914 (MONDO lacks the xref). MED-RT is not uniform across
    the class: tirzepatide carries the MTC contraindication on a different record, so it is NOT reached from
    MTC itself. That inconsistency is the class-propagation story (one member contraindicated -> review the
    class)."""
    glp = {label(d): path for d, path in contraindicated_drugs("MONDO:0015277").items() if is_glp1(d)}
    assert set(glp) == {"semaglutide", "dulaglutide"}, glp
    assert all(p[2] == "MESH:C536914" for p in glp.values()), glp


def test_g2_familial_mtc_leaf_has_its_own_route():
    """Familial MTC (child of MTC) carries its own MeSH SCR xref and reaches more class members directly."""
    leaf = "MONDO:0007958"
    assert "MONDO:0015277" in ancestors(leaf)
    glp = {label(d) for d in contraindicated_drugs(leaf) if is_glp1(d)}
    assert {"semaglutide", "dulaglutide", "liraglutide", "tirzepatide"} <= glp, glp


def test_g2_walk_is_sound_no_sibling_inherits_mtc_contraindications():
    """Small cell lung carcinoma is another neuroendocrine carcinoma. It must NOT reach GLP-1 RA
    contraindications; that would require stepping down from 'Carcinoma, Neuroendocrine' to the
    narrower MTC record."""
    sclc = "MONDO:0008433"  # small cell lung carcinoma
    assert label(sclc) == "small cell lung carcinoma"
    assert "MONDO:0002120" in ancestors(sclc)  # neuroendocrine carcinoma: same parent the unsound route used
    assert not [d for d in contraindicated_drugs(sclc) if is_glp1(d)]


def test_g1_comorbidity_class_is_polyhierarchical_and_deep():
    _, out, _ = kb()
    roots = ["MONDO:0005044", "MONDO:0021187", "MONDO:0005148", "MONDO:0005010"]
    members = set().union(*(descendants(r) for r in roots))
    assert len(members) >= 60
    multi = [m for m in members if len(out.get((m, "rdfs:subClassOf"), [])) > 1]
    assert len(multi) >= 15
    in_class = set().union(*(descendants(r) | {r} for r in roots))
    depth = max(len(ancestors(m) & in_class) for m in members)
    assert depth >= 3


def test_g3_prohibited_by_class_and_by_effect():
    concepts, _, inv = kb()
    by_class = {label(d) for d in inv.get((GLP1_EPC, "medrt:memberOf"), [])}
    assert {"semaglutide", "tirzepatide", "liraglutide"} <= by_class
    appetite = next(c for c, r in concepts.items() if r["label"] == "Appetite Suppression [PE]")
    by_pe = {label(d) for d in inv.get((appetite, "medrt:has_PE"), [])}
    assert "phentermine" in by_pe and not (by_pe & {"metformin", "atorvastatin"})


def test_g5_body_weight_concept_to_sdtm_variable_and_units():
    concepts, out, inv = kb()
    dss = inv.get(("COSMOS_BC:C81328", "cosmos:specializes"), [])
    assert "COSMOS_DSS:WEIGHT" in dss
    bindings = out[("COSMOS_DSS:WEIGHT", "cosmos:hasVariableBinding")]
    unit_binding = next(b for b in bindings if "SDTM:VS.VSORRESU" in out.get((b, "cosmos:constrains"), []))
    units = {concepts[t]["notation"] for t in out.get((unit_binding, "cosmos:allowedValue"), [])}
    assert units == {"LB", "g", "kg"}
    testcd = next(b for b in bindings if "SDTM:VS.VSTESTCD" in out.get((b, "cosmos:constrains"), []))
    assert {concepts[t]["notation"] for t in out[(testcd, "cosmos:assignedValue")]} == {"WEIGHT"}


def test_kb_has_no_dangling_references_and_only_direct_assertions():
    concepts, out, _ = kb()
    for (s, _p), objs in out.items():
        assert s in concepts, s
        for o in objs:
            assert o in concepts, o
    # direct-only: no edge duplicates a 2-hop is_a path (a materialized transitive edge)
    for (s, p), parents in out.items():
        if p != "rdfs:subClassOf":
            continue
        grand = {g for q in parents for g in out.get((q, "rdfs:subClassOf"), [])}
        assert not (set(parents) & grand) or s in {"MONDO:0000001"}, (s, set(parents) & grand)


if __name__ == "__main__":
    import sys

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
