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

# Benchmark data: a vendored copy ships inside the app (deploy-safe — the whole repo isn't synced), with the
# repo's docs/benchmark as the local-dev fallback. Override with CARE_BENCHMARK_DIR.
_BUNDLED = os.path.join(os.path.dirname(__file__), "..", "benchmark_data")
_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
BENCH_DIR = os.environ.get("CARE_BENCHMARK_DIR") or (
    os.path.abspath(_BUNDLED) if os.path.isdir(_BUNDLED) else os.path.join(_REPO, "docs", "benchmark"))

# The five retrieval approaches benchmarked head-to-head, one consistent rubric per cell. metric_view /
# closure / genie_ontology are hand-verified (genie = the authoritative A1-off run; the ON/OFF experiment is
# the separate observational section). rag / graph are the designed-capability verdicts from the ground-truth
# hypotheses (ground_truth.yaml), carried into the matrix so every column uses the same question set + rubric.
# The five retrieval approaches, scored on ONE basis from the same retrieved context (retrieval_eval harness,
# docs/benchmark/retrieval_eval_arena.json): tier 1 = the answer is in the context; tier 2 = the context gives what's
# needed for ONE SQL query that returns the answer (the query is run and its result judged); tier 3 = neither.
# Genie One end-to-end (retrieval + its own SQL) is a different thing — kept as a separate, hand-verified column.
ARMS = [
    {"id": "metric_view", "label": "Metric View", "eval_arm": "metric_view", "kind": "retrieval"},
    {"id": "closure", "label": "Closure / SQL", "eval_arm": "closure_sql", "kind": "retrieval"},
    {"id": "genie_ontology", "label": "Genie Ontology", "eval_arm": "genie_ontology", "kind": "retrieval"},
    {"id": "rag", "label": "RAG", "eval_arm": "rag", "kind": "retrieval"},
    {"id": "graph", "label": "Ontobricks graph", "eval_arm": "ontobricks", "kind": "retrieval"},
    {"id": "genie_one", "label": "Genie One (end-to-end)", "csv_col": "genie_ontology", "kind": "end_to_end"},
]
_REACHED = {"reached", "correct_refusal"}  # a correct refusal is a correct outcome


def _eval_rows() -> dict:
    path = os.path.join(BENCH_DIR, "retrieval_eval_arena.json")
    if not os.path.isfile(path):
        return {}
    d = json.load(open(path))
    return {"meta": {"judge": d.get("judge"), "agent": d.get("agent"), "repeats": d.get("repeats")},
            "by": {(r["arm"], r["qid"]): r for r in d.get("rows", [])}}


@router.get("/benchmark/capability_map")
def capability_map():
    path = os.path.join(BENCH_DIR, "capability_matrix.csv")
    if not os.path.isfile(path):
        raise HTTPException(404, f"capability_matrix.csv not found at {path}")
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    ev = _eval_rows()
    by = ev.get("by", {})

    def verdict(a, r):
        if a["kind"] == "end_to_end":
            return r[a["csv_col"]]
        e = by.get((a["eval_arm"], r["question_id"]))
        if not e or e.get("tier") is None:
            return "pending"
        if e["tier"] == 3 and e.get("skipped_search"):
            return "skipped"
        if e["tier"] == 3 and not e.get("n_docs"):
            return "no_retrieval"
        return f"tier{e['tier']}"

    def evidence(a, r):
        e = by.get((a.get("eval_arm"), r["question_id"])) or {}
        out = {"context": (e.get("context") or "")[:600], "sql": e.get("sql"), "tier_runs": e.get("tier_runs"),
               "stable": e.get("stable")}
        return out

    classes: list[dict] = []
    vmap: dict[str, dict] = {}
    for r in rows:
        cn = r["class_num"]
        if not classes or classes[-1]["class_num"] != cn:
            classes.append({"class_num": cn, "class_name": r["class_name"], "questions": []})
        v = {a["id"]: verdict(a, r) for a in ARMS}
        vmap[r["question_id"]] = v
        classes[-1]["questions"].append({
            "id": r["question_id"], "question": r["question"], "gold": r["gold_25k"],
            "min_approach": r["min_approach"], "note": "", "verdicts": v,
            "evidence": {a["id"]: evidence(a, r) for a in ARMS if a["kind"] == "retrieval"},
        })

    rollup = []
    for a in ARMS:
        vals = [vmap[r["question_id"]][a["id"]] for r in rows]
        applicable = [v for v in vals if v not in ("not_applicable", "pending")]
        rollup.append({
            "arm": a["id"], "label": a["label"], "kind": a["kind"],
            "tier1": sum(v == "tier1" for v in vals), "tier2": sum(v == "tier2" for v in vals),
            "tier3": sum(v in ("tier3", "no_retrieval", "skipped") for v in vals),
            "skipped": sum(v == "skipped" for v in vals),
            "unstable": sum(1 for r in rows if a["kind"] == "retrieval"
                            and not (by.get((a["eval_arm"], r["question_id"])) or {}).get("stable", True)),
            "reached": sum(v in _REACHED for v in vals),
            "diverged": sum(v == "diverged" for v in vals),
            "not_reached": sum(v == "not_reached" for v in vals),
            "no_retrieval": sum(v == "no_retrieval" for v in vals),
            "not_applicable": sum(v == "not_applicable" for v in vals),
            "pending": sum(v == "pending" for v in vals),
            "applicable": len(applicable),
            "total": len(vals),
        })
    floor = [by.get(("closed_book", r["question_id"])) for r in rows]
    floor_rollup = {"tier1": sum(1 for f in floor if f and f.get("tier") == 1),
                    "tier2": sum(1 for f in floor if f and f.get("tier") == 2), "total": len(rows)}
    return {"arms": ARMS, "classes": classes, "rollup": rollup, "a1_on_source": None,
            "scored_by": ev.get("meta"), "floor": floor_rollup}


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


def _snippet_evidence() -> dict:
    """Observed Genie Ontology retrieval per workspace (scripts/record_genie_ontology.py)."""
    path = os.path.join(BENCH_DIR, "genie_ontology_retrieval.json")
    if not os.path.isfile(path):
        return {}
    d = json.load(open(path))
    out = {"recorded_at": d.get("recorded_at")}
    for ws, v in d.get("workspaces", {}).items():
        qs = v.get("questions", {}).values()
        snips = [x for q in qs for x in q.get("snippets") or []]
        out[ws] = {"identity": v.get("identity"), "questions": len(v.get("questions", {})),
                   "searched": sum(1 for q in qs if q.get("queries")),
                   "snippets": len(snips), "on_topic": sum(1 for x in snips if x.get("on_topic")),
                   "pages": sum(len(q.get("pages") or []) for q in qs)}
    return out


@router.get("/benchmark/a1_runs")
def a1_runs():
    off = _signals(_latest("A1_off_*.json"))
    on = _signals(_latest("A1_on_*.json"))
    ev = _snippet_evidence()
    return {
        "off": off,
        "on": on,
        "snippet_evidence": ev,
        "caveat": (
            "Observed 2026-11-04: the inferred-snippet layer fires on BOTH workspaces — it is not an on/off switch. "
            "Run as the same user over the 10 questions, ECT's snippets were almost all about this demo (mined from its "
            "Genie spaces and metric views) while DMVM's came from other projects in the shared metastore. Retrieval "
            "is also identity-scoped (the app's service principal sees fewer snippets). Answer accuracy is close on "
            "both workspaces because Genie One mostly grounds in the shared Pages, certified metric views and SQL; "
            "the snippets carry definitions, not computed values. Still observational, not causal (ADR-0018)."
        ),
        "caveat_old": (
            "Intended contrast, not yet a proven one. A1-on (DMVM) is the INTENDED ontology-ON arm: we are "
            "building the per-workspace surfaces (notebooks, dashboards, Genie agents, metric views, comments, "
            "query history) that mint native inferred snippets, assuming that layer will surface. But a direct "
            "probe shows Genie One on DMVM grounding in the same curated Pages + metric views that BOTH arms "
            "share — we have not yet observed the inferred ('learned') layer doing work. Whether it ever "
            "retrieves inferred snippets — or only ever uses the shared modeled layer — is an open question this "
            "demo is designed to answer. Lead with the layer map above; treat ON-vs-OFF as a live experiment, "
            "and read a1_on verdicts as pending that build + extraction + an inferred-only question."
        ),
    }
