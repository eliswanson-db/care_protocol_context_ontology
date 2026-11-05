"""Retrieval Arena — retrieval vs retrieval for one benchmark question.

GET /api/arena/{qid}/context returns, for the question's text:
  * ontology  — what Genie Ontology's MODELED layer holds for it (Pages + certified metric views), retrieved live
  * graph     — the Ontobricks typed subgraph for it, retrieved live from the latest published triplestore
  * scored    — what ONE fixed agent answered from each context alone, with the three judges' verdicts
                (docs/benchmark/retrieval_eval_arena.json, produced by the retrieval_eval harness from the SAME
                retrieval code in server/context_retrieval.py)
  * genie_one — the trail of what Genie One itself retrieved on the recorded end-to-end run (Pages it fetched,
                snippet searches, governed tables it queried). Genie's API exposes the trail, not the payload.

So the comparison is like-for-like: two knowledge layers, same question, same agent, same judges — separate
from Genie One's end-to-end answer (retrieval + SQL), which the Arena shows in its own section.
"""
import csv
import glob
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException

from ..config import (CATALOG, ONTOBRICKS_CATALOG, ONTOBRICKS_SCHEMA, SCHEMA, SCHEMA_SEMANTIC,
                      get_ontobricks_table)
from ..context_retrieval import graph_context, ontology_context
from ..warehouse import run_sql
from .benchmark import BENCH_DIR

router = APIRouter()


def _question(qid: str) -> str:
    with open(os.path.join(BENCH_DIR, "capability_matrix.csv"), newline="") as f:
        for r in csv.DictReader(f):
            if r["question_id"] == qid:
                return r["question"]
    raise HTTPException(404, f"Unknown benchmark question {qid!r}")


def _scored(qid: str) -> dict:
    path = os.path.join(BENCH_DIR, "retrieval_eval_arena.json")
    if not os.path.isfile(path):
        return {}
    d = json.load(open(path))
    out = {r["arm"]: {k: r.get(k) for k in ("correct", "grounded", "sufficient", "answer", "n_docs")}
           for r in d.get("rows", []) if r["qid"] == qid}
    out["_meta"] = {"agent": d.get("agent"), "judge": d.get("judge")}
    return out


def _genie_trail(qid: str) -> dict:
    """What Genie One retrieved on the recorded run (ECT, the matrix's authoritative A1 run)."""
    hits = sorted(glob.glob(os.path.join(BENCH_DIR, "a1_runs", "A1_off_*.json")))
    if not hits:
        return {}
    rec = next((r for r in json.load(open(hits[-1])) if r["id"] == qid), None)
    if not rec:
        return {}
    ans = rec.get("answer") or ""
    pages = sorted({t for t, _ in re.findall(r"\[([^\]]+)\]\([^)]*/discover/pages/([0-9a-f-]+)", ans)})
    snippet_q, tables = [], set()
    for kind, val in rec.get("assets") or []:
        if kind == "snippet_search":
            try:
                snippet_q.append(json.loads(val).get("query"))
            except Exception:  # noqa: BLE001 — truncated argument JSON
                snippet_q.append(val[:120])
        if kind == "sql":
            for m in re.findall(r"`?(care_protocol[a-z_]*)`?\.`?([a-z0-9_]+)`?", val):
                tables.add(f"{m[0]}.{m[1]}")
    tools = rec.get("tool_names") or []
    return {"snapshot": os.path.basename(hits[-1]), "pages_cited": pages, "snippet_searches": snippet_q,
            "tables_queried": sorted(x for x in tables if not any(y != x and y.startswith(x) for y in tables)),
            "sql_queries": tools.count("execute_sql_query"),
            "tool_calls": len(tools), "latency_s": rec.get("latency_s"),
            "used_ontobricks_mcp": any("ontobricks" in t for t in tools)}


@router.get("/arena/{qid}/context")
def arena_context(qid: str):
    q = _question(qid)
    graph = f"{ONTOBRICKS_CATALOG}.{ONTOBRICKS_SCHEMA}.{get_ontobricks_table()}_graph"

    def timed(fn, *a):
        t0 = time.time()
        try:
            return {"docs": fn(*a), "latency_s": round(time.time() - t0, 1)}
        except Exception as e:  # noqa: BLE001 — show the real failure in that column
            return {"docs": [], "error": f"{type(e).__name__}: {str(e)[:240]}", "latency_s": round(time.time() - t0, 1)}

    with ThreadPoolExecutor(max_workers=2) as ex:
        f_o = ex.submit(timed, ontology_context, q, run_sql, CATALOG, SCHEMA, SCHEMA_SEMANTIC)
        f_g = ex.submit(timed, graph_context, q, run_sql, graph)
        onto, gr = f_o.result(), f_g.result()
    scored = _scored(qid)
    return {"qid": qid, "question": q,
            "ontology": {**onto, "scored": scored.get("genie_ontology")},
            "graph": {**gr, "graph_table": graph, "scored": scored.get("ontobricks")},
            "closed_book": scored.get("closed_book"),
            "scored_meta": scored.get("_meta"),
            "genie_one": _genie_trail(qid)}
