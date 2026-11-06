"""Retrieval-science arm runner (ADR-0020). Holds ONE fixed agent (agent.py) constant and varies the injected
retrieval approach (providers.py), with closed_book as the floor. Every (approach x question) cell is scored in
three tiers from the SAME retrieved context:

  tier 1  answer in context   -- an MLflow judge finds EACH gold fact explicitly stated in the context
  tier 2  one query           -- the agent writes exactly ONE SQL query using only names in the context (no schema
                                 given); we run it (read-only guard) and judge the result rows against each gold fact
  tier 3  neither

LLM steps vary run to run, so each cell runs --repeats times (default 3) and the majority tier is reported with
every run's tier kept. Infrastructure failures (auth, truncation) are retried and never scored.

Usage (run as a user with read access to the shared catalog):
  PYTHONPATH=src DATABRICKS_CONFIG_PROFILE=ECT .venv/bin/python -m benchmark.retrieval_eval.run_retrieval_eval \
      --out retrieval_eval_arena.json      # then copy to src/app/server/benchmark_data/
"""
from __future__ import annotations

import json
import os
import time

import mlflow

from . import agent, providers
from .warehouse import run_readonly
from server.context_retrieval import CLOSURE_TOOLS, closure_tool
from server.graph_runner import TOOLS as GRAPH_TOOLS

JUDGE = agent.JUDGE_MODEL
EXPERIMENT = os.environ.get("CARE_EVAL_EXPERIMENT", "/Shared/care_protocol_retrieval_eval")

# The scored set. Mirrors docs/benchmark/capability_matrix.csv; expected_facts are the hand-verified gold (25k).
# Chosen to exercise every arm's lift AND its blind spot -- in particular the graph-native classes (8) where the
# graph is the only arm that should reach, and the aggregate-COUNT classes (2/4/6) where a triple neighbourhood
# legitimately should NOT (it carries membership + typed edges, but doesn't aggregate -- that's closure's job).
QUESTIONS = [
    {"qid": "kpi_gsd_rate", "cls": "1_simple_kpi", "wins": "metric_view",
     "question": "What is the overall GSD compliance rate?",
     "expected_facts": ["The overall GSD compliance rate for measurement year 2026 (year-to-date) is about 74.2 percent (0.7424)."]},
    {"qid": "sub_kidney", "cls": "2_icd_subsumption", "wins": "closure_sql",
     "question": "How many patients have diabetes WITH kidney complications?",
     "expected_facts": ["1881 distinct patients have diabetes with a kidney complication."]},
    {"qid": "med_on_statin", "cls": "4_rxnorm_subsumption", "wins": "closure_sql",
     "question": "How many diabetic patients are on any statin?",
     "expected_facts": ["1651 diabetic patients are on a statin (any member of the statin drug class)."]},
    {"qid": "vintage_egfr_2026", "cls": "5_value_set_vintage", "wins": "metric_view",
     "question": "Under the 2026 KED eGFR definition, how many patients have a qualifying eGFR test?",
     "expected_facts": ["0 patients have a qualifying eGFR test under the 2026 KED definition (the MDRD code was dropped)."]},
    {"qid": "proto_cardiorenal", "cls": "6_protocol_multihop", "wins": "closure_sql",
     "question": ("Identify cardiorenal patients (diabetes + CKD + heart failure) and whether each is on "
                  "statin + ACE/ARB + SGLT2."),
     "expected_facts": ["There are 10 cardiorenal patients (diabetes AND chronic kidney disease AND heart failure).",
                        "All 10 are on a statin, 8 of the 10 are on an ACE inhibitor or ARB, and none is on an SGLT2 "
                        "inhibitor."]},
    {"qid": "def_metformin_egfr", "cls": "7_definition_provenance", "wins": "rag",
     "question": "Below what eGFR is metformin contraindicated, and where is that stated?",
     "expected_facts": ["Metformin (a biguanide) is contraindicated when eGFR is below 30 (eGFR < 30)."]},
    # Graph-native by construction: answering needs THIS patient's own records (diagnoses + prescriptions) joined to
    # the protocol's typed rules (drug class -contraindicatedWith-> value set -contains-> ICD code, with ICD and
    # RxNorm subsumption on both ends). The question names no drug class, condition or code. The rules also live
    # relationally (protocol_edges, value_set_segment) -- the graph's difference is that patient facts, hierarchies
    # and rules sit in ONE traversable structure. Gold: gold_queries.sql @id graph_contra_conflict.
    {"qid": "graph_contra_conflict", "cls": "8_graph_native", "wins": "graph",
     "question": ("Patient fa93c75f-1541-10c2-ea84-f947c8561ce5 is on a statin. Does any of their own recorded "
                  "diagnoses contraindicate it under this care protocol? Name the drug, the diagnosis and the "
                  "protocol rule."),
     # Facts are stated in codes + the rule (what the question turns on), not display names: the published
     # graph carries no labels for drugs / ICD codes / value sets, and every arm is held to the same facts.
     "expected_facts": [
         "Yes: the patient is prescribed RxNorm 314231, which belongs to the statin drug class.",
         "The patient has diagnosis ICD-10 Z34.90, which falls under Z34, a code in the CONTRA_PREGNANCY value set.",
         "The care-protocol rule is that the statin drug class is contraindicated with CONTRA_PREGNANCY."]},
    # --- Built so the closure / edge tables should NOT suffice (they hold no patient data and no measure business
    # logic) while the graph (patient layer) or Genie Ontology (definitions in snippets + Pages) holds the answer.
    # Every gold was verified against current data; the graph's patient layer agrees with gold on all five measures.
    {"qid": "graph_patient_gaps", "cls": "8_graph_native", "wins": "graph",
     "question": ("Patient 00f63646-fc2f-16a9-53e5-951816dfefe3: which diabetes quality measures are they eligible "
                  "for, and on which of those do they have an open care gap?"),
     "expected_facts": ["The patient is eligible for all five measures: GSD, KED, BPD, SPD and EED.",
                        "The patient has open care gaps on KED and EED.",
                        "The patient has no care gap on GSD, BPD and SPD."]},
    {"qid": "graph_statin_contra_cohort", "cls": "8_graph_native", "wins": "graph",
     "question": ("How many patients are prescribed a statin even though one of their own diagnoses is a statin "
                  "contraindication under the care protocol?"),
     "expected_facts": ["198 patients are prescribed a statin while having a diagnosis in a statin-contraindication "
                        "value set (all via CONTRA_PREGNANCY)."]},
    {"qid": "onto_ked_definition", "cls": "10_semantic_definition", "wins": "genie_ontology",
     "question": "Who is eligible for the KED measure, and what does a patient need to count as compliant?",
     "expected_facts": ["KED applies to diabetic patients aged 18 to 85.",
                        "To be compliant a patient needs BOTH an eGFR test and a uACR test in the measurement year."]},
    {"qid": "onto_poor_control_denominator", "cls": "10_semantic_definition", "wins": "genie_ontology",
     "question": ("Is the GSD poor-control rate calculated over all eligible patients or only some of them, and what "
                  "A1c level counts as poor control?"),
     "expected_facts": ["The GSD poor-control rate is computed only among A1c-tested patients, not all eligible patients.",
                        "Poor control means the latest A1c in the measurement year is above 9.0%."]},
    {"qid": "onto_age_and_window", "cls": "10_semantic_definition", "wins": "genie_ontology",
     "question": ("For these diabetes quality measures, at what point in time is a patient's age evaluated for "
                  "eligibility, and in what window must the required care happen?"),
     "expected_facts": ["Age is evaluated at the end of the measurement year (period end, December 31).",
                        "The required care must happen within the measurement year (January 1 to December 31)."]},
    # Structure that breaks a closure: E11.22 has two parents (E11.2 and N18). The closure keeps one row per ancestor
    # at the shortest distance and no routes; a traversal returns every route. Gold: @id graph_multiparent_routes.
    {"qid": "graph_multiparent_routes", "cls": "8_graph_native", "wins": "graph",
     "question": "Which top-level conditions does ICD-10 code E11.22 roll up to, and through which parent codes?",
     # The question asks THROUGH WHICH parents, so each fact is a route. A list of ancestors with distances (E11.2 1,
     # N18 1, E11 2) does not show a route: it can't tell whether E11 is reached through E11.2 or through N18.
     "expected_facts": [
         "The route E11.22 -> E11.2 -> E11 is shown: E11.22 reaches type 2 diabetes mellitus (E11) through E11.2. "
         "A list of ancestors with distances alone does not show this route.",
         "The route E11.22 -> N18 is shown: E11.22 reaches chronic kidney disease (N18) directly, as a second parent "
         "with no code in between."]},
    {"qid": "op_worst_clinic_annual", "cls": "9_operational_temporal", "wins": "metric_view",
     "question": "Which clinic has the lowest protocol Step-3 (A1c follow-up) adherence overall this year?",
     "expected_facts": ["CLINIC-04 has the lowest Step-3 adherence year-to-date (about 44.3%)."]},
    {"qid": "op_clinic_drift", "cls": "9_operational_temporal", "wins": "metric_view",
     "question": ("Which clinic's protocol Step-3 adherence has recently DROPPED, and by how much versus its "
                  "own history?"),
     "expected_facts": ["CLINIC-08 dropped the most: about 32% over the trailing three months versus its own "
                        "baseline of about 60%."]},
    {"qid": "op_drift_rootcause", "cls": "9_operational_temporal", "wins": "closure_sql",
     "question": "Why did CLINIC-08's protocol Step-3 adherence slip this year?",
     "expected_facts": ["CLINIC-08's Step-3 adherence slipped after a primary-care (PCP) handoff on 2026-05-15; "
                        "the follow-up order set was not carried over."]},
]

ARMS = ["closed_book", "metric_view", "closure_sql", "rag", "genie_ontology", "genie_ontology_dmvm", "ontobricks"]


def _yes(feedback) -> bool:
    v = getattr(feedback, "value", feedback)
    return str(v).strip().lower() in ("yes", "true", "1")


def retrieve(arm: str, question: str, qid: str) -> list[dict]:
    if arm == "closed_book":
        return []
    return providers.PROVIDERS[arm](question, qid)


# How each approach is allowed to query in the one-shot step: its OWN native interface.
INTERFACE = {"metric_view": "sql", "genie_ontology": "sql", "genie_ontology_dmvm": "sql", "rag": "sql",
             "closed_book": "sql", "closure_sql": "closure", "ontobricks": "graph"}
INTERFACE_LABEL = {"sql": "SQL", "closure": "closure-tool call", "graph": "graph-runner call"}


def _run_query(arm: str, query: dict) -> str:
    """Execute the one-shot query in the arm's native interface; returns the rendered result."""
    if query["kind"] == "sql":
        return _render_rows(run_readonly(query["sql"]))
    if query["interface"] == "closure":
        res = closure_tool(query["tool"], query.get("args") or {}, providers.run_sql, providers.CATALOG,
                           providers.SCHEMA, providers.SCHEMA_TERM)
    else:
        from server import graph_runner as gr
        res = gr.call(providers.graph_runner(), query["tool"], query.get("args") or {})
    from server.graph_runner import render
    return render(res)


@mlflow.trace(name="cell")
def run_cell(arm: str, q: dict) -> dict:
    """One (arm x question) cell.
      1. Retrieve with the arm's own method.
      2. Judge each gold fact against the retrieved context. All stated -> tier 1 ("answered in context").
      3. Otherwise the agent may make ONE query in the arm's native interface (SQL / closure tool / graph runner),
         using only what the context names. We run it and judge each gold fact against the result -> tier 2.
      4. Neither -> tier 3. Every judgment keeps its rationale; `reason` is a one-line summary of why."""
    mlflow.update_current_trace(tags={"arm": arm, "qid": q["qid"], "cls": q["cls"]})
    docs = retrieve(arm, q["question"], q["qid"])
    ctx = "\n\n".join(d.get("page_content", "") for d in docs) or "(no context retrieved)"

    in_ctx = [agent.judge_fact(q["question"], f, "" if not docs else ctx, "retrieved context")
              for f in q["expected_facts"]]
    sufficient = all(x["ok"] for x in in_ctx)

    interface = INTERFACE.get(arm, "sql")
    query, result, error, in_res = None, None, None, None
    if not sufficient:
        tools = {"closure": CLOSURE_TOOLS, "graph": GRAPH_TOOLS}.get(interface)
        query = agent.write_query(q["question"], docs, interface, tools)
        if query:
            try:
                result = _run_query(arm, query)
            except Exception as e:  # noqa: BLE001 -- a failed or rejected query is a miss, recorded verbatim
                error = f"{type(e).__name__}: {str(e)[:300]}"
        if result is not None:
            in_res = [agent.judge_fact(q["question"], f, result, "query result") for f in q["expected_facts"]]
    query_correct = bool(in_res) and all(x["ok"] for x in in_res)
    tier = 1 if sufficient else (2 if query_correct else 3)
    facts = [{"fact": f, "in_context": in_ctx[k], "in_result": (in_res[k] if in_res else None)}
             for k, f in enumerate(q["expected_facts"])]
    what = ("retrieved nothing" if not docs else
            "every gold fact is stated in what it retrieved (no query needed)" if sufficient else
            "not every fact was in what it retrieved; the agent declined to write a query (NO_QUERY)" if not query else
            f"not every fact was in what it retrieved; the agent's {INTERFACE_LABEL[interface]} failed" if error else
            f"not every fact was in what it retrieved; the agent's {INTERFACE_LABEL[interface]} ran")
    outcome = {"tier": tier, "what_happened": what, "interface": INTERFACE_LABEL[interface],
               "retrieved": providers.summarize(arm, docs),
               "facts": facts,
               "query": query, "query_result": (result or "")[:1500], "query_error": error}
    reason = agent.explain(q["question"], arm, outcome)
    skipped = providers.genie_skipped(arm, q["qid"])
    return {"arm": arm, "qid": q["qid"], "tier": tier, "sufficient": sufficient, "query_correct": query_correct,
            "interface": INTERFACE_LABEL[interface], "query": query,
            "sql": (query or {}).get("sql") or (json.dumps({k: query[k] for k in ("tool", "args")}) if query else None),
            "sql_error": error, "sql_result": (result or None) and result[:2500],
            "facts": facts, "reason": reason, "retrieved": outcome["retrieved"],
            "n_docs": len(docs), "skipped_search": bool(skipped),
            "facts_in_context": [x["ok"] for x in in_ctx], "facts_in_result": [x["ok"] for x in in_res] if in_res else None,
            "context": ctx[:6000]}


def _render_rows(rows, limit: int = 40) -> str:
    if not rows:
        return "(query returned no rows)"
    cols = list(rows[0].keys())
    lines = [" | ".join(cols)] + [" | ".join(str(r.get(c)) for c in cols) for r in rows[:limit]]
    return "\n".join(lines) + (f"\n... ({len(rows)} rows total)" if len(rows) > limit else "")


def main():
    import argparse
    global ARMS
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default=",".join(ARMS), help="comma-separated subset of " + ",".join(ARMS))
    ap.add_argument("--out", default="retrieval_eval.json", help="file name under docs/benchmark/")
    ap.add_argument("--merge", action="store_true", help="replace only the (arm, question) rows run now in --out")
    ap.add_argument("--qids", default="", help="comma-separated question ids (default: the demo set in the CSV)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--repeats", type=int, default=1, help="runs per cell; the majority tier is reported")
    args = ap.parse_args()
    ARMS = [a for a in args.arms.split(",") if a]
    # Judges authenticate to Databricks via the model URI regardless of the trace store, so if the SP cannot
    # create the workspace experiment we fall back to a LOCAL trace store -- the matrix is still produced.
    try:
        mlflow.set_tracking_uri("databricks")
        mlflow.set_experiment(EXPERIMENT)
        print(f"Tracing to Databricks experiment {EXPERIMENT}")
    except Exception as e:  # noqa: BLE001
        local = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".mlruns")
        mlflow.set_tracking_uri("file:" + os.path.normpath(local))
        print(f"(workspace experiment unavailable: {type(e).__name__}: {str(e)[:100]}; "
              f"tracing locally to {local})")

    from concurrent.futures import ThreadPoolExecutor

    providers.warm()  # populate metadata caches once, before the parallel cells

    def one(cell):
        q, arm = cell
        t0 = time.time()
        r, err = None, None
        for attempt in range(3):  # infra failures (auth blips, truncation, endpoint errors) are retried
            try:
                r = run_cell(arm, q)
                break
            except Exception as e:  # noqa: BLE001
                err = f"{type(e).__name__}: {str(e)[:200]}"
                time.sleep(3 * (attempt + 1))
        if r is None:  # still failing: recorded as a harness error and EXCLUDED from the majority vote
            r = {"arm": arm, "qid": q["qid"], "tier": None, "harness_error": err, "n_docs": 0}
        r["latency_s"] = round(time.time() - t0, 1)
        print(f"  {q['qid']:<22} {arm:<20} tier={r['tier']} docs={r['n_docs']:<4} "
              f"sql={'yes' if r.get('sql') else 'NO_QUERY'}{' ERR' if r.get('sql_error') else ''}"
              f"{' HARNESS-ERROR' if r.get('harness_error') else ''} ({r['latency_s']}s)", flush=True)
        return r

    # Default question set = the demo set in docs/benchmark/capability_matrix.csv (the rest are archived in
    # capability_matrix_full.csv and still runnable with --qids).
    import csv
    demo = [x["question_id"] for x in csv.DictReader(open(os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "docs", "benchmark", "capability_matrix.csv")))]
    wanted = args.qids.split(",") if args.qids else demo
    cells = [(q, arm) for _ in range(args.repeats) for q in QUESTIONS for arm in ARMS if q["qid"] in wanted]
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        runs = list(ex.map(one, cells))
    # The agent (tier 2) and judges are LLMs, so a cell can differ run to run. Report the MAJORITY tier over
    # --repeats runs (ties -> the worse tier), keep every run's tier, and flag cells that were not unanimous.
    groups: dict[tuple, list[dict]] = {}
    for r in runs:
        groups.setdefault((r["arm"], r["qid"]), []).append(r)
    rows = []
    for (arm, qid), rs in groups.items():
        tiers = [r["tier"] for r in rs if r["tier"] is not None]
        if not tiers:
            rows.append({**rs[0], "tier_runs": [], "stable": False, "runs": []})
            continue
        maj = max(sorted(set(tiers), reverse=True), key=tiers.count)
        rep = dict(next(r for r in rs if r["tier"] == maj))
        rep.update({"tier_runs": tiers, "stable": len(set(tiers)) == 1,
                    "harness_errors": sum(r["tier"] is None for r in rs),
                    "runs": [{"tier": r["tier"], "sql": (r.get("sql") or "")[:1500], "sql_error": r.get("sql_error"),
                              "facts_in_context": r.get("facts_in_context"), "facts_in_result": r.get("facts_in_result")}
                             for r in rs]})
        rows.append(rep)

    by = {(r["arm"], r["qid"]): r for r in rows}
    print("\n=== Tier by question x arm (1 = in context, 2 = one query from context, 3 = neither) ===")
    print("question".ljust(24) + "".join(a[:12].ljust(13) for a in ARMS))
    for q in QUESTIONS:
        if (ARMS[0], q["qid"]) in by:
            print(q["qid"].ljust(24) + "".join((str(by[(a, q["qid"])]["tier"]) + ("" if by[(a, q["qid"])]["stable"]
                  else "~" + "".join(map(str, by[(a, q["qid"])]["tier_runs"])))).ljust(13) for a in ARMS))

    out = os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "benchmark", args.out)
    out = os.path.normpath(out)
    if args.merge and os.path.isfile(out):
        done = {(r["arm"], r["qid"]) for r in rows}
        old = [x for x in json.load(open(out)).get("rows", []) if (x["arm"], x["qid"]) not in done]
        rows = old + rows
    json.dump({"judge": JUDGE, "agent": agent.AGENT_MODEL, "scoring": "tiers-v1", "repeats": args.repeats, "rows": rows}, open(out, "w"), indent=2, default=str)
    print(f"\nPer-cell detail -> {out}")
    if providers._rag_error:
        print(f"NOTE: RAG arm ran in degraded mode ({providers._rag_error}).")


if __name__ == "__main__":
    main()
