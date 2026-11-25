"""Retrieval-science arm runner (ADR-0020). Holds ONE fixed agent (agent.py) constant and varies the injected
retrieval approach (providers.py), with closed_book as the floor. Every (approach x question) cell is scored in
three tiers from the SAME retrieved context:

  tier 1  answer in context   -- an MLflow judge finds EACH gold fact explicitly stated in the context
  tier 2  one query           -- the agent writes exactly ONE SQL query using only names in the context (no schema
                                 given); we run it (read-only guard) and judge the result rows against each gold fact
  tier 3  neither

LLM steps vary run to run, so each cell runs --repeats times and the majority tier is reported with every run's tier
kept. Test mode (the default) is 1 run per cell; use --final (= 3 runs) only for final demo testing, since every run
costs model and warehouse time. Infrastructure failures (auth, truncation) are retried and never scored.

Usage (run as a user with read access to the shared catalog):
  PYTHONPATH=src DATABRICKS_CONFIG_PROFILE=ECT .venv/bin/python -m benchmark.retrieval_eval.run_retrieval_eval \
      --out retrieval_eval_arena.json      # then copy to src/app/server/benchmark_data/
"""
from __future__ import annotations

import json
import os
import re
import time

import mlflow

from . import agent, providers
from .warehouse import run_readonly
from server.graph_runner import TOOLS as GRAPH_TOOLS

JUDGE = agent.JUDGE_MODEL
EXPERIMENT = os.environ.get("CARE_EVAL_EXPERIMENT", "/Shared/care_protocol_retrieval_eval")

# The scored set: the locked HEDIS benchmark v2 (docs/benchmark/questions_v2.yaml). Real analyst questions, fixed
# dates, hand-verified expected facts; nothing is designed to win (each question's predictions are checked, not
# assumed). The previous set is in git history.
QUESTIONS = [{"qid": q["id"], "cls": "v2", "question": q["question"], "expected_facts": q["expected_facts"]}
             for q in providers.QMETA.values()]

# The five approaches. closed_book (no retrieval, the floor) is available with --arms; the ECT/DMVM split is retired.
ARMS = ["metric_view", "closure_sql", "rag", "genie_ontology", "ontobricks"]
ALL_ARMS = ["closed_book", *ARMS, "genie_one"]  # genie_one = Genie One as the reasoning engine (step 6 column)


def _yes(feedback) -> bool:
    v = getattr(feedback, "value", feedback)
    return str(v).strip().lower() in ("yes", "true", "1")


def retrieve(arm: str, question: str, qid: str) -> list[dict]:
    if arm == "closed_book":
        return []
    return providers.PROVIDERS[arm](question, qid)


# How each approach is allowed to query in the one-shot step: its OWN native interface.
INTERFACE = {"metric_view": "sql", "genie_ontology": "sql", "genie_ontology_dmvm": "sql", "rag": "sql",
             "closed_book": "sql", "closure_sql": "closure", "ontobricks": "graph", "genie_one": "answer"}
INTERFACE_LABEL = {"sql": "SQL", "closure": "closure-tool call", "graph": "graph-runner call",
                   "answer": "its own answer (no follow-up query)"}


def _run_query(arm: str, query: dict) -> str:
    """Execute the one-shot query in the arm's native interface; returns the rendered result."""
    if query["kind"] == "sql":
        return _render_rows(run_readonly(query["sql"]))
    if query["interface"] == "closure":
        res = providers.run_closure_tool(query["tool"], query.get("args") or {})
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
    query, result, error, in_res, declined = None, None, None, None, ""
    if not sufficient and arm != "genie_one":
        tools = {"closure": providers.closure_tools(), "graph": GRAPH_TOOLS}.get(interface)
        query, declined = agent.write_query(q["question"], docs, interface, tools)
        if query and query.get("kind") == "sql" and not re.search(r"\bFROM\b", query["sql"], re.IGNORECASE):
            # SELECT 'a' AS x, 'b' AS y reads no table: it is the agent's answer typed as SQL, not a query. It is
            # recorded as no query, and the cell is judged on the context alone.
            declined = "The agent wrote a SELECT of constants (its answer as literals), which reads no table."
            query = None
        if query:
            try:
                result = _run_query(arm, query)
            except Exception as e:  # noqa: BLE001 -- a failed or rejected query is a miss, recorded verbatim
                error = f"{type(e).__name__}: {str(e)[:300]}"
        if result is not None:
            # The one query is judged as the agent would read it: the query (which table, which filters, which
            # segment) together with the rows it returned. The rows must carry the values; the query says what they are.
            shown = f"QUERY ({INTERFACE_LABEL[interface]}):\n{(query or {}).get('sql') or json.dumps(query)}\n\nRESULT:\n{result}"
            in_res = [agent.judge_fact(q["question"], f, shown, "query and its result") for f in q["expected_facts"]]
    # The agent has BOTH the context and its one query: a fact counts if either states it (the context can carry the
    # definition while the query supplies the number).
    query_correct = bool(in_res) and all(c["ok"] or r["ok"] for c, r in zip(in_ctx, in_res))
    tier = 1 if sufficient else (2 if query_correct else 3)
    result_outcome = _outcome(arm, docs, sufficient, query, error, in_ctx, in_res)
    facts = [{"fact": f, "in_context": in_ctx[k], "in_result": (in_res[k] if in_res else None)}
             for k, f in enumerate(q["expected_facts"])]
    what = ("no recorded Genie One answer" if arm == "genie_one" and not docs else
            "Genie One's answer states every gold fact" if arm == "genie_one" and sufficient else
            "Genie One's answer is missing or contradicts a gold fact" if arm == "genie_one" else
            "retrieved nothing" if not docs else
            "every gold fact is stated in what it retrieved (no query needed)" if sufficient else
            f"not every fact was in what it retrieved; the agent declined to write a query (NO_QUERY): {declined}"
            if not query else
            f"not every fact was in what it retrieved; the agent's {INTERFACE_LABEL[interface]} failed" if error else
            f"not every fact was in what it retrieved; the agent's {INTERFACE_LABEL[interface]} ran")
    outcome = {"tier": tier, "outcome": result_outcome, "what_happened": what, "interface": INTERFACE_LABEL[interface],
               "retrieved": providers.summarize(arm, docs),
               "facts": facts,
               "query": query, "query_result": (result or "")[:1500], "query_error": error}
    reason = agent.explain(q["question"], arm, outcome, ls=providers.LS)
    skipped = providers.genie_skipped(arm, q["qid"])
    return {"arm": arm, "qid": q["qid"], "tier": tier, "outcome": result_outcome, "declined_reason": declined or None,
            "sufficient": sufficient, "query_correct": query_correct,
            "interface": INTERFACE_LABEL[interface], "query": query,
            "sql": (query or {}).get("sql") or (json.dumps({k: query[k] for k in ("tool", "args")}) if query else None),
            "sql_error": error, "sql_result": (result or None) and result[:2500],
            "facts": facts, "reason": reason, "retrieved": outcome["retrieved"],
            "n_docs": len(docs), "skipped_search": bool(skipped),
            "facts_in_context": [x["ok"] for x in in_ctx], "facts_in_result": [x["ok"] for x in in_res] if in_res else None,
            "context": ctx[:6000]}


# The cell's outcome, one of: in_context, one_query (both answered: every gold fact stated by the context, or by the
# context and the one query together); incomplete (some gold facts stated, the rest missing, none contradicted);
# not_found (the query ran but states none of them); wrong (it contradicts a gold fact); query_failed; no_query (it
# retrieved something but the agent declined to write its one query); nothing (it retrieved nothing). Genie One is
# judged on its own answer. The tier (1/2/3) is unchanged; this only says which kind of miss.
OUTCOMES = ("in_context", "one_query", "incomplete", "not_found", "wrong", "query_failed", "no_query", "nothing")


def _outcome(arm, docs, sufficient, query, error, in_ctx, in_res) -> str:
    def judged(xs):
        if any(x.get("verdict") == "contradicted" for x in xs):
            return "wrong"
        return "incomplete" if any(x.get("ok") for x in xs) else "not_found"
    if arm == "genie_one":
        return "in_context" if sufficient else ("nothing" if not docs else judged(in_ctx))
    if sufficient:
        return "in_context"
    if not docs:
        return "nothing"
    if not query:
        return "no_query"
    if error or in_res is None:
        return "query_failed"
    best = [c if c["ok"] else r for c, r in zip(in_ctx, in_res)]  # per fact: the context's verdict if it states it
    return "one_query" if all(x["ok"] for x in best) else judged(best)


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
    ap.add_argument("--arms", default=",".join(ARMS), help="comma-separated subset of " + ",".join(ALL_ARMS))
    ap.add_argument("--out", default="ls_benchmark.json" if providers.LS else "benchmark_v2.json",
                    help="file name under docs/benchmark/ (set CARE_DEMO=life_sciences_clinical for the LS set)")
    ap.add_argument("--merge", action="store_true", help="replace only the (arm, question) rows run now in --out")
    ap.add_argument("--qids", default="", help="comma-separated question ids (default: the demo set in the CSV)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--repeats", type=int, default=1, help="runs per cell (test mode: 1); the majority tier is reported")
    ap.add_argument("--final", action="store_true", help="final demo testing: 3 runs per cell (overrides --repeats)")
    args = ap.parse_args()
    if args.final:
        args.repeats = 3
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

    wanted = args.qids.split(",") if args.qids else [q["qid"] for q in QUESTIONS]
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
                    "runs": [{"tier": r["tier"], "outcome": r.get("outcome"),
                              "sql": (r.get("sql") or "")[:1500], "sql_error": r.get("sql_error"),
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
    json.dump({"demo": providers.DEMO, "judge": JUDGE, "agent": agent.AGENT_MODEL, "scoring": "tiers-v2 (per-fact stated/missing/contradicted)", "repeats": args.repeats, "rows": rows}, open(out, "w"), indent=2, default=str)
    print(f"\nPer-cell detail -> {out}")
    if providers._rag_error:
        print(f"NOTE: RAG arm ran in degraded mode ({providers._rag_error}).")


if __name__ == "__main__":
    main()
