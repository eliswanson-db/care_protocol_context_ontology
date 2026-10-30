"""Benchmark a retrieval arm against a ground-truth question set; log to MLflow (ADR-0004).

Supports multiple arms, each logged as its own MLflow run in one experiment for side-by-side comparison:
  --arm A2  : Genie Agent (space) — LLM generates SQL, Conversation API.
  --arm A6  : Supervisor + custom MCP — a router picks a governed, deterministic tool (no LLM SQL).

Scores per question:
  - answer_correct : the expected value/string appears in the arm's answer text.
  - asset_grounded : A2 -> the generated SQL references the expected governed asset; A6 -> a governed tool
                     (not the Genie fallback) answered.
More arms (A1 Genie One, A4 Lakebase) plug in as additional --arm branches.
"""
import argparse
import json
import os
import sys
import time

import mlflow
from databricks.sdk import WorkspaceClient


def norm(s):
    return s.lower().replace(",", "").replace("%", "")


# ---------- A2: Genie Agent ----------
def run_a2(questions, w, space_id):
    rows = []
    for q in questions:
        t0 = time.time()
        text, sql = "", ""
        try:
            msg = w.genie.start_conversation_and_wait(space_id, q["question"])
            for a in (msg.attachments or []):
                if getattr(a, "text", None) and a.text and a.text.content:
                    text += " " + a.text.content
                if getattr(a, "query", None) and a.query and a.query.query:
                    sql += " " + a.query.query
        except Exception as e:  # noqa: BLE001
            text = f"ERROR: {e}"
        dt = round(time.time() - t0, 2)
        answer_ok = norm(q["expect_contains"]) in norm(text)
        asset_ok = (not q["expect_asset"]) or (q["expect_asset"].lower() in sql.lower())
        rows.append({"id": q["id"], "answer_correct": answer_ok, "asset_grounded": asset_ok,
                     "latency_s": dt, "answer": text[:300], "detail": sql[:200]})
    return rows


# ---------- A6: Supervisor + custom MCP ----------
def run_a6(questions, w, warehouse_id, catalog, repo_src):
    sys.path.insert(0, os.path.join(repo_src, "mcp"))
    from care_protocol_tools import make_tools
    from supervisor import answer as route_answer, summarize

    def query(sql):
        r = w.statement_execution.execute_statement(warehouse_id=warehouse_id, statement=sql, wait_timeout="30s")
        cols = [c.name for c in r.manifest.schema.columns] if r.manifest and r.manifest.schema else []
        data = (r.result.data_array if r.result and r.result.data_array else []) or []
        return [dict(zip(cols, row)) for row in data]

    tools = make_tools(catalog)
    rows = []
    for q in questions:
        t0 = time.time()
        try:
            ans = route_answer(q["question"], tools, query)
            text, tool = summarize(ans), ans["tool"]
        except Exception as e:  # noqa: BLE001
            text, tool = f"ERROR: {e}", "error"
        dt = round(time.time() - t0, 2)
        answer_ok = norm(q["expect_contains"]) in norm(text)
        asset_ok = tool not in ("genie_fallback", "error")
        rows.append({"id": q["id"], "answer_correct": answer_ok, "asset_grounded": asset_ok,
                     "latency_s": dt, "answer": text[:300], "detail": tool})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["A2", "A6"], default="A2")
    ap.add_argument("--questions", required=True)
    ap.add_argument("--experiment", required=True)
    ap.add_argument("--space_id", default="")        # A2
    ap.add_argument("--warehouse_id", default="")    # A6
    ap.add_argument("--catalog", default="eli_test_classic_catalog")  # A6
    ap.add_argument("--repo_src", default="")        # A6 imports (mcp)
    args = ap.parse_args()

    with open(args.questions) as f:
        questions = json.load(f)
    w = WorkspaceClient()

    names = {"A2": "A2_genie_agent", "A6": "A6_supervisor_mcp"}
    print(f"Running arm {args.arm} ({names[args.arm]}) over {len(questions)} questions...")
    if args.arm == "A2":
        rows = run_a2(questions, w, args.space_id)
    else:
        rows = run_a6(questions, w, args.warehouse_id, args.catalog, args.repo_src)

    n = len(questions)
    n_ans = sum(r["answer_correct"] for r in rows)
    n_grnd = sum(r["asset_grounded"] for r in rows)
    avg_lat = round(sum(r["latency_s"] for r in rows) / n, 2)
    for r in rows:
        print(f"  {r['id']}: answer={'OK' if r['answer_correct'] else 'X'} "
              f"grounded={'OK' if r['asset_grounded'] else 'X'} ({r['latency_s']}s) [{r['detail'][:40]}]")

    mlflow.set_experiment(args.experiment)
    with mlflow.start_run(run_name=names[args.arm]):
        mlflow.log_param("arm", args.arm)
        mlflow.log_param("approach", names[args.arm])
        mlflow.log_param("n_questions", n)
        mlflow.log_metric("answer_accuracy", round(n_ans / n, 3))
        mlflow.log_metric("asset_grounding", round(n_grnd / n, 3))
        mlflow.log_metric("avg_latency_s", avg_lat)
        cols = {k: [r.get(k) for r in rows] for k in rows[0].keys()}
        mlflow.log_table(data=cols, artifact_file="benchmark_results.json")

    print(f"\n{names[args.arm]}: answer_accuracy={n_ans}/{n}, asset_grounding={n_grnd}/{n}, "
          f"avg_latency={avg_lat}s. Logged to {args.experiment}.")


if __name__ == "__main__":
    main()
