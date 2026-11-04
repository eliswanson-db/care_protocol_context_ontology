"""One-off: score ONLY the ontobricks (graph) arm for the matrix questions not covered by the main
retrieval_eval run, so the whole Benchmark `graph` column is a measured live result (not hypothesis) and
internally consistent. Reuses the same controlled supervisor (agent.py) + is_correct judge as the main runner.

  PYTHONPATH=src DATABRICKS_CONFIG_PROFILE=ECT .venv/bin/python scripts/score_graph_remaining.py
"""
import json
import os

from mlflow.genai.judges import is_correct

from benchmark.retrieval_eval import agent, providers

JUDGE = os.environ.get("CARE_JUDGE_MODEL", "databricks:/databricks-claude-sonnet-5")

# The graph-claimed matrix questions NOT in the main run (gold from capability_matrix.csv gold_25k).
Q = [
    ("sub_retinopathy", "Count patients with any form of diabetic retinopathy.",
     ["393 patients have some form of diabetic retinopathy."]),
    ("lab_a1c_any_method", "How many patients have had an HbA1c test, counting every assay method?",
     ["9709 patients have had an HbA1c test across all assay methods."]),
    ("lab_egfr_codes", "Which LOINC codes count as an eGFR test here?",
     ["The LOINC codes that count as an eGFR test are 33914-3 and 98979-8."]),
    ("vintage_egfr_2026", "Under the 2026 KED eGFR definition, how many patients have a qualifying eGFR test?",
     ["Under the 2026 KED eGFR definition, 0 patients have a qualifying eGFR test (MDRD was dropped)."]),
    ("proto_statin_gap_safe", "Which diabetics 40-75 have a statin care gap AND no contraindication "
     "(not pregnant, no active hepatic disease)?",
     ["1609 diabetics aged 40-75 have a statin care gap and no contraindication."]),
    ("proto_albuminuria_aceiarb", "Patients with albuminuria (uACR >= 30) NOT on an ACE inhibitor or ARB, "
     "per protocol?",
     ["131 patients have albuminuria (uACR >= 30) and are not on an ACE inhibitor or ARB."]),
    ("op_drift_rootcause", "Why did CLINIC-08's protocol Step-3 adherence slip in Q3?",
     ["CLINIC-08's Step-3 adherence slipped in Q3 due to a PCP handoff (departure + locum), "
      "confounded with case-mix."]),
]


def _yes(fb) -> bool:
    v = getattr(fb, "value", fb)
    return str(v).strip().lower() in ("yes", "true", "1")


def main():
    out = []
    for qid, q, facts in Q:
        docs = providers.ontobricks(q, qid)
        ans = agent.answer(q, docs)
        correct = _yes(is_correct(request=q, response=ans, expected_facts=facts, model=JUDGE))
        out.append({"qid": qid, "correct": correct, "n_docs": len(docs), "answer": ans[:160]})
        print(f"  {qid:<26} correct={'Y' if correct else 'n'} docs={len(docs):>2}  {ans[:90]!r}")
    dst = os.path.join(os.path.dirname(__file__), "..", "docs", "benchmark", "retrieval_eval_graph_remaining.json")
    json.dump(out, open(os.path.normpath(dst), "w"), indent=2, default=str)
    print(f"\n-> {os.path.normpath(dst)}")


if __name__ == "__main__":
    main()
