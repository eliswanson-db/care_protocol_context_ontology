"""Supervisor router for the Care Protocol agent (A6).

Routes a natural-language question to a governed tool (care_protocol_tools) when it matches a known
intent, and otherwise defers to Genie (A2) for open-ended analytical questions. The point of A6: for the
questions the ontology can answer deterministically (measure rates, cohort size, subsumption, value sets,
care gaps), use a *trusted tool* with a fixed reviewed query instead of letting an LLM write SQL.

Pure-Python routing (no LLM) keeps it auditable; swap in an LLM classifier later if desired. `answer()`
takes the tool set and a `query` callable so it runs anywhere (warehouse, Lakebase, aitools).
"""
from __future__ import annotations

import re

_MEASURE_PATTERNS = {
    "GSD": r"\bgsd\b|glycemic|a1c|hba1c|blood sugar",
    "KED": r"\bked\b|kidney|egfr|uacr|renal",
    "BPD": r"\bbpd\b|blood pressure|\bbp\b|hypertension|systolic|diastolic",
    "SPD": r"\bspd\b|statin|cholesterol|lipid",
    "EED": r"\beed\b|eye exam|retinal|retinopathy|ophthal",
}


def route(question: str) -> dict:
    """Return {tool, kwargs} for a matched intent, or {tool: 'genie_fallback'}."""
    q = question.lower()
    measure = next((m for m, pat in _MEASURE_PATTERNS.items() if re.search(pat, q)), None)

    # Care-gap intent (check before rate, since a gap question may also name a measure).
    if re.search(r"care gap|not[_ ]?met|missing|without|haven'?t|gap in care", q) and measure:
        return {"tool": "list_care_gaps", "kwargs": {"measure_id": measure}}
    # Subsumption / hierarchy expansion.
    m = re.search(r"(?:under|descendant|children|subsume|below)\s+(?:code\s+)?([A-Z]\d{2}(?:\.\d+)?)", question, re.I)
    if m:
        return {"tool": "subsumption_expand", "kwargs": {"code_system": "ICD10CM", "ancestor_code": m.group(1).upper()}}
    # Value-set intent. Segment ids are UPPER_SNAKE (e.g. SPD_STATIN, KED_EGFR).
    m = re.search(r"\b([A-Z]{2,}_[A-Z0-9_]+)\b", question)
    if re.search(r"value set|which codes|what codes|codes for", q) and m:
        return {"tool": "resolve_value_set", "kwargs": {"segment_id": m.group(1)}}
    # Cohort size.
    if re.search(r"cohort|how many (?:diabet|patients with diabet)", q) and "diabet" in q and not measure:
        return {"tool": "diabetes_cohort_size", "kwargs": {}}
    # Measure rate / eligibility / counts.
    if measure and re.search(r"rate|complian|adheren|how many|eligible|met|share|percent", q):
        return {"tool": "get_measure_rate", "kwargs": {"measure_id": measure}}
    return {"tool": "genie_fallback", "kwargs": {}}


def answer(question: str, tools: dict, query) -> dict:
    """Route and execute; returns {question, tool, result} or a genie_fallback marker."""
    r = route(question)
    if r["tool"] == "genie_fallback":
        return {"question": question, "tool": "genie_fallback",
                "note": "No governed tool matched; defer to Genie (A2) for open-ended analysis."}
    result = tools[r["tool"]](query, **r["kwargs"])
    return {"question": question, "tool": r["tool"], "result": result}


def summarize(ans: dict) -> str:
    """One-line natural-language summary of a tool result (for display / benchmark answer text)."""
    t, res = ans.get("tool"), ans.get("result", {})
    if t == "genie_fallback":
        return ans["note"]
    if t == "get_measure_rate":
        return (f"{res['measure_id']} ({res['measure_name']}) compliance is {res['compliance_rate_pct']}% "
                f"({res['numerator']}/{res['eligible']} eligible, ages {res['eligible_ages']}).")
    if t == "diabetes_cohort_size":
        return f"The diabetes cohort has {res['patient_count']} patients ({res['method']})."
    if t == "subsumption_expand":
        return f"{res['ancestor_code']} subsumes {res['count']} {res['code_system']} codes."
    if t == "resolve_value_set":
        return f"Value set {res['segment_id']} has {res['count']} codes."
    if t == "list_care_gaps":
        return f"{res['measure_id']} has {res['care_gap_count']} care gaps (patients eligible but NOT_MET)."
    return str(res)
