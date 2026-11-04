"""Retrieval-science arm runner (ADR-0020). Holds ONE fixed agent (agent.py) constant and varies the injected
retrieval approach (providers.py) one component at a time, with closed_book as the floor. Each (approach x
question) cell is scored with MLflow GenAI judges:

  correctness  -- is_correct(expected_facts)            : did this approach's context let the agent answer?
  groundedness -- meets_guidelines(answer <= documents)  : was the answer actually built from the retrieved context?
  sufficiency  -- meets_guidelines(documents => facts)   : did retrieval even surface enough to answer?

NECESSITY falls out as correctness LIFT over closed_book. The output is the capability matrix -- which
retrieval approach is sufficient / adds value / necessary per question class -- not a single accuracy number.

Smoke set (3 questions chosen to cross over): a KPI (metric view wins), an ICD-subsumption count (closure
wins), a protocol definition (RAG wins / or closed_book already knows -- an honest null result). Scale to the
full ground_truth.yaml once the mechanic is proven.

Usage:
  DATABRICKS_CONFIG_PROFILE=TEST_SPN .venv/bin/python -m benchmark.retrieval_eval.run_retrieval_eval
  (run from src/, or: PYTHONPATH=src .venv/bin/python -m benchmark.retrieval_eval.run_retrieval_eval)
"""
from __future__ import annotations

import json
import os
import time

import mlflow
from mlflow.genai.judges import is_correct, meets_guidelines

from . import agent, providers

JUDGE = os.environ.get("CARE_JUDGE_MODEL", "databricks:/databricks-claude-sonnet-5")
EXPERIMENT = os.environ.get("CARE_EVAL_EXPERIMENT", "/Shared/care_protocol_retrieval_eval")

# The scored set. Mirrors docs/benchmark/capability_matrix.csv; expected_facts are the hand-verified gold (25k).
# Chosen to exercise every arm's lift AND its blind spot -- in particular the graph-native classes (8) where the
# graph is the only arm that should reach, and the aggregate-COUNT classes (2/4/6) where a triple neighbourhood
# legitimately should NOT (it carries membership + typed edges, but doesn't aggregate -- that's closure's job).
QUESTIONS = [
    {
        "qid": "kpi_gsd_rate",
        "cls": "1_simple_kpi",
        "question": "What is the overall GSD compliance rate?",
        "expected_facts": ["The overall GSD compliance rate is approximately 80.7 percent (0.8071)."],
        "wins": "metric_view",
    },
    {
        "qid": "sub_kidney",
        "cls": "2_icd_subsumption",
        "question": "How many patients have diabetes WITH kidney complications?",
        "expected_facts": ["1881 distinct patients have diabetes with a kidney complication."],
        "wins": "closure_sql",
    },
    {
        "qid": "med_on_statin",
        "cls": "4_rxnorm_subsumption",
        "question": "How many diabetic patients are on any statin?",
        "expected_facts": ["1651 diabetic patients are on a statin (any member of the statin drug class)."],
        "wins": "closure_sql",
    },
    {
        "qid": "med_is_statin",
        "cls": "4_rxnorm_subsumption",
        "question": "Is a patient prescribed 'Simvastatin 20 MG Oral Tablet' on a statin?",
        "expected_facts": ["Yes -- simvastatin belongs to the statin drug class, so the patient is on a statin."],
        "wins": "closure_sql",
    },
    {
        "qid": "proto_cardiorenal",
        "cls": "6_protocol_multihop",
        "question": ("Identify cardiorenal patients (diabetes AND chronic kidney disease AND heart failure) and "
                     "whether each is on a statin plus an ACE/ARB plus an SGLT2."),
        "expected_facts": ["There are 10 cardiorenal patients (diabetes AND chronic kidney disease AND heart failure)."],
        "wins": "closure_sql",
    },
    {
        "qid": "def_controlled_bp",
        "cls": "7_definition_provenance",
        "question": "What does 'controlled' blood pressure mean for the BPD measure, and where is it defined?",
        # The substantive gold is the THRESHOLD; provenance ("where defined") is captured by the
        # sufficiency/groundedness judges, not gated as a correctness fact.
        "expected_facts": [
            "Controlled blood pressure for the BPD measure means systolic < 140 mmHg AND diastolic < 90 mmHg.",
        ],
        "wins": "rag",
    },
    {
        "qid": "def_metformin_egfr",
        "cls": "7_definition_provenance",
        "question": "Below what eGFR is metformin contraindicated, and where is that stated?",
        "expected_facts": ["Metformin (a biguanide) is contraindicated when eGFR is below 30 (eGFR < 30)."],
        "wins": "graph",
    },
    {
        "qid": "infer_rationale_path",
        "cls": "8_graph_native",
        "question": ("Explain the clinical rationale connecting a diabetes diagnosis to statin therapy -- "
                     "show the connecting path."),
        "expected_facts": [
            "A diabetes diagnosis makes a patient eligible for the SPD statin-use measure, and the statin drug "
            "class is recommended for SPD -- that recommendation path connects diabetes to statin therapy.",
        ],
        "wins": "graph",
    },
    {
        "qid": "infer_defined_class",
        "cls": "8_graph_native",
        "question": ("Which patients qualify as 'high cardiorenal risk' as DEFINED by the protocol ontology "
                     "(diabetes AND CKD AND on a drug class flagged for review)?"),
        # Gold is a REFUSAL: no such defined class exists in clinicaldomain, so the correct answer is to say so.
        "expected_facts": [
            "The protocol ontology does not define a 'high cardiorenal risk' class, so the correct response is "
            "that this class is undefined and no patient list can be produced for it.",
        ],
        "wins": "graph",
    },
]

ARMS = ["closed_book", "metric_view", "closure_sql", "rag", "ontobricks"]


def _yes(feedback) -> bool:
    v = getattr(feedback, "value", feedback)
    return str(v).strip().lower() in ("yes", "true", "1")


def retrieve(arm: str, question: str, qid: str) -> list[dict]:
    if arm == "closed_book":
        return []
    return providers.PROVIDERS[arm](question, qid)


@mlflow.trace(name="cell")
def run_cell(arm: str, q: dict) -> dict:
    """One (arm x question) cell: retrieve with this arm, answer, score with the three judges."""
    mlflow.update_current_trace(tags={"arm": arm, "qid": q["qid"], "cls": q["cls"]})
    docs = retrieve(arm, q["question"], q["qid"])
    ctx = "\n\n".join(d.get("page_content", "") for d in docs) or "(no context retrieved)"
    ans = agent.answer(q["question"], docs)

    correct = _yes(is_correct(request=q["question"], response=ans,
                              expected_facts=q["expected_facts"], model=JUDGE))
    grounded = None
    if docs:  # grounding is only meaningful when something was retrieved
        grounded = _yes(meets_guidelines(
            name="groundedness",
            guidelines=("Every factual claim in the response is directly supported by the retrieved_documents. "
                        "Answer 'yes' only if nothing in the response goes beyond those documents."),
            context={"response": ans, "retrieved_documents": ctx}, model=JUDGE))
    sufficient = _yes(meets_guidelines(
        name="sufficiency",
        guidelines=("The retrieved_documents contain enough information to fully support ALL of these required "
                    "facts: " + " | ".join(q["expected_facts"]) + ". Answer 'no' if documents are empty."),
        context={"retrieved_documents": ctx}, model=JUDGE))

    return {"arm": arm, "qid": q["qid"], "correct": correct, "grounded": grounded,
            "sufficient": sufficient, "answer": ans[:300], "n_docs": len(docs)}


def main():
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

    rows = []
    for q in QUESTIONS:
        for arm in ARMS:
            t0 = time.time()
            try:
                r = run_cell(arm, q)
            except Exception as e:  # noqa: BLE001
                r = {"arm": arm, "qid": q["qid"], "correct": False, "grounded": None,
                     "sufficient": False, "answer": f"ERROR: {type(e).__name__}: {str(e)[:160]}", "n_docs": 0}
            r["latency_s"] = round(time.time() - t0, 1)
            rows.append(r)
            g = {True: "Y", False: "n", None: "-"}
            print(f"  {q['qid']:<18} {arm:<12} correct={g[r['correct']]} "
                  f"grounded={g[r['grounded']]} sufficient={g[r['sufficient']]} "
                  f"docs={r['n_docs']} ({r['latency_s']}s)  {r['answer'][:70]!r}")

    # --- capability matrix + lift ---------------------------------------------------------------------------
    by = {(r["arm"], r["qid"]): r for r in rows}
    mark = {True: "✓", False: "·", None: "-"}
    print("\n=== Capability matrix (correctness) ===")
    hdr = "question".ljust(20) + "".join(a.ljust(13) for a in ARMS)
    print(hdr)
    for q in QUESTIONS:
        line = q["qid"].ljust(20)
        for arm in ARMS:
            c = by[(arm, q["qid"])]["correct"]
            line += mark[c].ljust(13)
        print(line + f"  (expected winner: {q['wins']})")

    print("\n=== Correctness LIFT over closed_book (necessity signal) ===")
    for q in QUESTIONS:
        base = by[("closed_book", q["qid"])]["correct"]
        gains = [arm for arm in ARMS if arm != "closed_book"
                 and by[(arm, q["qid"])]["correct"] and not base]
        note = "closed_book already answered (retrieval not necessary)" if base else \
               (f"necessary: {', '.join(gains)}" if gains else "no arm answered")
        print(f"  {q['qid']:<20} closed_book={'✓' if base else '·'}  -> {note}")

    out = os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "benchmark",
                       "retrieval_eval.json")
    out = os.path.normpath(out)
    json.dump({"judge": JUDGE, "agent": agent.AGENT_MODEL, "rows": rows}, open(out, "w"), indent=2, default=str)
    print(f"\nPer-cell detail -> {out}")
    if providers._rag_error:
        print(f"NOTE: RAG arm ran in degraded mode ({providers._rag_error}).")


if __name__ == "__main__":
    main()
