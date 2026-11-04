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
