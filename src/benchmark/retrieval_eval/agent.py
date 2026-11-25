"""The controlled supervisor: ONE fixed vanilla agent, identical across every arm.

It answers strictly from the injected context so that any difference in correctness/groundedness is
attributable to the RETRIEVAL approach, not to a smarter front door. Temperature 0 for reproducibility.
If the injected context cannot support an answer it must say so verbatim -- that is how closed_book and
structurally-insufficient arms score a clean miss instead of hallucinating."""
from __future__ import annotations

import json
import os
import re
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
    "a query, reply with NO_QUERY followed by a colon and one short sentence naming what the CONTEXT lacks (e.g. "
    "'NO_QUERY: no table with patient-level A1c results is named.'). Otherwise reply with the SQL only, no "
    "explanation, no markdown fences."
)


@mlflow.trace(span_type="CHAT_MODEL", name="write_sql")
def write_sql(question: str, context_docs: list[dict]) -> tuple[str | None, str]:
    """One SQL query written from the retrieved context only (no schema dump, no retries).
    Returns (sql, "") or (None, the agent's one-line reason for declining)."""
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
    if sql.upper().startswith("NO_QUERY"):
        return None, _decline_reason(sql)
    if sql.startswith("```"):
        sql = sql.strip("`").split("\n", 1)[-1] if "\n" in sql else ""
        sql = sql.rsplit("```", 1)[0]
    sql = sql.strip().rstrip(";").strip()
    if not sql or not _LOOKS_LIKE_SQL.match(sql):
        return None, "The agent replied with prose instead of a query."
    return sql, ""


def _decline_reason(text: str) -> str:
    """The sentence after NO_QUERY, or a neutral note if the agent gave none."""
    why = re.sub(r"^\s*NO_QUERY\s*[:\-–—]?\s*", "", text.strip(), flags=re.IGNORECASE).strip()
    return why[:240] or "The agent declined without giving a reason."


# --- One-shot query in each approach's NATIVE interface ----------------------------------------------------------
# metric view / Genie Ontology / RAG / closed book -> one read-only SQL statement over Unity Catalog
# closure tables                                   -> one closure-tool call
# Ontobricks graph                                 -> one graph-runner call
_TOOL_SYSTEM = (
    "You get a QUESTION and the CONTEXT retrieved by one retrieval approach. You may make exactly ONE call to the "
    "{name}. Use only node ids / codes that appear in the CONTEXT (or that the CONTEXT's naming scheme makes "
    "unambiguous). Tools:\n{tools}\n"
    "Reply with JSON only: {{\"tool\": \"<name>\", \"args\": {{...}}}}. If one call cannot answer the question, reply "
    "NO_QUERY followed by a colon and one short sentence naming what the CONTEXT lacks."
)


def _parse_tool(text: str) -> dict | None:
    t = text.strip()
    if t.upper().startswith("NO_QUERY"):
        return None
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return d if isinstance(d, dict) and d.get("tool") else None


@mlflow.trace(span_type="CHAT_MODEL", name="write_query")
def write_query(question: str, context_docs: list[dict], interface: str, tools: dict[str, str] | None = None):
    """Return (query, decline_reason): query is {"kind": "sql", "sql": ...} | {"kind": "tool", "tool": ..., "args":
    {...}}, or None with the agent's one-line reason for not writing one (NO_QUERY)."""
    if interface == "sql":
        sql, why = write_sql(question, context_docs)
        return ({"kind": "sql", "sql": sql}, "") if sql else (None, why)
    name = {"graph": "graph runner (in-memory traversal over the Ontobricks graph)",
            "closure": "closure-table tools"}[interface]
    ctx = "\n\n".join(f"[{i + 1}] {d.get('page_content', '')}".strip() for i, d in enumerate(context_docs)) \
        or "(no context was retrieved)"
    msg = [{"role": "system", "content": _TOOL_SYSTEM.format(
               name=name, tools="\n".join(f"- {v}" for v in (tools or {}).values()))},
           {"role": "user", "content": f"QUESTION:\n{question}\n\nCONTEXT:\n{ctx}"}]
    resp = _client().chat.completions.create(model=AGENT_MODEL, messages=msg, max_tokens=16000)
    if resp.choices[0].finish_reason == "length":
        raise HarnessError("write_query hit max_tokens (output truncated)")
    text = _as_text(resp.choices[0].message.content)
    call = _parse_tool(text)
    if call:
        return {"kind": "tool", "interface": interface, **call}, ""
    return None, (_decline_reason(text) if text.strip().upper().startswith("NO_QUERY")
                  else "The agent's reply was not a valid tool call.")


APPROACH_DOES = {
    "metric_view": "retrieves the YAML definitions of the certified metric views most relevant to the question",
    "closure_sql": "resolves diagnosis / drug concepts named in the question to ICD-10 / RxNorm hierarchy nodes and "
                   "returns their ancestors, subtree and the patients recorded under it; nothing else",
    "genie_ontology": "Genie's own retrieval: inferred snippets mined from Genie spaces and query history, plus Pages",
    "genie_ontology_dmvm": "Genie's own retrieval on the DMVM workspace: inferred snippets plus Pages",
    "rag": "the top 5 passages of the care-protocol documents (prose, no tables)",
    "ontobricks": "the subgraph around the entities the question names, from the published Ontobricks graph",
    "closed_book": "nothing (the no-retrieval floor)",
}
APPROACH_DOES_LS = {
    **APPROACH_DOES,
    "metric_view": "retrieves the YAML definitions of the certified clinical-study metric views most relevant to the "
                   "question",
    "closure_sql": "resolves disease / drug-class concepts and protocol concept classes named in the question to MONDO / "
                   "MED-RT nodes, returns their ancestors, subtree, class roots and the participants recorded under "
                   "them; nothing else",
    "genie_ontology": "Genie's own retrieval: inferred snippets mined from Genie spaces and query history, plus Pages",
    "rag": "the top 5 passages of the study documents and monitoring visit reports (prose, no tables)",
    "ontobricks": "the subgraph around the entities the question names, from the published ClinicalStudyLab graph",
}


@mlflow.trace(span_type="CHAT_MODEL", name="explain")
def explain(question: str, approach: str, outcome: dict, ls: bool = False) -> str:
    """One plain sentence (<= 16 words) saying exactly why this approach did or didn't answer, from the judged
    evidence: which gold fact was or wasn't in the context, what the one query returned, or how it failed."""
    msg = [{"role": "system", "content": (
        "Write ONE plain sentence of at most 18 words saying why this retrieval approach did or did not answer the "
        "question, based ONLY on the evidence. Follow EVIDENCE.what_happened:\n"
        "- facts stated in what it retrieved: say which retrieved item states them (e.g. 'The KED Page states ages "
        "18-85 and both tests.').\n"
        "- agent declined to query: say what the retrieval had and what it lacked (e.g. 'Has the >9% cut-off but "
        "nothing on who is counted.').\n"
        "- a query ran: read the query, say what it computed, and, if wrong, how that differs from the question (e.g. "
        "'Counted diabetes AND CKD, not diabetes with kidney complications: 1,791.'). Name it by its interface (SQL, "
        "closure-tool call, graph-runner call). If the result matches the gold, do not invent shortcomings.\n"
        "- retrieved nothing: say why this approach has nothing for this question, using APPROACH_DOES.\n"
        "- EVIDENCE.outcome 'incomplete' means nothing contradicts the gold but a fact is missing: name the missing "
        "fact. 'wrong' means a fact is contradicted: give the value it produced versus the gold value.\n"
        "Never write 'no SQL query was executed'. No preamble, no markdown.")},
        {"role": "user", "content": f"QUESTION: {question}\nAPPROACH: {approach}\n"
                                    f"APPROACH_DOES: {(APPROACH_DOES_LS if ls else APPROACH_DOES).get(approach, '')}"
                                    f"\nEVIDENCE: "
                                    f"{json.dumps(outcome, ensure_ascii=False)[:6000]}"}]
    resp = _client().chat.completions.create(model=AGENT_MODEL, messages=msg, max_tokens=4000)
    return _as_text(resp.choices[0].message.content).strip().strip('"')[:220]


# --- Evidence-based fact judge: the verdict must come with a verbatim quote, and the quote is checked in code --------
JUDGE_MODEL = os.environ.get("CARE_JUDGE_MODEL", "databricks:/databricks-claude-sonnet-5").replace("databricks:/", "")
_JUDGE_SYSTEM = (
    "You check whether a TEXT states a FACT. The fact counts as stated only if the TEXT says it explicitly about the "
    "entities in the question -- not if it states a general rule the fact could be inferred from, lists codes it could "
    "be looked up with, or describes how it could be computed. For a QUERY and its RESULT, read them together: the "
    "query says what the rows are (the table, the filters, e.g. segment KED_EGFR for 2026), and the rows must show the "
    "values (a filter alone, with no rows confirming it, states nothing). The rows must show the fact (allow "
    "formatting differences: a rate as a fraction or percent, rounding to 3 significant figures, a count as the number "
    "of rows, codes with or without a prefix). The quote must state the fact ON ITS OWN, read by someone who does not "
    "already know the answer; if you have to add an inference to get from the quote to the fact, it is not stated. "
    "Reply with JSON only: "
    "Decide 'stated' exactly as above; the contradiction check below never changes it. If the fact is NOT stated, "
    "also say whether the TEXT CONTRADICTS it: it gives a DIFFERENT VALUE for the same thing -- a different number, "
    "date, yes/no, code or named entity (e.g. 40.1% where the fact says 39.7%, 'dispensed' where the fact says "
    "'ordered', 'no record exists' where the fact says one does). Leaving part of the fact out, or describing the same "
    "value more narrowly (e.g. naming two of the three codes behind the same count), is NOT a contradiction. "
    "Reply with JSON only: "
    '{"stated": true|false, "contradicted": true|false, '
    '"quote": "<the shortest verbatim span of the TEXT that states it, or that contradicts it, or empty>", '
    '"why": "<one short sentence>"}'
)


def _norm(t: str) -> str:
    """Compare quotes on word tokens only: YAML line continuations (backslash + newline), dash and quote styles and
    markdown punctuation must not make a real quote look invented."""
    t = re.sub(r"\\[nrt]", " ", (t or "").lower()).replace("\\", " ")
    return " ".join(re.findall(r"[a-z0-9]+(?:\.[a-z0-9]+)*", t))


def _loads_lenient(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        return {}
    s = m.group(0)
    for cand in (s, re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", s)):
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            continue
    return {}


@mlflow.trace(span_type="LLM", name="judge_fact")
def judge_fact(question: str, fact: str, text: str, where: str) -> dict:
    """{"ok", "verdict", "quote", "rationale"}. verdict = stated | contradicted | missing. ok (= stated) requires
    stated=true AND the quote to appear verbatim in the text; a contradiction needs a verbatim quote too."""
    if not text or not text.strip() or text.startswith("(no context retrieved)"):
        return {"ok": False, "verdict": "missing", "quote": "", "rationale": f"Nothing in the {where}."}
    msg = [{"role": "system", "content": _JUDGE_SYSTEM},
           {"role": "user", "content": f"QUESTION: {question}\nFACT: {fact}\nTEXT ({where}):\n{text[:24000]}"}]
    for attempt in range(2):
        resp = _client().chat.completions.create(model=JUDGE_MODEL, messages=msg, max_tokens=8000)
        raw = _as_text(resp.choices[0].message.content)
        d = _loads_lenient(raw)
        if not d:
            raise HarnessError("judge_fact: unparseable judge reply")
        stated, quote, why = bool(d.get("stated")), str(d.get("quote") or ""), str(d.get("why") or "")
        contra = bool(d.get("contradicted")) and not stated
        if not ((stated or contra) and quote and _norm(quote) not in _norm(text)):
            break
        # One retry: the quote must be copied exactly, or the fact isn't stated.
        msg = msg + [{"role": "assistant", "content": raw},
                     {"role": "user", "content": "That quote does not appear verbatim in the TEXT. Copy the exact span "
                                                 "from the TEXT, or answer stated=false."}]
    if stated and quote and _norm(quote) not in _norm(text):
        return {"ok": False, "verdict": "missing", "quote": quote,
                "rationale": f"Judge quoted text that is not in the {where}: {why}"}
    if stated and not quote:
        return {"ok": False, "verdict": "missing", "quote": "", "rationale": f"Judge gave no supporting quote. {why}"}
    if stated:
        return {"ok": True, "verdict": "stated", "quote": quote, "rationale": why}
    if contra and quote and _norm(quote) in _norm(text):
        return {"ok": False, "verdict": "contradicted", "quote": quote, "rationale": why}
    return {"ok": False, "verdict": "missing", "quote": "", "rationale": why}
