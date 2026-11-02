"""Persist the A1 (Genie One) run evidence into Unity Catalog — the observational layer of the capability map.

ADR-0018 / ADR-0010. Distinct from the hand-verified capability matrix (persist_capability_map.py): that layer
holds the authoritative *verdicts* (Eli's, per the charter); THIS layer holds the machine-observed *evidence*
from driving Genie One headless over the ground-truth questions on each workspace arm:

  a1_off  -> ECT  (~200 workspace snippets, below the ~1,000 inferred-snippet threshold = baseline)
  a1_on   -> DMVM (~1,100 snippets, above threshold = native ontology active = treatment)

The single most important column is **ontology_used**: whether Genie One consulted the native ontology for that
answer (fired search_knowledge_snippets, fetched a knowledge_page, or cited a /discover/pages/ Page — captured by
run_capability_map.py). The A1-on vs A1-off split on that column is the directly-observable ADR-0018 signal
(no UI snippet-density guess needed).

Input: dated A1_detail.json snapshots produced by run_capability_map.py, committed under
docs/benchmark/a1_runs/ (Genie is non-deterministic, so each run is an as-of snapshot — commit it).

  python src/benchmark/run_capability_map.py --arm A1 --profile ECT  --out /tmp/capmap_ect
  python src/benchmark/run_capability_map.py --arm A1 --profile DMVM --out /tmp/capmap_dmvm
  cp /tmp/capmap_ect/A1_detail.json  docs/benchmark/a1_runs/A1_off_ect_<date>.json
  cp /tmp/capmap_dmvm/A1_detail.json docs/benchmark/a1_runs/A1_on_dmvm_<date>.json
  python src/benchmark/persist_a1_runs.py   # serverless job task or local

Writes ${catalog}.${schema}.benchmark_a1_runs (one row per arm x question). Re-runnable (overwrite).
"""
import argparse
import glob
import json
import os

import pandas as pd
from pyspark.sql import SparkSession

# Each committed snapshot file is named A1_<arm_key>_<workspace>_<date>.json; we also map arm_key -> workspace.
ARM_WORKSPACE = {"a1_off": "ECT", "a1_on": "DMVM"}
ARM_LABEL = {
    "a1_off": "A1-off — Genie One (ECT baseline, sub-threshold)",
    "a1_on": "A1-on — Genie One (DMVM, inferred ontology)",
}


def _arm_key_from_name(path: str) -> str:
    base = os.path.basename(path).lower()
    if "a1_on" in base or "dmvm" in base:
        return "a1_on"
    if "a1_off" in base or "ect" in base:
        return "a1_off"
    raise SystemExit(f"Cannot infer arm (a1_off/a1_on) from filename: {path}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", default=os.environ.get("CATALOG", "eli_test_classic_catalog"))
    p.add_argument("--schema", default=os.environ.get("SCHEMA", "care_protocol"))
    default_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                               "docs", "benchmark", "a1_runs") if "__file__" in globals() else "docs/benchmark/a1_runs"
    p.add_argument("--runs_dir", default=default_dir, help="Dir of committed A1_detail snapshots.")
    args = p.parse_args()

    files = sorted(glob.glob(os.path.join(args.runs_dir, "*.json")))
    if not files:
        raise SystemExit(f"No A1 run snapshots in {args.runs_dir} (copy A1_detail.json there first).")

    rows = []
    for fpath in files:
        arm_key = _arm_key_from_name(fpath)
        run_tag = os.path.splitext(os.path.basename(fpath))[0]
        for r in json.load(open(fpath)):
            assets = r.get("assets", []) or []
            tool_names = r.get("tool_names", []) or []
            ok = r.get("answer_ok")
            rows.append({
                "arm_key": arm_key,
                "arm": ARM_LABEL.get(arm_key, arm_key),
                "workspace": ARM_WORKSPACE.get(arm_key, "?"),
                "run_tag": run_tag,
                "question_id": r.get("id"),
                "class_name": r.get("cls"),
                "question": r.get("question"),
                "gold": str(r.get("gold")),
                "ontology_used": bool(r.get("ontology_used")),
                "first_pass_reached": (None if ok is None else bool(ok)),
                "matched": ", ".join(r.get("matched", []) or []),
                "n_tool_calls": len(tool_names),
                "tool_names": ", ".join(tool_names),
                "latency_s": float(r.get("latency_s") or 0.0),
                "cited_page": any(a[0] in ("page", "knowledge_page") for a in assets),
                "cited_metric_view": any(a[0] == "metric_view" for a in assets),
                "snippet_search": any(a[0] == "snippet_search" for a in assets),
                "answer": (r.get("answer") or "")[:1000],
            })

    df = pd.DataFrame(rows)
    spark = SparkSession.builder.getOrCreate()
    fqn = f"{args.catalog}.{args.schema}.benchmark_a1_runs"
    spark.createDataFrame(df).write.mode("overwrite").option("overwriteSchema", True).saveAsTable(fqn)
    spark.sql(f"COMMENT ON TABLE {fqn} IS '{_q(_DOC)}'")
    for col, doc in _COLS.items():
        spark.sql(f"COMMENT ON COLUMN {fqn}.{col} IS '{_q(doc)}'")

    # headline contrast to stdout
    g = df.groupby("arm_key").agg(
        questions=("question_id", "count"),
        ontology=("ontology_used", "sum"),
        first_pass=("first_pass_reached", lambda s: int(sum(x is True for x in s))),
    )
    print(f"Wrote {len(df)} rows -> {fqn}")
    for arm_key, r in g.iterrows():
        print(f"  {arm_key}: ontology_used {int(r['ontology'])}/{int(r['questions'])} | "
              f"first-pass reached {int(r['first_pass'])}/{int(r['questions'])}")


def _q(s: str) -> str:
    return s.replace("'", "''")


_DOC = (
    "A1 (Genie One) run evidence — the OBSERVATIONAL layer of the capability map (ADR-0018). One row per "
    "(arm x ground-truth question) from driving Genie One headless on each workspace: a1_off = ECT baseline "
    "(sub inferred-snippet threshold), a1_on = DMVM (native ontology active). ontology_used is the directly-"
    "observed ON/OFF signal. Machine-observed and non-deterministic (as-of snapshot); the hand-verified "
    "benchmark_capability_matrix holds the authoritative verdicts. Synthetic 25k data; HEDIS-aligned, not NCQA-certified."
)
_COLS = {
    "arm_key": "a1_off (ECT baseline) or a1_on (DMVM, inferred ontology).",
    "arm": "Display label of the A1 arm.",
    "workspace": "Workspace the run executed on (ECT / DMVM) — same shared catalog, differing native-ontology layer.",
    "run_tag": "Snapshot filename (dated) this row came from; Genie is non-deterministic so runs are as-of snapshots.",
    "question_id": "Ground-truth question id (ground_truth.yaml).",
    "class_name": "Question class (the reasoning demanded).",
    "question": "Natural-language question put to Genie One.",
    "gold": "Pinned hand-verified gold answer the first-pass auto-scorer checks against.",
    "ontology_used": "TRUE if Genie One consulted the native ontology for this answer (search_knowledge_snippets, a knowledge_page fetch, or a cited /discover/pages/ Page) — the ADR-0018 ON/OFF signal.",
    "first_pass_reached": "Auto-scorer first pass: did the gold token appear in the answer? NULL = needs manual verdict. The hand-verified matrix is authoritative.",
    "matched": "Gold surface-forms found in the answer (raw / percent / thousands-comma).",
    "n_tool_calls": "Number of Genie One tool calls for this answer.",
    "tool_names": "Ordered Genie One tool calls (e.g. search_knowledge_snippets, search_assets, get_asset_info, execute_sql_query).",
    "latency_s": "Wall-clock seconds for the Genie One answer.",
    "cited_page": "TRUE if the answer cited / fetched a Discover Page (modeled ontology).",
    "cited_metric_view": "TRUE if the answer cited a governed metric view.",
    "snippet_search": "TRUE if Genie One fired search_knowledge_snippets (inferred-snippet retrieval).",
    "answer": "First 1000 chars of Genie One's answer text (evidence for hand verdict).",
}


if __name__ == "__main__":
    main()
