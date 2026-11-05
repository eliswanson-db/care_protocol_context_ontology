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
from mlflow.genai.judges import meets_guidelines

from . import agent, providers
from .warehouse import run_readonly

JUDGE = os.environ.get("CARE_JUDGE_MODEL", "databricks:/databricks-claude-sonnet-5")
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
     "expected_facts": ["There are 10 cardiorenal patients (diabetes AND chronic kidney disease AND heart failure)."]},
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
                  "protocol rule, and show the connecting path."),
     # Facts are stated in codes + the rule (what the question turns on), not display names: the published
     # graph carries no labels for drugs / ICD codes / value sets, and every arm is held to the same facts.
     "expected_facts": [
         "Yes: the patient is prescribed RxNorm 314231, which belongs to the statin drug class.",
         "The patient has diagnosis ICD-10 Z34.90, which falls under Z34, a code in the CONTRA_PREGNANCY value set.",
         "The care-protocol rule is that the statin drug class is contraindicated with CONTRA_PREGNANCY."]},
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


@mlflow.trace(name="cell")
def run_cell(arm: str, q: dict) -> dict:
    """One (arm x question) cell, scored in three tiers from the SAME retrieved context:
      tier 1  the answer is directly in the retrieved context           (sufficiency judge over the context)
      tier 2  the context gives what's needed for ONE query that answers (agent writes one SQL from the context
              only; we RUN it and judge the result rows against the gold facts)
      tier 3  neither."""
    mlflow.update_current_trace(tags={"arm": arm, "qid": q["qid"], "cls": q["cls"]})
    docs = retrieve(arm, q["question"], q["qid"])
    ctx = "\n\n".join(d.get("page_content", "") for d in docs) or "(no context retrieved)"

    # Tier 1: judged ONE FACT AT A TIME (all must pass) -- a single all-facts judge proved lenient and flipped
    # between runs (it accepted a general rule as evidence of a patient-specific fact).
    fact_t1 = [_yes(meets_guidelines(
        name="in_context",
        guidelines=("The retrieved_documents EXPLICITLY state the following fact about the entities in the question. "
                    "It is NOT enough that they state a general rule from which the fact could be inferred, list "
                    "codes it could be looked up with, or describe how it could be computed. Answer 'no' if the "
                    "documents are empty. FACT: " + f),
        context={"question": q["question"], "retrieved_documents": ctx}, model=JUDGE)) for f in q["expected_facts"]]
    sufficient = all(fact_t1)

    sql = agent.write_sql(q["question"], docs)
    sql_rows, sql_error, query_correct, fact_t2 = None, None, False, None
    if sql:
        try:
            sql_rows = run_readonly(sql)
        except Exception as e:  # noqa: BLE001 -- a failed or rejected query is a tier-2 miss, recorded verbatim
            sql_error = f"{type(e).__name__}: {str(e)[:300]}"
    if sql_rows is not None:
        result = _render_rows(sql_rows)
        fact_t2 = [_yes(meets_guidelines(
            name="query_result_correct",
            guidelines=("The query_result rows establish the following fact. Allow formatting differences (a rate "
                        "as a fraction or percent, rounding to 3 significant figures, a count given as the number of "
                        "returned rows, codes with or without a prefix). Answer 'no' if the result is empty, shows a "
                        "different value, or answers a different question. FACT: " + f),
            context={"question": q["question"], "query": sql, "query_result": result}, model=JUDGE))
            for f in q["expected_facts"]]
        query_correct = all(fact_t2)
    tier = 1 if sufficient else (2 if query_correct else 3)
    skipped = providers.genie_skipped(arm, q["qid"])
    return {"arm": arm, "qid": q["qid"], "tier": tier, "sufficient": sufficient, "query_correct": query_correct,
            "sql": sql, "sql_error": sql_error, "sql_result": _render_rows(sql_rows)[:2500] if sql_rows is not None else None,
            "n_docs": len(docs), "skipped_search": bool(skipped), "facts_in_context": fact_t1,
            "facts_in_result": fact_t2, "context": ctx[:6000]}


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
    ap.add_argument("--qids", default="", help="comma-separated subset of question ids")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--repeats", type=int, default=3, help="runs per cell; the majority tier is reported")
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

    cells = [(q, arm) for _ in range(args.repeats) for q in QUESTIONS for arm in ARMS
             if not args.qids or q["qid"] in args.qids.split(",")]
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
