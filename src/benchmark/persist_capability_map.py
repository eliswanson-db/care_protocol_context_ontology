"""Persist the hand-verified capability matrix (docs/benchmark/capability_matrix.csv) into Unity Catalog.

The capability MAP -- not a leaderboard (BENCHMARK_CHARTER.md, ADR-0010) -- is the serious deliverable: per
class of hard clinical question, which context/retrieval approach reaches the hand-verified answer and HOW.
`run_capability_map.py` logs an as-of A1/M0 run to MLflow; the authoritative verdicts are hand-verified in
docs/benchmark/capability_map.md and mirrored as data in capability_matrix.csv. This task loads that CSV so a
governed AI/BI dashboard can read it (the roadmap gap: "no results table exists; benchmark logs to MLflow only").

Writes into ${catalog}.${schema}:
  benchmark_capability_matrix  -- wide: one row per question, one verdict column per arm (mirrors the CSV).
  benchmark_capability_tidy    -- long: one row per (question, arm) with verdict + numeric score, for charting.

Reproducible-by-code; re-runnable (overwrite). Run as a serverless job task (resources/jobs.yml) or locally.
"""
import argparse
import os

import pandas as pd
from pyspark.sql import SparkSession

# Verdict -> numeric score for heatmap coloring. The map stays a capability map: a "correct refusal" (the arm
# correctly reported the answer is undefined) is a SUCCESS, so it scores 1.0 alongside "reached". "diverged"
# (reasoned soundly but to a different number, for lack of the governed value set) is partial. "not_applicable"
# is null (the arm structurally does not apply to that question), distinct from "not_reached" (0.0, it applies
# and missed). This encoding is for shading only; the verdict label is authoritative.
SCORE = {
    "reached": 1.0,
    "correct_refusal": 1.0,
    "diverged": 0.5,
    "not_reached": 0.0,
    "not_applicable": None,
    "pending": None,   # verdict not yet hand-verified (e.g. a1_on awaiting DMVM snippet extraction) — null shade
}
# ADR-0018: A1 (Genie One) splits into two workspace arms over the ONE shared catalog, varying only the native
# ontology: a1_off = ECT (~200 snippets, sub-threshold → modeled context only = baseline); a1_on = DMVM (~1,100
# snippets, above the ~1,000 inferred-snippet threshold → inferred ontology active = treatment).
ARMS = {
    "m0_metric_view": "M0 — Metric views only",
    "closure_sql": "closure_sql — Governed closure/edge SQL",
    "a1_off": "A1-off — Genie One (ECT baseline, sub-threshold)",
    "a1_on": "A1-on — Genie One (DMVM, inferred ontology)",
}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", default=os.environ.get("CATALOG", "eli_test_classic_catalog"))
    p.add_argument("--schema", default=os.environ.get("SCHEMA", "care_protocol"))
    default_src = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
    p.add_argument("--src_dir", default=default_src, help="Dir holding capability_matrix.csv (workspace file path).")
    args = p.parse_args()

    spark = SparkSession.builder.getOrCreate()
    csv_path = os.path.join(args.src_dir, "capability_matrix.csv")
    wide = pd.read_csv(csv_path, dtype=str).fillna("")

    # --- wide table (mirror of the CSV / capability_map.md matrix) ---
    wfqn = f"{args.catalog}.{args.schema}.benchmark_capability_matrix"
    spark.createDataFrame(wide).write.mode("overwrite").option("overwriteSchema", True).saveAsTable(wfqn)
    spark.sql(f"COMMENT ON TABLE {wfqn} IS '{_q(_WIDE_DOC)}'")
    for col, doc in _WIDE_COLS.items():
        spark.sql(f"COMMENT ON COLUMN {wfqn}.{col} IS '{_q(doc)}'")

    # --- tidy/long table (one row per question x arm), for charting ---
    rows = []
    for _, r in wide.iterrows():
        for arm_col, arm_label in ARMS.items():
            verdict = (r[arm_col] or "").strip()
            if not verdict:
                continue
            rows.append({
                "class_num": int(r["class_num"]),
                "class_name": r["class_name"],
                "question_id": r["question_id"],
                "question": r["question"],
                "gold_25k": r["gold_25k"],
                "min_approach": r["min_approach"],
                "arm": arm_label,
                "arm_key": arm_col,
                "verdict": verdict,
                "score": SCORE.get(verdict),
                "reached": verdict in ("reached", "correct_refusal"),
            })
    tidy = pd.DataFrame(rows)
    tfqn = f"{args.catalog}.{args.schema}.benchmark_capability_tidy"
    spark.createDataFrame(tidy).write.mode("overwrite").option("overwriteSchema", True).saveAsTable(tfqn)
    spark.sql(f"COMMENT ON TABLE {tfqn} IS '{_q(_TIDY_DOC)}'")
    for col, doc in _TIDY_COLS.items():
        spark.sql(f"COMMENT ON COLUMN {tfqn}.{col} IS '{_q(doc)}'")

    print(f"Wrote {len(wide)} questions -> {wfqn}")
    print(f"Wrote {len(tidy)} (question x arm) rows -> {tfqn}")


def _q(s: str) -> str:
    return s.replace("'", "''")


_WIDE_DOC = (
    "Hand-verified capability matrix (ADR-0010, BENCHMARK_CHARTER.md): per hard clinical question, which "
    "context/retrieval approach reaches the pinned gold and how. One row per question; one verdict column per "
    "arm. This is a capability MAP, not a leaderboard. Source of truth: docs/benchmark/capability_map.md, "
    "mirrored from docs/benchmark/capability_matrix.csv. Synthetic 25k-patient data; HEDIS-aligned, not NCQA-certified."
)
_WIDE_COLS = {
    "class_num": "Question-class number (1-9), ordered from baked KPIs to graph-native inference.",
    "class_name": "Question class: the kind of reasoning the question demands (e.g. ICD-10 subsumption, LOINC multiaxial identity).",
    "question_id": "Stable question id, matching ground_truth.yaml / gold_queries.sql.",
    "question": "Short natural-language statement of the hard question.",
    "gold_25k": "Hand-verified gold answer at 25k patients (verify_gold.py), the reference every arm is scored against.",
    "min_approach": "Minimal context layer sufficient in principle: metric_view, closure_sql, document, or graph.",
    "m0_metric_view": "Verdict for the metric-views-only baseline: reached / not_reached / diverged / not_applicable / correct_refusal.",
    "closure_sql": "Verdict for governed closure/edge SQL (the answer key for classes 2-6).",
    "a1_off": "Verdict for Genie One on ECT (ADR-0018 baseline: ~200 workspace snippets, below the ~1,000 inferred-snippet threshold → modeled context only, no inferred ontology).",
    "a1_on": "Verdict for Genie One on DMVM (ADR-0018 treatment: ~1,100 snippets, above threshold → inferred ontology active). 'pending' until post-extraction hand-verification.",
    "note": "Hand-verified annotation: how the arm reached (or missed) the answer.",
}
_TIDY_DOC = (
    "Long/tidy form of benchmark_capability_matrix: one row per (question, arm) with the hand-verified verdict, "
    "a numeric score for heatmap shading, and a boolean reached flag. Drives the capability-map AI/BI dashboard. "
    "Capability map, not leaderboard (ADR-0010)."
)
_TIDY_COLS = {
    "class_num": "Question-class number (1-9).",
    "class_name": "Question class (the reasoning demanded).",
    "question_id": "Stable question id.",
    "question": "Short natural-language question.",
    "gold_25k": "Hand-verified gold answer at 25k patients.",
    "min_approach": "Minimal sufficient context layer.",
    "arm": "Display label of the retrieval arm.",
    "arm_key": "Arm key (m0_metric_view / closure_sql / a1_off / a1_on).",
    "verdict": "Hand-verified verdict: reached / not_reached / diverged / not_applicable / correct_refusal / pending.",
    "score": "Numeric shade for the heatmap: reached & correct_refusal=1.0, diverged=0.5, not_reached=0.0, not_applicable & pending=null.",
    "reached": "True when the arm reached the correct outcome (reached, or a correct refusal).",
}


if __name__ == "__main__":
    main()
