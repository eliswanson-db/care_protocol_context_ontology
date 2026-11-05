"""The controlled supervisor: ONE fixed vanilla agent, identical across every arm.

It answers strictly from the injected context so that any difference in correctness/groundedness is
attributable to the RETRIEVAL approach, not to a smarter front door. Temperature 0 for reproducibility.
If the injected context cannot support an answer it must say so verbatim -- that is how closed_book and
structurally-insufficient arms score a clean miss instead of hallucinating."""
from __future__ import annotations

import os
from functools import lru_cache

import mlflow

AGENT_MODEL = os.environ.get("CARE_AGENT_MODEL", "databricks-claude-sonnet-5")

_SYSTEM = (
    "You are a clinical quality analyst answering HEDIS / care-protocol questions. "
    "Answer ONLY from the CONTEXT provided below. Do not use outside knowledge. "
    "If the context does not contain enough information to answer, reply with exactly: "
    "INSUFFICIENT CONTEXT. "
    "Be concise: give the specific number, code, or definition asked for, and cite the context you used."
)


@lru_cache(maxsize=1)
def _client():
    from databricks.sdk import WorkspaceClient
    profile = os.environ.get("DATABRICKS_CONFIG_PROFILE") or os.environ.get("DATABRICKS_PROFILE")
    w = WorkspaceClient(profile=profile) if profile else WorkspaceClient()
    return w.serving_endpoints.get_open_ai_client()


@mlflow.trace(span_type="CHAT_MODEL", name="supervisor")
def answer(question: str, context_docs: list[dict]) -> str:
    if context_docs:
        ctx = "\n\n".join(
            f"[{i + 1}] {d.get('page_content', '')}".strip() for i, d in enumerate(context_docs))
    else:
        ctx = "(no context was retrieved)"
    msg = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": f"QUESTION:\n{question}\n\nCONTEXT:\n{ctx}"},
    ]
    # NB: Claude-5 Databricks endpoints reject the `temperature` param, so we omit it (these models are
    # near-deterministic for short factual answers anyway).
    resp = _client().chat.completions.create(model=AGENT_MODEL, messages=msg, max_tokens=400)
    return _as_text(resp.choices[0].message.content)


def _as_text(content) -> str:
    """Claude serving endpoints sometimes return `content` as a list of content-blocks (dicts with a `text`
    field) rather than a plain string -- most often on longer, structured answers. Normalise either shape to
    text so downstream `.strip()` / the GenAI judges never see a list."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict):
                parts.append(b.get("text") or b.get("content") or "")
            elif isinstance(b, str):
                parts.append(b)
            else:
                parts.append(getattr(b, "text", "") or "")
        return "\n".join(p for p in parts if p).strip()
    return str(content).strip()


import re as _re

_LOOKS_LIKE_SQL = _re.compile(r"^\s*(\(\s*)*(select|with)\b", _re.I)


class HarnessError(RuntimeError):
    """An infrastructure failure (auth, truncation, endpoint error) -- retried, and never scored as a result."""


# --- Tier 2: can the retrieved context alone get the agent to the answer with ONE query? -------------------------
_SQL_SYSTEM = (
    "You write Databricks SQL. You are given a QUESTION and the CONTEXT retrieved by one retrieval approach. "
    "Write exactly ONE read-only SQL query (a single SELECT, CTEs allowed) whose result answers the question. "
    "Use ONLY tables, views, columns and code values that appear in the CONTEXT; do not invent table or column "
    "names and do not use outside knowledge of the schema. If the CONTEXT does not tell you enough to write such "
    "a query, reply with exactly: NO_QUERY. Otherwise reply with the SQL only, no explanation, no markdown fences."
)


@mlflow.trace(span_type="CHAT_MODEL", name="write_sql")
def write_sql(question: str, context_docs: list[dict]) -> str | None:
    """One SQL query written from the retrieved context only (no schema dump, no retries). None = NO_QUERY."""
    ctx = "\n\n".join(f"[{i + 1}] {d.get('page_content', '')}".strip() for i, d in enumerate(context_docs)) \
        or "(no context was retrieved)"
    msg = [{"role": "system", "content": _SQL_SYSTEM},
           {"role": "user", "content": f"QUESTION:\n{question}\n\nCONTEXT:\n{ctx}"}]
    # Reasoning tokens count against max_tokens on these endpoints, so the budget must be generous; a "length"
    # finish means the SQL was cut off -- a harness failure, never a retrieval verdict.
    resp = _client().chat.completions.create(model=AGENT_MODEL, messages=msg, max_tokens=16000)
    if resp.choices[0].finish_reason == "length":
        raise HarnessError("write_sql hit max_tokens (output truncated)")
    sql = _as_text(resp.choices[0].message.content).strip()
    if sql.startswith("```"):
        sql = sql.strip("`").split("\n", 1)[-1] if "\n" in sql else ""
        sql = sql.rsplit("```", 1)[0]
    sql = sql.strip().rstrip(";").strip()
    if not sql or sql.upper().startswith("NO_QUERY") or not _LOOKS_LIKE_SQL.match(sql):
        return None  # empty, an explicit NO_QUERY, or prose instead of SQL
    return sql


# --- Schema-aided tier: semantic context + the shared physical schema + a few tries with the error fed back. --------
_SQL_SCHEMA_SYSTEM = (
    "You write Databricks SQL. You get a QUESTION, the CONTEXT retrieved by one retrieval approach (it may be empty), "
    "and the physical SCHEMA (table and column names and types only). Use the CONTEXT for meaning -- definitions, "
    "rules, codes, which asset answers what -- and the SCHEMA for exact names. Do not use outside knowledge of the "
    "business rules or codes; if the meaning you need is not in the CONTEXT, you may only use what the names in the "
    "SCHEMA make obvious. Metric views (care_protocol_semantic) are queried as "
    "SELECT `Dim`, MEASURE(`Measure Name`) FROM <view> [WHERE `Dim` = ...] GROUP BY `Dim`; backtick names with "
    "spaces. Write exactly ONE read-only SELECT (CTEs allowed) whose result answers the question, or reply exactly "
    "NO_QUERY if you cannot. Reply with SQL only, no markdown."
)


@mlflow.trace(span_type="CHAT_MODEL", name="write_sql_with_schema")
def write_sql_with_schema(question: str, context_docs: list[dict], schema: str, previous: list[tuple[str, str]]):
    """One attempt; `previous` = [(sql, error)] from earlier failed attempts, fed back so the agent can fix them."""
    ctx = "\n\n".join(f"[{i + 1}] {d.get('page_content', '')}".strip() for i, d in enumerate(context_docs)) \
        or "(no context was retrieved)"
    user = f"QUESTION:\n{question}\n\nCONTEXT:\n{ctx}\n\nSCHEMA:\n{schema}"
    for sql, err in previous:
        user += f"\n\nYOUR EARLIER QUERY FAILED:\n{sql}\nERROR: {err}\nFix it."
    resp = _client().chat.completions.create(
        model=AGENT_MODEL, max_tokens=16000,
        messages=[{"role": "system", "content": _SQL_SCHEMA_SYSTEM}, {"role": "user", "content": user}])
    if resp.choices[0].finish_reason == "length":
        raise HarnessError("write_sql_with_schema hit max_tokens (output truncated)")
    sql = _as_text(resp.choices[0].message.content).strip()
    if sql.startswith("```"):
        sql = sql.strip("`").split("\n", 1)[-1] if "\n" in sql else ""
        sql = sql.rsplit("```", 1)[0]
    sql = sql.strip().rstrip(";").strip()
    if not sql or sql.upper().startswith("NO_QUERY") or not _LOOKS_LIKE_SQL.match(sql):
        return None  # empty, an explicit NO_QUERY, or prose instead of SQL
    return sql
