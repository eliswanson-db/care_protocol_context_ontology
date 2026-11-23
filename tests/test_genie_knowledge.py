"""Genie knowledge stores (ADR-0027): parity with code, API constraints, demo isolation. No workspace.

The live check (every snippet/join/benchmark runs and matches) is `scripts/genie_knowledge.py --validate`;
it also refreshes src/genie/table_columns.json, the schema snapshot used here.

    python3 -I tests/test_genie_knowledge.py   (or pytest)

"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genie.knowledge_stores import stores  # noqa: E402

STORES = stores()
SCHEMA = json.loads((ROOT / "src/genie/table_columns.json").read_text())
REG = yaml.safe_load((ROOT / "src/clinical_study/rules/registry.yaml").read_text())


def _gk():
    spec = importlib.util.spec_from_file_location("gk", ROOT / "scripts/genie_knowledge.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _space(key):
    return json.loads((ROOT / STORES[key].file).read_text())


def test_space_files_are_current():
    gk = _gk()
    for key, st in STORES.items():
        on_disk = _space(key)
        assert gk.body_with(st, key, json.loads(json.dumps(on_disk))) == on_disk, (
            f"{key}: rerun scripts/genie_knowledge.py"
        )


def test_api_constraints_ids_unique_and_sorted():
    for key in STORES:
        b = _space(key)
        ins = b["instructions"]
        ids = (
            [x["id"] for x in ins.get("text_instructions", [])]
            + [x["id"] for x in ins.get("example_question_sqls", [])]
            + [x["id"] for x in ins.get("join_specs", [])]
            + [x["id"] for v in ins.get("sql_snippets", {}).values() for x in v]
        )
        assert len(ids) == len(set(ids)), key
        for arr in [
            ins.get("join_specs", []),
            *ins.get("sql_snippets", {}).values(),
            b.get("benchmarks", {}).get("questions", []),
        ]:
            assert [x["id"] for x in arr] == sorted(x["id"] for x in arr), key
        qids = [x["id"] for x in b.get("config", {}).get("sample_questions", [])] + [
            x["id"] for x in b.get("benchmarks", {}).get("questions", [])
        ]
        assert len(qids) == len(set(qids)), key
        assert all(re.fullmatch(r"[0-9a-f]{32}", i) for i in ids + qids), key


def test_snippets_reference_real_columns_of_their_space_only():
    bad = []
    for key, st in STORES.items():
        tables = {t["identifier"] for t in _space(key)["data_sources"].get("tables", [])}
        by_short = {t.split(".")[-1]: t for t in tables}
        for s in st.snippets:
            sql = re.sub(r"'[^']*'", "", s.sql)
            # qualified references in the snippet body (subqueries use full names, checked below)
            for q, col in re.findall(r"(?<![\w.])([A-Za-z_]\w*)\.([A-Za-z_]\w*)\b", sql):
                if q in by_short and col not in SCHEMA[by_short[q]]:
                    bad.append((key, s.name, f"{q}.{col}"))
            for fq in re.findall(r"eli_test_classic_catalog\.\w+\.\w+", s.sql):
                if fq not in tables:
                    bad.append((key, s.name, f"subquery table {fq} not in the space"))
        for j in st.joins:
            for q, col in re.findall(r"([A-Za-z_]\w*)\.([A-Za-z_]\w*)", j.on):
                if col not in SCHEMA.get(by_short.get(q, ""), [col]):
                    bad.append((key, "join", f"{q}.{col}"))
        for t, cfg in st.columns.items():
            bad += [(key, "column", f"{t}.{c}") for c in cfg if t not in tables or c not in SCHEMA[t]]
    assert not bad, bad


def test_demo_isolation():
    for key, st in STORES.items():
        text = json.dumps(_space(key))
        other = "clinical_study" if st.demo == "healthcare_hedis" else "care_protocol"
        assert f"eli_test_classic_catalog.{other}" not in text, key


def test_hedis_thresholds_come_from_the_metric_views():
    src = " ".join(p.read_text() for p in (ROOT / "src/semantic/metric_views").glob("*.sql"))
    allowed = {float(x) for x in re.findall(r"(?<![\w.-])\d+(?:\.\d+)?(?![\w-])", src)} | {0.0, 1.0, 5.0}
    import csv  # value-set version years are canonical in the vendored value sets

    with open(ROOT / "src/terminology/value_sets_demo.csv", encoding="utf-8") as f:
        allowed |= {float(r["measurement_year"]) for r in csv.DictReader(f)}
    bad = []
    for key, st in STORES.items():
        if st.demo != "healthcare_hedis":
            continue
        for s in st.snippets:
            for x in re.findall(r"(?<![\w.'-])\d+(?:\.\d+)?(?![\w'-])", re.sub(r"'[^']*'", "", s.sql)):
                if float(x) not in allowed:
                    bad.append((key, s.name, x))
    assert not bad, bad


def test_ls_snippets_restate_the_registry():
    versions = {
        f"{e}.{v}"
        for e, ep in REG["endpoints"].items()
        for v, r in ep["rule_versions"].items()
        if r["review_state"] == "approved"
    }
    classes, studies = set(REG["concept_classes"]), set(REG["studies"])
    glp = REG["concept_classes"]["CI-STUDY-DRUG-CLASS"]["drug_class"]
    seen_versions = set()
    for key, st in STORES.items():
        if st.demo != "life_sciences_clinical":
            continue
        for s in st.snippets:
            for v in re.findall(r"'(EP-[AB]-WT24\.\w+)'", s.sql):
                assert v in versions, (s.name, v)
                seen_versions.add(v)
            for c in re.findall(r"class_id = '([\w-]+)'", s.sql):
                assert c in classes, (s.name, c)
            for sid in re.findall(r"STUDYID = '([\w-]+)'|study_id = '([\w-]+)'", s.sql):
                assert set(sid) - {""} <= studies, (s.name, sid)
            for m in re.findall(r"'(MEDRT:N\d+)'", s.sql):
                assert m == glp, (s.name, m)
            assert not re.search(r"'MONDO:\d+'", s.sql), (
                f"{s.name}: class membership must come from class_root"
            )
    assert seen_versions == versions, "every approved rule version needs exactly its own filter"


def test_ls_benchmarks_name_no_hand_authored_participant():
    # The demo data has only generated participants; a benchmark naming a test participant (FX-*) could never pass.
    for k in ("ls_study_analytics", "ls_protocol_evidence", "ls_standards_semantics"):
        for x in STORES[k].benchmarks:
            assert "-FX-" not in x.question + x.sql, (k, x.question)
        for sn in STORES[k].snippets:
            assert "-FX-" not in json.dumps(sn.__dict__, default=str), (k, sn)


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                fails += 1
                print(f"FAIL {name}: {str(e)[:300]}")
    sys.exit(1 if fails else 0)
