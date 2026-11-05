"""Genie One retrieval trace — EVERYTHING Genie Ontology retrieved for one question, captured live.

Calls the Genie One responses API (the endpoint `databricks genie ask` uses) and parses its event stream. Each
tool call's OUTPUT METADATA carries what was actually retrieved, so the trace is real, not reconstructed:

  search_knowledge_snippets  -> ranked Ontology PAGES (modeled) + INFERRED knowledge SNIPPETS (mined from
                                Genie spaces, metric views, query history...), with relevance / authority / source
  get_asset_info(page)       -> the Page body exactly as Genie reads it
  search_assets              -> UC asset search (comments / metadata); the stream reports only a result count
  get_asset_info(asset)      -> metric views, tables, Genie agents read
  load_skills                -> Genie skills loaded (content is not in the stream)
  episode_fetch              -> conversation memory (episodic)
  ask_genie_space            -> Genie agents Genie One delegated to
  execute_sql_query          -> SQL it ran
  mcp__*                     -> MCP tools (e.g. the Ontobricks MCP)

Runs are slow (~30-60s), so callers run this in the background and cache per question.
"""
from __future__ import annotations

import json
import re
import threading
import time

from .config import CATALOG, SCHEMA_SEMANTIC, get_workspace_client

_PATH = "/api/2.0/data-rooms/tools/onechat/responses"
_CACHE: dict[str, dict] = {}          # question -> {"status": running|done|error, "t": ts, "trace"|"error": ...}
_LOCK = threading.Lock()
_TTL = 1800


def _events(question: str) -> list[dict]:
    w = get_workspace_client()
    resp = w.api_client.do(
        "POST", _PATH,
        body={"input": [{"role": "user", "type": "message",
                         "content": [{"type": "input_text", "text": question}]}], "enable_viz": False},
        headers={"Accept": "text/event-stream", "Content-Type": "application/json"}, raw=True)
    buf = resp["contents"].read().decode("utf-8", "replace")
    out = []
    for line in buf.splitlines():
        s = line[5:].strip() if line.startswith("data:") else line.strip()
        if s.startswith("{"):
            try:
                out.append(json.loads(s))
            except json.JSONDecodeError:
                pass
    return out


def _on_topic(text: str | None) -> bool:
    t = (text or "").lower()
    return "care_protocol" in t or "care protocol" in t


def _stale(identifier: str) -> bool:
    """A *_metrics view outside the semantic schema = a pre-relocation copy (ADR-0013), not the certified one."""
    return bool(re.search(rf"{re.escape(CATALOG)}\.care_protocol\.\w+_metrics$", identifier or "")) and \
        f".{SCHEMA_SEMANTIC}." not in (identifier or "")


def parse(events: list[dict]) -> dict:
    calls: dict[str, dict] = {}
    outputs: dict[str, dict] = {}
    answer, citations = "", []
    for e in events:
        it = e.get("item") or {}
        if it.get("type") == "function_call":
            try:
                args = json.loads(it.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {"raw": it.get("arguments")}
            calls[it["call_id"]] = {"name": it.get("name", ""), "args": args}
        elif it.get("type") == "function_call_output" and e.get("type") != "response.output_item.updated":
            outputs[it.get("call_id")] = {"output": it.get("output"), "meta": it.get("metadata") or {}}
        elif it.get("type") == "message" and e.get("type") in ("response.output_item.added", "response.output_item.done"):
            for c in it.get("content") or []:
                if c.get("text"):
                    answer = c["text"]
                    citations = [{"title": a.get("title"), "type": a.get("asset_type")}
                                 for a in c.get("annotations") or []]

    snippet_searches, pages_read, asset_searches, assets_read = [], [], [], []
    skills, memory, agents, sql, mcp, order = [], 0, [], [], [], []
    for cid, c in calls.items():
        name, args = c["name"], c["args"]
        out = outputs.get(cid, {})
        meta = out.get("meta", {})
        order.append(name)
        if name == "search_knowledge_snippets":
            pages = [{"id": p.get("id"), "name": p.get("name"), "domain": p.get("domain"),
                      "relevance": round(p.get("relevance_score") or 0, 2),
                      "certified": p.get("certified"), "description": p.get("description"),
                      "on_topic": p.get("domain") == "Clinical Domain"} for p in meta.get("knowledge_pages") or []]
            snips = [{"headline": s.get("headline"), "type": (s.get("snippet_type") or "").replace("SNIPPET_TYPE_", "").lower(),
                      "source": s.get("asset_name"), "relevance": round(s.get("relevance_score") or 0, 2),
                      "authority": round(s.get("authority_score") or 0, 3), "content": s.get("content"),
                      "on_topic": _on_topic(s.get("asset_name")) or _on_topic(s.get("content")),
                      "stale": _stale(s.get("asset_name") or "")}
                     for s in meta.get("knowledge_snippets") or []]
            snippet_searches.append({"query": args.get("query"), "pages": pages, "snippets": snips})
        elif name == "get_asset_info" and meta.get("body") is not None:
            pages_read.append({"page_id": meta.get("page_id"), "body": meta.get("body")})
        elif name == "get_asset_info":
            ident = meta.get("identifier") or str(args.get("asset", ""))
            assets_read.append({"asset": meta.get("name") or ident, "type": (meta.get("asset_type") or "").lower(),
                                "stale": _stale(ident)})
        elif name == "search_assets":
            asset_searches.append({"query": args.get("query"), "keywords": ", ".join(args.get("keywords") or []),
                                   "result": out.get("output")})
        elif name == "load_skills":
            skills.append(args.get("skill_name"))
        elif name == "episode_fetch":
            memory += 1
        elif name == "ask_genie_space":
            agents.append({"space_id": meta.get("space_id"), "question": args.get("question"),
                           "result": out.get("output")})
        elif name == "execute_sql_query":
            sql.append(args.get("query") or "")
        elif name.startswith("mcp__"):
            mcp.append({"tool": name.split("__")[-1], "server": name.split("__")[1] if "__" in name else "", "args": args})
    names = {pg["id"]: pg["name"] for ss in snippet_searches for pg in ss["pages"]}
    for pr in pages_read:
        pr["name"] = names.get(pr["page_id"])
    # agent names from assets read (get_asset_info on the Genie space precedes ask_genie_space)
    agent_names = {a["asset"] for a in assets_read if a["type"] == "genie_space"}
    for a in agents:
        a["name"] = next(iter(agent_names), a["space_id"])
    return {"tool_order": order, "snippet_searches": snippet_searches, "pages_read": pages_read,
            "asset_searches": asset_searches, "assets_read": assets_read, "skills": skills, "memory_fetches": memory,
            "agents": agents, "sql": sql, "mcp": mcp, "answer": answer, "citations": citations}


def get_trace(question: str) -> dict:
    """Return {status: running|done|error, ...}; starts a background run on first call."""
    with _LOCK:
        hit = _CACHE.get(question)
        if hit and (hit["status"] == "running" or time.time() - hit["t"] < _TTL):
            return hit
        _CACHE[question] = {"status": "running", "t": time.time()}

    def run():
        t0 = time.time()
        try:
            tr = parse(_events(question))
            res = {"status": "done", "t": time.time(), "trace": tr, "latency_s": round(time.time() - t0, 1)}
        except Exception as e:  # noqa: BLE001 — surface the real failure (e.g. SP not allowed Genie One)
            res = {"status": "error", "t": time.time(), "error": f"{type(e).__name__}: {str(e)[:300]}"}
        with _LOCK:
            _CACHE[question] = res
    threading.Thread(target=run, daemon=True).start()
    return _CACHE[question]
