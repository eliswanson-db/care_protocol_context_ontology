"""Acceptance checks for an Ontobricks graph version BEFORE the app is pointed at it (read-only).

  .venv/bin/python -I scripts/check_graph_version.py --graph eswanson_demo.ontobricks.triplestore_clinicaldomain_v4_graph
  # simulate a republish: the live compiled-mapping VIEW recomputes the triples from today's source tables
  .venv/bin/python -I scripts/check_graph_version.py --graph eswanson_demo.ontobricks.triplestore_clinicaldomain_v3

REQUIRED checks protect the app and the eval (IRI convention, no lost predicates, the expected new edges, the graph
runner's tool results). OPTIONAL checks track the Ontobricks-side mapping fixes (names on the edge nodes, every drug
class's membership, clean hasIngredient). Exit code 0 only if every REQUIRED check passes.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "src", "app")))
os.environ.setdefault("DATABRICKS_CONFIG_PROFILE", "ECT")

from benchmark.retrieval_eval.warehouse import fetch_all, run_sql  # noqa: E402
from server import graph_runner as gr  # noqa: E402
from server.context_retrieval import graph_context  # noqa: E402

NS = "https://care-protocol.example/ontology/"
BASELINE = "eswanson_demo.ontobricks.triplestore_clinicaldomain_v3_graph"
OBS = f"'{NS}hasObservation', '{NS}ofTest', '{NS}resultValue'"
# Edge-endpoint prefixes the app, the entity linker and the graph tools rely on.
EDGE_PREFIXES = {"Patient", "icd", "rx", "ing", "DrugClass", "Measure", "ValueSet", "Threshold", "part", "loinc"}

results: list[tuple[str, str, bool, str]] = []


def check(level: str, name: str, ok: bool, detail: str = ""):
    results.append((level, name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} [{level:<8}] {name}{(' -- ' + detail) if detail else ''}", flush=True)


def pred_counts(table: str) -> dict[str, int]:
    rows = run_sql(f"SELECT regexp_extract(predicate, '([^/#]+)$', 1) AS p, count(*) AS n FROM {table} "
                   f"WHERE predicate NOT IN ({OBS}) GROUP BY 1")
    return {r["p"]: int(r["n"]) for r in rows}


def edge_prefixes(table: str) -> set[str]:
    """IRI prefixes (Patient, icd, rx, ...) of every node that takes part in an edge, as subject or object."""
    rows = run_sql(f"SELECT DISTINCT p FROM (SELECT regexp_extract(subject, '^{NS}([^/]+)/', 1) AS p FROM {table} "
                   f"WHERE predicate NOT IN ({OBS}) AND object LIKE '{NS}%/%' UNION ALL "
                   f"SELECT regexp_extract(object, '^{NS}([^/]+)/', 1) FROM {table} WHERE predicate NOT IN ({OBS}) "
                   f"AND object LIKE '{NS}%/%')")
    return {r["p"] for r in rows if r["p"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", required=True, help="catalog.schema.table (or view) to check")
    args = ap.parse_args()
    g_tab = args.graph

    # ---- structure vs the v3 baseline --------------------------------------------------------------------------
    base, new = pred_counts(BASELINE), pred_counts(g_tab)
    lost = sorted(p for p in base if p not in new)
    check("REQUIRED", "no predicate lost vs v3", not lost, f"lost: {lost}" if lost else f"{len(new)} predicates")
    shrunk = sorted(f"{p} {base[p]}->{new.get(p, 0)}" for p in base
                    if p in new and new[p] < 0.9 * base[p] and p not in ("hasIngredient",))
    check("REQUIRED", "no predicate shrank >10% (hasIngredient may shrink by design)", not shrunk, "; ".join(shrunk))
    prefixes, base_prefixes = edge_prefixes(g_tab), edge_prefixes(BASELINE)
    ok = EDGE_PREFIXES <= prefixes and prefixes == base_prefixes
    check("REQUIRED", "edge nodes keep the v3 IRI convention", ok,
          f"missing {sorted(base_prefixes - prefixes)}, new {sorted(prefixes - base_prefixes)}" if not ok else
          ", ".join(sorted(prefixes)))

    one = lambda sql: int(run_sql(sql)[0]["n"])  # noqa: E731
    check("REQUIRED", "multi-parent edge icd/E11.22 subClassOf icd/N18",
          one(f"SELECT count(*) AS n FROM {g_tab} WHERE subject = '{NS}icd/E11.22' AND predicate LIKE '%subClassOf' "
              f"AND object = '{NS}icd/N18'") == 1)
    check("REQUIRED", "BPD monitoredBy LP-SBP and LP-DBP (Nov 4 protocol_edges fix)",
          one(f"SELECT count(*) AS n FROM {g_tab} WHERE subject = '{NS}Measure/BPD' AND predicate LIKE '%monitoredBy' "
              f"AND object IN ('{NS}part/LP-SBP', '{NS}part/LP-DBP')") == 2)

    # ---- the Ontobricks-side mapping fixes (optional until ported) ---------------------------------------------
    for prefix, sample in (("icd", "icd/E11.2"), ("rx", "rx/314231"), ("ing", "ing/6809"),
                           ("DrugClass", "DrugClass/DRUGCLASS-ACE"), ("ValueSet", "ValueSet/CONTRA_PREGNANCY")):
        n = one(f"SELECT count(*) AS n FROM {g_tab} WHERE subject = '{NS}{sample}' AND predicate LIKE '%rdf-schema#label'")
        check("OPTIONAL", f"name on the edge node {sample}", n >= 1)
    n_cls = one(f"SELECT count(*) AS n FROM {g_tab} WHERE predicate LIKE '%inDrugClass'")
    check("OPTIONAL", "inDrugClass for every class (16 ingredient memberships; v3 has 3)", n_cls >= 16, f"{n_cls} edges")
    n_bad = one(f"SELECT count(*) AS n FROM {g_tab} WHERE predicate LIKE '%hasIngredient' AND object LIKE '%/DRUGCLASS-%'")
    check("OPTIONAL", "hasIngredient never points at a drug class", n_bad == 0, f"{n_bad} such edges")

    # ---- the graph runner on this version (what the eval's one-shot step uses) --------------------------------
    g = gr.load(g_tab, fetch_all, ttl_s=0)
    check("REQUIRED", "graph runner loads", g.n_edges > 100_000, f"{g.n_edges:,} edges")
    cohort = gr.call(g, "match", {"pattern": [
        ["?p", "prescribed", "?rx"], ["?rx", "hasIngredient", "?ing"], ["?ing", "inDrugClass", "DrugClass/DRUGCLASS-STATIN"],
        ["DrugClass/DRUGCLASS-STATIN", "contraindicatedWith", "?vs"], ["?vs", "contains", "?code"],
        ["?p", "hasDiagnosis", "?dx"], ["?dx", "subClassOf*", "?code"]], "select": "?p"})["count"]
    check("REQUIRED", "statin-contraindication cohort = 198 (gold)", cohort == 198, str(cohort))
    kidney = gr.call(g, "match", {"pattern": [["?p", "hasDiagnosis", "?dx"], ["?dx", "subClassOf*", "icd/E11.2"]],
                                  "select": "?p"})["count"]
    check("REQUIRED", "diabetes with kidney complications (E11.2 subtree) = 1881 (gold)", kidney == 1881, str(kidney))
    routes = {r["end"] for r in gr.call(g, "routes", {"node": "icd/E11.22", "predicate": "subClassOf"})["rows"]}
    check("REQUIRED", "routes(E11.22) reaches both E11 and N18", routes == {"icd/E11", "icd/N18"}, str(sorted(routes)))
    met = gr.call(g, "find_nodes", {"text": "metformin"})["count"]
    check("OPTIONAL", "find_nodes('metformin') finds a node by name", met >= 1, f"{met} nodes")
    ace = gr.call(g, "match", {"pattern": [["?p", "prescribed", "?rx"], ["?rx", "hasIngredient", "?ing"],
                                           ["?ing", "inDrugClass", "DrugClass/DRUGCLASS-ACE"]], "select": "?p"})["count"]
    check("OPTIONAL", "patients on an ACE inhibitor reachable via inDrugClass", ace > 0, str(ace))

    # ---- the entity linker / retrieval the Arena and eval use -------------------------------------------------
    for q in ("How many patients have diabetes WITH kidney complications?",
              "How many patients are prescribed a statin even though one of their own diagnoses is a statin "
              "contraindication under the care protocol?",
              "Which top-level conditions does ICD-10 code E11.22 roll up to, and through which parent codes?"):
        docs = graph_context(q, run_sql, g_tab)
        check("REQUIRED", f"graph retrieval returns triples: {q[:55]}...", len(docs) > 1, f"{len(docs) - 1} triples")

    req = [r for r in results if r[0] == "REQUIRED"]
    opt = [r for r in results if r[0] == "OPTIONAL"]
    print(f"\nREQUIRED {sum(r[2] for r in req)}/{len(req)} passed; OPTIONAL {sum(r[2] for r in opt)}/{len(opt)} passed")
    sys.exit(0 if all(r[2] for r in req) else 1)


if __name__ == "__main__":
    main()
