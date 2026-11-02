"""Benchmark Scorecard API — makes the capability map visible (BENCHMARK_CHARTER.md, ADR-0010/0018).

Serves two things from the committed, hand-verified artifacts (the charter says the hand-verified matrix is
authoritative — so we read it directly, no warehouse round-trip):

  * capability_map  — docs/benchmark/capability_matrix.csv: question x arm (M0 / closure_sql / a1_off / a1_on)
    with a verdict per cell (reached / not_reached / diverged / not_applicable / correct_refusal / pending).
    This is the "when does each layer earn its place" deliverable.
  * a1_runs         — the dated A1-off (ECT) vs A1-on (DMVM) snapshots: the ADR-0018 observational layer
    (ontology-engagement signal per answer). Honest caveat travels with it: identical accuracy on covered
    questions; a fair ON/OFF test needs inferred-ontology-only questions (not yet in the set).
"""
import csv
import glob
import json
import os

from fastapi import APIRouter, HTTPException

router = APIRouter()

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
BENCH_DIR = os.environ.get("CARE_BENCHMARK_DIR", os.path.join(_REPO, "docs", "benchmark"))

ARMS = [
    {"id": "m0_metric_view", "label": "M0 · metric view", "col": "m0_metric_view"},
    {"id": "closure_sql", "label": "Closure SQL", "col": "closure_sql"},
    {"id": "a1_off", "label": "A1 off (ECT)", "col": "a1_off"},
    {"id": "a1_on", "label": "A1 on (DMVM)", "col": "a1_on"},
]
_REACHED = {"reached", "correct_refusal"}  # a correct refusal is a correct outcome


@router.get("/benchmark/capability_map")
def capability_map():
    path = os.path.join(BENCH_DIR, "capability_matrix.csv")
    if not os.path.isfile(path):
        raise HTTPException(404, f"capability_matrix.csv not found at {path}")
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))

    classes: list[dict] = []
    for r in rows:
        cn = r["class_num"]
        if not classes or classes[-1]["class_num"] != cn:
            classes.append({"class_num": cn, "class_name": r["class_name"], "questions": []})
        classes[-1]["questions"].append({
            "id": r["question_id"], "question": r["question"], "gold": r["gold_25k"],
            "min_approach": r["min_approach"], "note": r["note"],
            "verdicts": {a["id"]: r[a["col"]] for a in ARMS},
        })

    rollup = []
    for a in ARMS:
        vals = [r[a["col"]] for r in rows]
        applicable = [v for v in vals if v not in ("not_applicable", "pending")]
        rollup.append({
            "arm": a["id"], "label": a["label"],
            "reached": sum(v in _REACHED for v in vals),
            "diverged": sum(v == "diverged" for v in vals),
            "not_reached": sum(v == "not_reached" for v in vals),
            "not_applicable": sum(v == "not_applicable" for v in vals),
            "pending": sum(v == "pending" for v in vals),
            "applicable": len(applicable),
            "total": len(vals),
        })
    return {"arms": ARMS, "classes": classes, "rollup": rollup}


def _latest(pattern: str) -> str | None:
    hits = sorted(glob.glob(os.path.join(BENCH_DIR, "a1_runs", pattern)))
    return hits[-1] if hits else None


def _signals(path: str | None) -> dict | None:
    if not path:
        return None
    rows = json.load(open(path))
    return {
        "snapshot": os.path.basename(path),
        "n": len(rows),
        "reached_auto": sum(r.get("answer_ok") is True for r in rows),
        "snippet_search_fired": sum("search_knowledge_snippets" in (r.get("tool_names") or []) for r in rows),
        "ontology_used": sum(bool(r.get("ontology_used")) for r in rows),
        "by_id": {r["id"]: {
            "answer_ok": r.get("answer_ok"),
            "ontology_used": bool(r.get("ontology_used")),
            "tool_names": r.get("tool_names") or [],
            "latency_s": r.get("latency_s"),
            "answer": (r.get("answer") or "")[:600],
        } for r in rows},
    }


@router.get("/benchmark/a1_runs")
def a1_runs():
    off = _signals(_latest("A1_off_*.json"))
    on = _signals(_latest("A1_on_*.json"))
    return {
        "off": off,
        "on": on,
        "caveat": (
            "Accuracy is identical on these questions: the care_protocol domain is fully modeled (governed "
            "metric views + curated Pages exist on BOTH arms), so Genie One reaches the answers with or without "
            "the high-density inferred ontology. The inferred layer adds candidate breadth, not answer "
            "correctness, on covered questions. A fair ON/OFF test needs inferred-ontology-only questions "
            "(cross-space / outside care_protocol) — a benchmark scope extension, not yet in the set."
        ),
    }
