"""The Genie hop, live — dual-mode so it works both locally and when deployed as a Databricks App.

Local (CLI available): drive **Genie One** (A1, the workspace front door) headless via `databricks genie ask`,
which exposes the ADR-0018 ontology-engagement signal (search_knowledge_snippets / cited Pages).

Deployed (no CLI in the Apps runtime): call the governed **Genie space** (A2 Agent) via the SDK Conversation
API as the app service principal. This is a different surface — it does NOT expose inferred-snippet retrieval —
so we label it honestly (`surface`) rather than pretend it's Genie One.

Either way it's a read (it asks; it doesn't mutate), it's an LLM call (seconds of latency), and the answer is
AI-generated and shown as such.
"""
import json
import os
import re
import subprocess
import time

from fastapi import APIRouter, HTTPException

from ..config import ARM, IS_DATABRICKS_APP, MEASUREMENT_YEAR, get_warehouse_id, get_workspace_client

router = APIRouter()

GENIE_SPACE_ID = os.environ.get("CARE_GENIE_SPACE_ID", "")


def _profile() -> str:
    return os.environ.get("DATABRICKS_PROFILE", "ECT")


def _question(patient_id: str) -> str:
    return (
        f"For measurement year {MEASUREMENT_YEAR}, is patient {patient_id} compliant with the HEDIS GSD "
        f"(Glycemic Status Assessment for Patients With Diabetes) measure, and why? "
        f"Use the governed GSD metric view and cite any ontology page you relied on."
    )


def _cite_from_text(text: str) -> tuple[list[dict], bool]:
    citations, ontology_used = [], False
    for m in sorted(set(re.findall(r"care_protocol\w*\.\w+\.\w+", text))):
        citations.append({"kind": "table", "detail": m})
    if "/discover/pages/" in text:
        ontology_used = True
        citations.append({"kind": "page", "detail": "Genie Ontology Page cited"})
    if "_metrics" in text:
        citations.append({"kind": "metric_view", "detail": "governed metric view cited"})
    return citations, ontology_used


def _ask_cli(patient_id: str) -> dict:
    """Genie One (A1) via the CLI — exposes the inferred-ontology signal."""
    question = _question(patient_id)
    cmd = ["databricks", "genie", "ask", "-s", f"app_{patient_id[:8]}_{int(time.time())}",
           "--output", "json", "--profile", _profile(), "--warehouse-id", get_warehouse_id(), question]
    t0 = time.time()
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Genie One timed out (>180s).")
    except FileNotFoundError:
        raise HTTPException(500, "databricks CLI not found on this host (expected only in local dev).")
    if out.returncode != 0:
        raise HTTPException(502, f"Genie CLI error: {(out.stderr or out.stdout).strip()[:300]}")
    try:
        d = json.loads(out.stdout)
    except json.JSONDecodeError:
        raise HTTPException(502, f"Genie returned non-JSON: {out.stdout.strip()[:300]}")

    text = d.get("text", "") or ""
    generated_sql, tool_names, ontology_used, citations = None, [], False, []
    for tc in d.get("tool_calls", []):
        name = tc.get("name", "")
        if name:
            tool_names.append(name)
        if tc.get("sql") and not generated_sql:
            generated_sql = tc["sql"]
        args = str(tc.get("arguments") or "")
        if name == "search_knowledge_snippets":
            ontology_used = True
            citations.append({"kind": "snippet_search", "detail": args[:200]})
        if name == "get_asset_info" and "knowledge_page" in args:
            ontology_used = True
            citations.append({"kind": "knowledge_page", "detail": args[:200]})
    c2, ont2 = _cite_from_text(text)
    citations += c2
    return {
        "question": question, "answer": text, "generated_sql": generated_sql,
        "tool_names": tool_names, "ontology_used": ontology_used or ont2, "citations": citations,
        "surface": "Genie One (A1, workspace front door)",
        "ran_as": f"the app's Databricks identity against the {ARM} workspace via Genie One",
        "latency_s": round(time.time() - t0, 1),
    }


def _ask_sdk(patient_id: str) -> dict:
    """Governed Genie space (A2 Agent) via the SDK — the deployed path (no CLI)."""
    if not GENIE_SPACE_ID:
        raise HTTPException(500, "CARE_GENIE_SPACE_ID is not set — cannot reach a Genie space.")
    question = _question(patient_id)
    w = get_workspace_client()
    t0 = time.time()
    try:
        msg = w.genie.start_conversation_and_wait(GENIE_SPACE_ID, question)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Genie space error: {type(e).__name__}: {str(e)[:260]}")

    texts, generated_sql = [], None
    for a in (msg.attachments or []):
        qy = getattr(a, "query", None)
        txt = getattr(a, "text", None)
        if qy is not None:
            if getattr(qy, "description", None):
                texts.append(qy.description)
            if getattr(qy, "query", None) and not generated_sql:
                generated_sql = qy.query
        if txt is not None and getattr(txt, "content", None):
            texts.append(txt.content)
    answer = "\n\n".join(t for t in texts if t)
    citations, _ = _cite_from_text(answer + " " + (generated_sql or ""))
    return {
        "question": question, "answer": answer, "generated_sql": generated_sql,
        "tool_names": ["genie_space_query"] if generated_sql else [],
        "ontology_used": False,  # a Genie space does not do Genie One's inferred-snippet retrieval
        "citations": citations,
        "surface": "Governed Genie space (A2 Agent) — not Genie One",
        "ran_as": f"the app service principal against the governed Genie space on the {ARM} workspace",
        "latency_s": round(time.time() - t0, 1),
    }


@router.get("/patient/{patient_id}/genie")
def ask_genie(patient_id: str):
    use_sdk = IS_DATABRICKS_APP or os.environ.get("CARE_GENIE_FORCE_SDK") == "1"
    result = _ask_sdk(patient_id) if use_sdk else _ask_cli(patient_id)
    return {"patient_id": patient_id, "arm": ARM, **result}
