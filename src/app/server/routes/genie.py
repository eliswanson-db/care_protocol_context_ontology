"""The Genie hop, live. Fires a real Genie One call about the selected patient and returns the
grounded answer + the lineage of HOW it answered: generated SQL, cited metric views / Pages, and the
ADR-0018 ontology-engagement signal (did Genie consult the native ontology for THIS answer?).

Driven headless via `databricks genie ask --output json` (same front door as the capability-map benchmark,
src/benchmark/run_capability_map.py), so the answer reflects whatever Genie Ontology / Pages exist in THIS
workspace — sparse on ECT (arm=local/off), dense on DMVM (arm=on). The ontology_used flag is the ON/OFF tell.

This is a read path (it asks; it does not mutate), but it is an LLM call: latency is seconds, and the answer
is AI-generated and must be shown as such (verify before clinical use).
"""
import json
import os
import re
import subprocess
import time

from fastapi import APIRouter, HTTPException

from ..config import ARM, MEASUREMENT_YEAR, get_warehouse_id

router = APIRouter()


def _profile() -> str:
    return os.environ.get("DATABRICKS_PROFILE", "ECT")


@router.get("/patient/{patient_id}/genie")
def ask_genie(patient_id: str):
    short = patient_id[:8]
    question = (
        f"For measurement year {MEASUREMENT_YEAR}, is patient {patient_id} compliant with the HEDIS GSD "
        f"(Glycemic Status Assessment for Patients With Diabetes) measure, and why? "
        f"Use the governed GSD metric view and cite any ontology page you relied on."
    )
    cmd = ["databricks", "genie", "ask", "-s", f"app_{short}_{int(time.time())}",
           "--output", "json", "--profile", _profile(), "--warehouse-id", get_warehouse_id(), question]

    t0 = time.time()
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Genie One timed out (>180s).")
    except FileNotFoundError:
        raise HTTPException(500, "databricks CLI not found on this host.")
    latency = round(time.time() - t0, 1)

    if out.returncode != 0:
        raise HTTPException(502, f"Genie CLI error: {(out.stderr or out.stdout).strip()[:300]}")
    try:
        d = json.loads(out.stdout)
    except json.JSONDecodeError:
        raise HTTPException(502, f"Genie returned non-JSON: {out.stdout.strip()[:300]}")

    text = d.get("text", "") or ""
    generated_sql = None
    tool_names: list[str] = []
    ontology_used = False
    citations: list[dict] = []

    for tc in d.get("tool_calls", []):
        name = tc.get("name", "")
        if name:
            tool_names.append(name)
        if tc.get("sql") and not generated_sql:
            generated_sql = tc["sql"]
        args = str(tc.get("arguments") or "")
        # ADR-0018 ontology-engagement signals for THIS answer.
        if name == "search_knowledge_snippets":
            ontology_used = True
            citations.append({"kind": "snippet_search", "detail": args[:200]})
        if name == "get_asset_info" and "knowledge_page" in args:
            ontology_used = True
            citations.append({"kind": "knowledge_page", "detail": args[:200]})

    for m in sorted(set(re.findall(r"care_protocol\w*\.\w+\.\w+", text))):
        citations.append({"kind": "table", "detail": m})
    if "/discover/pages/" in text:
        ontology_used = True
        citations.append({"kind": "page", "detail": "Genie Ontology Page cited"})
    if "_metrics" in text:
        citations.append({"kind": "metric_view", "detail": "governed metric view cited"})

    return {
        "patient_id": patient_id,
        "question": question,
        "answer": text,
        "generated_sql": generated_sql,
        "tool_names": tool_names,
        "ontology_used": ontology_used,
        "citations": citations,
        "arm": ARM,
        "ran_as": f"the app's Databricks identity against the {ARM} workspace via Genie One",
        "latency_s": latency,
    }
