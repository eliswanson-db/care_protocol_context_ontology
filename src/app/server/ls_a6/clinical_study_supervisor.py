"""Supervisor router for the Clinical Study lab (A6). Pure-Python, auditable intent routing, no LLM.

Routes to ONE governed tool from clinical_study_tools, abstains when the question is out of scope (HEDIS /
health plan / care gaps) or would pool studies or rule versions, and otherwise defers to the Genie spaces.
It never recomputes an endpoint itself: numbers come from the tools, which read the deterministic engine's
gold tables.
"""

from __future__ import annotations

import re

RV_HINTS = [  # (pattern, rule version) checked in order
    (r"csl-?b|study b", "EP-B-WT24.R1"),
    (r"\bv2\b|\br2\b|version 2|rule version 2|amendment 1|amended|±14|14[- ]day|protocol 2", "EP-A-WT24.R2"),
    (r"\bv1\b|\br1\b|version 1|rule version 1|original|±7|7[- ]day|protocol 1", "EP-A-WT24.R1"),
]
OUT_OF_SCOPE = (
    r"\bhedis\b|\bncqa\b|care gap|\bgsd\b|\bked\b|\bbpd\b|\bspd\b|\beed\b|star rating|health plan|a1c"
)
SUPERIORITY = r"\bsuperior|\bbetter than\b|\bproves?\b|\befficacy\b|\bcausal|\beffective(ness)?\b"


def _rv(q: str) -> str | None:
    return next((rv for pat, rv in RV_HINTS if re.search(pat, q)), None)


def route(question: str) -> dict:
    q = question.lower()
    if re.search(OUT_OF_SCOPE, q):
        return {
            "tool": "abstain",
            "reason": "out_of_scope",
            "note": "This is the Clinical Study lab; HEDIS / health-plan questions belong to the healthcare "
            "demo.",
        }
    if re.search(SUPERIORITY, q):
        return {
            "tool": "abstain",
            "reason": "unsupported_inference",
            "note": "Synthetic, descriptive results cannot establish efficacy, superiority or a causal "
            "effect.",
        }
    subj = re.search(r"\bCSL-[AB]-(?:\d{3}-\d{4}|FX-\d{2})\b", question, re.I)
    concept = re.search(r"\b(MONDO:\d{7})\b", question, re.I)
    if concept and re.search(r"contraindicat|exclud.*class|glp", q):
        return {"tool": "contraindication_check", "kwargs": {"concept_id": concept.group(1).upper()}}
    if concept and re.search(r"comorbid|member|wrc|class", q):
        cls = "WRC-V2" if re.search(r"amendment 1|wrc-v2|protocol 2|sleep apnea", q) else "WRC-V1"
        return {
            "tool": "class_membership",
            "kwargs": {"class_id": cls, "concept_id": concept.group(1).upper()},
        }
    about_obs = re.search(r"observation|record|week 24|weight|measurement|result", q)
    if subj and (re.search(r"eligib|screen|criteri|enrol", q) or (re.search(r"exclu", q) and not about_obs)):
        return {"tool": "eligibility_explain", "kwargs": {"usubjid": subj.group(0).upper()}}
    if subj:
        rv = _rv(q) or ("EP-B-WT24.R1" if subj.group(0).upper().startswith("CSL-B") else None)
        if rv is None:
            return {
                "tool": "clarify",
                "reason": "ambiguous_version",
                "note": "Which rule version: EP-A-WT24.R1 (±7 days) or EP-A-WT24.R2 (±14 days, Amendment 1)?",
            }
        return {
            "tool": "participant_trace",
            "kwargs": {"usubjid": subj.group(0).upper(), "endpoint_version": rv},
        }
    if re.search(r"equivalent|comparab|same definition|compare.*(csl-?a|study a).*(csl-?b|study b)|pool", q):
        return {"tool": "compare_endpoints", "kwargs": {"a": "EP-A-WT24.R2", "b": "EP-B-WT24.R1"}}
    if re.search(r"approved|draft|candidate|±21|21[- ]day|wider window", q):
        study = "CSL-B" if re.search(r"csl-?b|study b", q) else "CSL-A"
        return {"tool": "rule_status", "kwargs": {"study_id": study}}
    if re.search(r"amendment|what changed|changed after|became|recovered", q):
        site = re.search(r"\bSITE-\d{3}\b", question, re.I)
        return {"tool": "amendment_impact", "kwargs": {"site_id": site.group(0).upper() if site else None}}
    if re.search(r"where .*(represented|stored|mapped)|sdtm|dataset|variable|which units|unit", q):
        return {"tool": "dataset_mapping", "kwargs": {}}
    if re.search(r"definition|defined|rule|window|baseline|tie", q) and not re.search(
        r"summary|mean|how many", q
    ):
        rv = _rv(q)
        if rv is None:
            return {"tool": "clarify", "reason": "ambiguous_version", "note": "Which study and rule version?"}
        return {"tool": "rule_definition", "kwargs": {"endpoint_version": rv}}
    if re.search(r"summary|mean|average|median|missing|how many|derived|percent change|results?", q):
        rv = _rv(q)
        if rv is None:
            return {
                "tool": "clarify",
                "reason": "ambiguous_version",
                "note": "Results differ by study and rule version and are never pooled. Which one?",
            }
        return {"tool": "endpoint_summary", "kwargs": {"endpoint_version": rv}}
    return {
        "tool": "genie_fallback",
        "note": "No governed tool matched; ask the Clinical Study Genie spaces.",
    }


def answer(question: str, tools: dict, query) -> dict:
    r = route(question)
    if r["tool"] in ("abstain", "clarify", "genie_fallback"):
        return {"question": question, **r}
    return {
        "question": question,
        "tool": r["tool"],
        "kwargs": r["kwargs"],
        "result": tools[r["tool"]](query, **r["kwargs"]),
    }
