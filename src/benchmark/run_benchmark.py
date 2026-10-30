"""Benchmark the Care Protocol Genie Agent (A2) against a ground-truth question set; log to MLflow.

ADR-0004: this harness evaluates the Genie AGENT (A2), not Genie One. For each question it starts a Genie
conversation, reads the agent's answer + generated SQL, and scores two things:
  - answer_correct: the expected value/string appears in the agent's text answer
  - asset_grounded: the agent's SQL references the expected governed table/metric view
Results (accuracy, grounding, latency, per-question detail) are logged to an MLflow run tagged with the
approach, so additional arms (A1/A4/A6) can be added as separate runs in the same experiment and compared.

Serverless task. Reads src/benchmark/benchmark_questions.json. See resources/jobs.yml (benchmark).
"""
import argparse
import json
import os
import time

import mlflow
from databricks.sdk import WorkspaceClient


def answer_and_sql(msg):
    text, sql = [], []
    for a in (msg.attachments or []):
        if getattr(a, "text", None) and a.text and a.text.content:
            text.append(a.text.content)
        if getattr(a, "query", None) and a.query and a.query.query:
            sql.append(a.query.query)
    return " ".join(text), " ".join(sql)


def norm(s):
    return s.lower().replace(",", "").replace("%", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--space_id", required=True)
    ap.add_argument("--questions", required=True, help="Path to benchmark_questions.json (workspace file).")
    ap.add_argument("--experiment", required=True, help="MLflow experiment path.")
    ap.add_argument("--approach", default="A2_genie_agent")
    args = ap.parse_args()

    with open(args.questions) as f:
        questions = json.load(f)

    w = WorkspaceClient()
    mlflow.set_experiment(args.experiment)
    rows, latencies, n_answer, n_ground = [], [], 0, 0

    with mlflow.start_run(run_name=args.approach):
        mlflow.log_param("approach", args.approach)
        mlflow.log_param("space_id", args.space_id)
        mlflow.log_param("n_questions", len(questions))

        for q in questions:
            t0 = time.time()
            try:
                msg = w.genie.start_conversation_and_wait(args.space_id, q["question"])
                answer, sql = answer_and_sql(msg)
            except Exception as e:  # noqa: BLE001
                answer, sql = f"ERROR: {e}", ""
            dt = round(time.time() - t0, 2)
            latencies.append(dt)

            answer_ok = norm(q["expect_contains"]) in norm(answer)
            asset_ok = (not q["expect_asset"]) or (q["expect_asset"].lower() in sql.lower())
            n_answer += int(answer_ok)
            n_ground += int(asset_ok)
            rows.append({"id": q["id"], "question": q["question"], "expect": q["expect_contains"],
                         "answer_correct": answer_ok, "asset_grounded": asset_ok, "latency_s": dt,
                         "answer": answer[:300], "sql": sql[:300]})
            print(f"  {q['id']}: answer={'OK' if answer_ok else 'X'} grounded={'OK' if asset_ok else 'X'} ({dt}s)")

        n = len(questions)
        mlflow.log_metric("answer_accuracy", round(n_answer / n, 3))
        mlflow.log_metric("asset_grounding", round(n_ground / n, 3))
        mlflow.log_metric("avg_latency_s", round(sum(latencies) / n, 2))
        # log_table wants a DataFrame or dict-of-columns, not a list of dicts.
        cols = {k: [r.get(k) for r in rows] for k in rows[0].keys()}
        mlflow.log_table(data=cols, artifact_file="benchmark_results.json")

    print(f"\n{args.approach}: answer_accuracy={n_answer}/{n}, asset_grounding={n_ground}/{n}, "
          f"avg_latency={round(sum(latencies) / n, 2)}s. Logged to MLflow experiment {args.experiment}.")


if __name__ == "__main__":
    main()
