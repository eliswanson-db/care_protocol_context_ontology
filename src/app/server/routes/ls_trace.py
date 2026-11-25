"""Life-sciences traces: three pieces of information, each followed from its source through every layer into the
retrieval approaches. The HEDIS counterpart is server/traces.py + routes/tracer.py + routes/stage_detail.py; the
responses have the same shapes, so the same Trace tab renders both.

  GET /api/ls/traces                                   the three traces, each with its participant (picked by rule)
  GET /api/ls/traces/{usubjid}/journey?trace=          the stages + an answer whose claims link back to them
  GET /api/ls/traces/{usubjid}/stage/{key}?trace=      one stage, retrieved live (with the queries that produced it)

  lb    a body weight keyed in pounds: EDC export -> bronze -> SDTM VS (kg) -> Week 24 endpoint candidate -> result
  amd1  Amendment 1's Week 24 window (+/-7 -> +/-14 days): document -> rule registry -> a participant it recovered
  mh    a medical-history term: verbatim -> MONDO code -> disease hierarchy -> the exclusion it triggers

Participants come from server/ls_heroes.py (stated rules, lowest USUBJID that qualifies), never chosen by hand.
"""

from __future__ import annotations

import html
import re
import time

from fastapi import APIRouter, HTTPException

from ..config import CATALOG, LS_ONTOBRICKS_NS, LS_ONTOBRICKS_TABLE, ONTOBRICKS_CATALOG, ONTOBRICKS_SCHEMA
from ..ls_heroes import HEROES
from ..warehouse import run_sql

router = APIRouter(prefix="/ls/traces")
DEMO = "life_sciences_clinical"
CS, STD, SEM = f"{CATALOG}.clinical_study", f"{CATALOG}.clinical_study_standards", f"{CATALOG}.clinical_study_semantic"
G = f"{ONTOBRICKS_CATALOG}.{ONTOBRICKS_SCHEMA}.{LS_ONTOBRICKS_TABLE}_graph"
NS = LS_ONTOBRICKS_NS
ID = re.compile(r"^CSL-[AB]-\d{3}-\d{4}$")

TRACES: dict[str, dict] = {
    "lb": {
        "hero": "lb_weight",
        "title": "A body weight keyed in pounds",
        "summary": "One Week 24 weight, keyed in lb at a US site, standardized to kg and used in the primary endpoint.",
        "stages": ["protocol", "raw", "bronze", "silver", "gold", "metric", "page", "rag", "closure_ret", "ontobricks"],
        "docs": [("CSL-DMS-v1.0", "2.2"), ("CSL-A-SAP-v2.0", "9.4.1")],
        "rag_question": "How is a body weight recorded in pounds converted for the Week 24 endpoint, and which units "
                        "are valid?",
    },
    "amd1": {
        "hero": "amd1_recovered",
        "title": "Amendment 1's Week 24 window",
        "summary": "One protocol change, the Week 24 window from ±7 to ±14 days, followed into the rule registry and "
                   "a participant it recovered.",
        "stages": ["protocol", "bronze", "silver", "gold", "metric", "page", "rag", "closure_ret", "ontobricks"],
        "docs": [("CSL-A-PROT-AMD1", "1"), ("CSL-A-SAP-v1.0", "9.4.1"), ("CSL-A-SAP-v2.0", "9.4.1")],
        "rag_question": "What did CSL-A Amendment 1 change about the Week 24 analysis window, and why?",
    },
    "mh": {
        "hero": "mh_hierarchy_exclusion",
        "title": "A medical-history term, through the disease hierarchy",
        "summary": "One verbatim history term, coded to MONDO and rolled up the disease hierarchy to the exclusion it "
                   "triggers.",
        "stages": ["protocol", "raw", "bronze", "silver", "closure", "cohort", "metric", "page", "rag", "closure_ret",
                   "ontobricks"],
        "docs": [("CSL-A-PROT-v1.0", "5.2")],
        "rag_question": "Which medical history excludes a participant from CSL-A?",
    },
}


# ------------------------------------------------------------------------------------------------ helpers
def _q(sql: str, params: dict | None, log: list | None = None, label: str = "") -> list[dict]:
    if log is not None:
        log.append({"label": label, "sql": re.sub(r"\s+", " ", sql).strip()})
    return run_sql(sql, params or {})


def _short(iri: str | None) -> str:
    return (iri or "").replace(NS, "")


def _num(x, nd=1) -> str:
    try:
        return f"{float(x):.{nd}f}"
    except (TypeError, ValueError):
        return "—"


def _check(usubjid: str, trace: str) -> dict:
    if trace not in TRACES:
        raise HTTPException(404, f"Unknown trace {trace!r}; known: {', '.join(TRACES)}")
    if not ID.match(usubjid):
        raise HTTPException(400, f"invalid participant id {usubjid!r}")
    return TRACES[trace]


def _followup(u: str, rv: str) -> dict:
    """The Week 24 weight a rule version selected (or, if none, the visit labelled WEEK 24), with its SDTM row."""
    rows = run_sql(
        f"""SELECT c.obs_id, c.decision, c.reason, c.days_from_target, c.visit, c.vsdtc, v.VSORRES, v.VSORRESU,
                   v.CPL_RAW_UNIT, v.VSSTRESN, v.CPL_SOURCE_RECORD_ID, v.VSDY
            FROM {CS}.gold_endpoint_candidate c JOIN {CS}.silver_vs v ON v.CPL_OBS_ID = c.obs_id
            WHERE c.USUBJID = :u AND c.rule_version = :rv AND c.role = 'FOLLOWUP'
            ORDER BY c.decision = 'SELECTED' DESC, c.visit = 'WEEK 24' DESC, abs(c.days_from_target) LIMIT 1""",
        {"u": u, "rv": rv})
    return rows[0] if rows else {}


def _mh_term(u: str) -> dict:
    rows = run_sql(
        f"""SELECT mh.MHTERM, mh.CPL_MONDO_ID, mh.MHSTDTC, mh.CPL_SOURCE_RECORD_ID, k.label AS mondo_label,
                   element_at(e.path_labels, -1) AS root_label, element_at(e.path, -1) AS root_code
            FROM {CS}.gold_eligibility_criterion e
            JOIN {CS}.silver_mh mh ON mh.USUBJID = e.USUBJID AND array_contains(e.evidence, mh.CPL_SOURCE_RECORD_ID)
            LEFT JOIN {STD}.kb_concept k ON k.concept_id = mh.CPL_MONDO_ID
            WHERE e.USUBJID = :u AND e.criterion_id = 'EXC-MH' AND e.outcome = 'TRIGGERED' LIMIT 1""", {"u": u})
    return rows[0] if rows else {}


# ------------------------------------------------------------------------------------------------ heroes
_hero_cache: dict = {"t": 0.0, "v": None}


def _hero(trace: str) -> dict | None:
    t = TRACES[trace]
    rule = next(h for h in HEROES if h["id"] == t["hero"])
    rows = run_sql(rule["sql"])
    u = rows[0]["u"] if rows else None
    if not u:
        return None
    if trace == "lb":
        f = _followup(u, "R2")
        chips = [f"{f.get('VSORRES')} {f.get('CPL_RAW_UNIT')}", f"→ {_num(f.get('VSSTRESN'))} kg", str(f.get("visit")),
                 str(f.get("vsdtc"))[:10]]
        question = (f"Participant {u}'s Week 24 weight was keyed as {f.get('VSORRES')} {f.get('CPL_RAW_UNIT')}. "
                    f"How does it become their Week 24 result?")
    elif trace == "amd1":
        f1, f2 = _followup(u, "R1"), _followup(u, "R2")
        chips = [f"{f2.get('visit')} {f2.get('days_from_target')} days from target", f"R1 {f1.get('decision', '—').lower()}",
                 f"R2 {f2.get('decision', '—').lower()}"]
        question = (f"Participant {u}'s Week 24 visit was {f2.get('days_from_target')} days after the target date. "
                    f"Do they have a Week 24 result, and under which rule?")
    else:
        m = _mh_term(u)
        chips = [str(m.get("MHTERM")), str(m.get("CPL_MONDO_ID")), f"since {m.get('MHSTDTC')}"]
        question = f"Participant {u}'s history records {m.get('MHTERM')!r}. Can they be enrolled in CSL-A, and why?"
    return {"trace": trace, "title": t["title"], "summary": t["summary"], "patient_id": u, "chips": chips,
            "question": question, "rule": rule["rule"]}


@router.get("")
def list_traces():
    """The three traces with their participants (cached 10 minutes)."""
    if not _hero_cache["v"] or time.time() - _hero_cache["t"] > 600:
        out = [h for h in (_hero(k) for k in TRACES) if h]  # no qualifying participant -> leave the trace out
        _hero_cache.update(t=time.time(), v=out)
    return {"demo_id": DEMO, "traces": _hero_cache["v"]}


def _question(u: str, trace: str) -> str:
    h = next((x for x in list_traces()["traces"] if x["trace"] == trace and x["patient_id"] == u), None)
    return h["question"] if h else f"Trace “{TRACES[trace]['title']}” for participant {u}"


# ------------------------------------------------------------------------------------------------ stages
def _protocol(u, log, trace):
    secs = []
    for doc, num in TRACES[trace]["docs"]:
        r = _q(f"SELECT d.title, d.version, d.status, d.effective_date, s.heading, s.text FROM {CS}.doc_section s "
               f"JOIN {CS}.doc_document d USING (document_id) WHERE s.document_id = :d AND s.section_number = :n",
               {"d": doc, "n": num}, log, f"{doc} §{num}")
        if r:
            x = r[0]
            secs.append({"label": f"{doc} §{num} {x['heading']} · {x['status']}, effective {x['effective_date']}",
                         "kind": "quote", "text": x["text"]})
    pv = _q(f"SELECT protocol_version, eligibility_rule_id, STUDYID FROM {CS}.gold_participant_population "
            f"WHERE USUBJID = :u", {"u": u}, log, "The protocol version this participant was screened under")
    p0 = pv[0] if pv else {}
    secs.append({"label": "This participant", "kind": "kv", "data": {
        "Study": p0.get("STUDYID"), "Protocol version at screening": p0.get("protocol_version"),
        "Eligibility rule applied": p0.get("eligibility_rule_id")}})
    what = {"lb": "The data management specification says how a site's unit becomes kg; the SAP says which units "
                  "are valid for the endpoint.",
            "amd1": "Amendment 1 widens the Week 24 window; SAP 1.0 and 2.0 hold the two versions of the rule.",
            "mh": "The protocol's exclusion criteria: an exclusionary condition, including any more specific form."}
    return {"what": what[trace], "takeaway": f"{len(secs) - 1} approved document section(s) define this trace's rule.",
            "source": f"{CS}.doc_document · doc_section", "sections": secs}


def _raw_row(u, log, kind: str) -> tuple[dict, str]:
    if kind == "mh":
        m = _mh_term(u)
        b = _q(f"SELECT record_id, _source_file FROM {CS}.bronze_edc_mh WHERE record_id = :r",
               {"r": m.get("CPL_SOURCE_RECORD_ID")}, log, "Which export file the history row came from")
    else:
        f = _followup(u, "R2")
        b = _q(f"SELECT record_id, _source_file FROM {CS}.bronze_edc_vs WHERE record_id = :r",
               {"r": f.get("CPL_SOURCE_RECORD_ID")}, log, "Which export file the weight row came from")
    if not b:
        return {}, ""
    path = re.sub(r"^dbfs:", "", b[0]["_source_file"])
    if not re.match(r"^/Volumes/[\w./-]+$", path):
        raise HTTPException(502, "unexpected source file path")
    row = _q(f"SELECT * FROM read_files('{path}', format => 'csv', header => true, inferColumnTypes => false) WHERE record_id = :r",
             {"r": b[0]["record_id"]}, log, "The row, read straight from the delivered EDC export")
    return (row[0] if row else {}), path


def _raw(u, log, trace):
    row, path = _raw_row(u, log, "mh" if trace == "mh" else "vs")
    data = {k: v for k, v in row.items() if not k.startswith("_")}
    take = (f"The site keyed {data.get('vsorres')} {data.get('vsorresu')!r} on {data.get('vsdtc')}: the unit is "
            f"free text as typed, not yet a CDISC value." if trace != "mh" else
            f"The site keyed the history term {data.get('mhterm')!r}; the EDC carries no MONDO code until coding.")
    return {"what": "The EDC export exactly as delivered: one CSV row per record, every field a string.",
            "takeaway": take, "source": path,
            "sections": [{"label": "The delivered row", "kind": "kv", "data": data}]}


def _bronze(u, log, trace):
    if trace == "mh":
        rows = _q(f"SELECT record_id, mhseq, mhterm, mhstdtc, _source_table FROM {CS}.bronze_edc_mh "
                  f"WHERE usubjid = :u ORDER BY mhseq", {"u": u}, log, "Medical-history rows as landed")
        take = f"{len(rows)} history rows landed for this participant, as text."
    else:
        rows = _q(f"SELECT record_id, visit, vsdtc, vsorres, vsorresu, vsstat FROM {CS}.bronze_edc_vs "
                  f"WHERE usubjid = :u AND vstestcd = 'WEIGHT' ORDER BY vsdtc", {"u": u}, log,
                  "Every weight row as landed")
        units = sorted({str(r["vsorresu"]) for r in rows})
        take = f"{len(rows)} weight rows landed, all strings; units as keyed: {', '.join(units)}."
    return {"what": "Bronze: the export landed as-is, plus the file it came from. Nothing is cleaned here.",
            "takeaway": take, "source": f"{CS}.bronze_edc_{'mh' if trace == 'mh' else 'vs'}",
            "sections": [{"label": "Landed rows", "kind": "table", "rows": rows}]}


def _silver(u, log, trace):
    if trace == "mh":
        rows = _q(f"SELECT mh.MHSEQ, mh.MHTERM, mh.CPL_MONDO_ID, k.label AS mondo_label, mh.CPL_CODING_STATUS, "
                  f"mh.MHSTDTC FROM {CS}.silver_mh mh LEFT JOIN {STD}.kb_concept k ON k.concept_id = mh.CPL_MONDO_ID "
                  f"WHERE mh.USUBJID = :u ORDER BY mh.MHSEQ", {"u": u}, log, "SDTM MH, coded to MONDO")
        m = _mh_term(u)
        take = (f"{m.get('MHTERM')!r} is coded {m.get('CPL_MONDO_ID')} ({m.get('mondo_label')}). MedDRA isn't used "
                f"(licensed); MONDO is the demo's disease vocabulary (CSL-DMS §3).")
        return {"what": "Silver: SDTM-shaped MH, each verbatim term coded to a MONDO disease.", "takeaway": take,
                "source": f"{CS}.silver_mh", "sections": [{"label": "Coded history", "kind": "table", "rows": rows}]}
    rows = _q(f"SELECT VSSEQ, VISIT, VSDTC, VSDY, VSORRES, VSORRESU, CPL_RAW_UNIT, round(VSSTRESN, 2) AS VSSTRESN_kg, "
              f"CPL_UNIT_MAPPING_STATUS FROM {CS}.silver_vs WHERE USUBJID = :u AND VSTESTCD = 'WEIGHT' ORDER BY VSDTC",
              {"u": u}, log, "SDTM VS weights: unit mapped to CDISC CT, value standardized to kg")
    f = _followup(u, "R2")
    take = (f"The Week 24 weight {f.get('VSORRES')} {f.get('CPL_RAW_UNIT')} becomes VSORRESU = {f.get('VSORRESU')} "
            f"(CDISC CT) and VSSTRESN = {_num(f.get('VSSTRESN'), 2)} kg (× 0.45359237); the raw unit is kept for "
            f"lineage." if trace == "lb" else
            f"Study day {f.get('VSDY')} for the visit labelled {f.get('visit')}: the analysis window is decided by "
            f"the date, not the label.")
    return {"what": "Silver: SDTM VS. The site's unit is mapped to a CDISC CT value and the result standardized.",
            "takeaway": take, "source": f"{CS}.silver_vs", "sections": [{"label": "Weights", "kind": "table", "rows": rows}]}


def _gold(u, log, trace):
    cand = _q(f"SELECT rule_version, role, visit, vsdtc, round(weight_kg, 2) AS weight_kg, days_from_target, decision, "
              f"reason FROM {CS}.gold_endpoint_candidate WHERE USUBJID = :u AND endpoint_id = 'EP-A-WT24' "
              f"AND (decision = 'SELECTED' OR (role = 'FOLLOWUP' AND abs(days_from_target) <= 21)) "
              f"ORDER BY rule_version, role, vsdtc", {"u": u}, log,
              "Every candidate weight near the target, with the engine's decision and reason")
    res = _q(f"SELECT endpoint_version, result_status, round(BASE, 2) AS baseline_kg, round(AVAL_FU, 2) AS week24_kg, "
             f"round(PCHG, 2) AS pct_change, exclusion_reason, followup_target_date FROM {CS}.gold_endpoint_result "
             f"WHERE USUBJID = :u ORDER BY endpoint_version", {"u": u}, log, "The endpoint result per rule version")
    if trace == "amd1":
        r1 = next((r for r in res if r["endpoint_version"].endswith("R1")), {})
        r2 = next((r for r in res if r["endpoint_version"].endswith("R2")), {})
        take = (f"Under R1 (±7 days) the result is {r1.get('result_status')} ({r1.get('exclusion_reason') or 'no reason'}); "
                f"under R2 (±14 days) it is {r2.get('result_status')}, {r2.get('pct_change')}%.")
    else:
        r2 = next((r for r in res if r["endpoint_version"].endswith("R2")), {})
        take = (f"The lb weight is the selected Week 24 observation: {r2.get('baseline_kg')} kg → "
                f"{r2.get('week24_kg')} kg = {r2.get('pct_change')}% under {r2.get('endpoint_version')}.")
    return {"what": "Gold: every candidate observation with the engine's decision, and the result per rule version.",
            "takeaway": take, "source": f"{CS}.gold_endpoint_candidate · gold_endpoint_result",
            "sections": [{"label": "Endpoint results", "kind": "table", "rows": res},
                         {"label": "Candidates and decisions", "kind": "table", "rows": cand}]}


def _closure(u, log, trace):
    m = _mh_term(u)
    rows = _q(f"SELECT c.ancestor_code, c.ancestor_name, c.depth, r.class_id AS class_root_of FROM {STD}.mondo_closure c "
              f"LEFT JOIN {STD}.class_root r ON r.concept_id = c.ancestor_code AND r.kind = 'root' "
              f"WHERE c.descendant_code = :d AND c.depth > 0 ORDER BY c.depth, c.ancestor_code",
              {"d": m.get("CPL_MONDO_ID")}, log, "Every MONDO ancestor of the coded term (materialized closure)")
    hit = [r for r in rows if r["class_root_of"] == "EXCL-MH-V1"]
    take = (f"{m.get('CPL_MONDO_ID')} has {len(rows)} ancestors; "
            + (f"{hit[0]['ancestor_name']} ({hit[0]['ancestor_code']}, depth {hit[0]['depth']}) is a root of the "
               f"exclusionary-history class EXCL-MH-V1." if hit else "none is an EXCL-MH-V1 root."))
    return {"what": "The disease hierarchy, materialized: every ancestor of a code is one row away.", "takeaway": take,
            "source": f"{STD}.mondo_closure · class_root",
            "sections": [{"label": f"Ancestors of {m.get('CPL_MONDO_ID')} ({m.get('mondo_label')})", "kind": "table",
                          "rows": rows}]}


def _cohort(u, log, trace):
    crit = _q(f"SELECT criterion_id, criterion_type, outcome, detail FROM {CS}.gold_eligibility_criterion "
              f"WHERE USUBJID = :u ORDER BY criterion_type DESC, criterion_id", {"u": u}, log,
              "Every criterion, evaluated under the protocol version at screening")
    pop = _q(f"SELECT p.protocol_version, p.eligibility_rule_id, p.rule_eligible, p.edc_eligible, p.randomized, "
             f"p.FASFL, p.PPSFL, d.CPL_SCREEN_OUTCOME, d.CPL_SCREEN_FAIL_REASON FROM {CS}.gold_participant_population p "
             f"JOIN {CS}.silver_dm d USING (USUBJID) WHERE p.USUBJID = :u", {"u": u}, log, "The participant's outcome")
    p0 = pop[0] if pop else {}
    fails = [c["criterion_id"] for c in crit if c["outcome"] in ("TRIGGERED", "NOT_MET")]
    take = (f"Under {p0.get('eligibility_rule_id')}, {', '.join(fails) or 'nothing'} fails; the site recorded "
            f"{p0.get('CPL_SCREEN_OUTCOME')}" + (f" ({p0.get('CPL_SCREEN_FAIL_REASON')})" if p0.get("CPL_SCREEN_FAIL_REASON")
                                                 else "") + ".")
    return {"what": "Eligibility: each criterion evaluated from the coded history, plus what the site recorded.",
            "takeaway": take, "source": f"{CS}.gold_eligibility_criterion · gold_participant_population",
            "sections": [{"label": "Criteria", "kind": "table", "rows": crit},
                         {"label": "Outcome", "kind": "kv", "data": p0}]}


def _metric(u, log, trace):
    site = _q(f"SELECT STUDYID, SITEID, ARMCD FROM {CS}.silver_dm WHERE USUBJID = :u", {"u": u}, log, "Participant")[0]
    if trace == "lb":
        rows = _q(f"SELECT `Arm`, MEASURE(`Participants With Derived Endpoint`) AS derived, "
                  f"round(MEASURE(`Mean Percent Change`), 2) AS mean_pct_change FROM {SEM}.endpoint_result_metrics "
                  f"WHERE `Study` = :s AND `Rule Version` = 'EP-A-WT24.R2' GROUP BY ALL ORDER BY 1",
                  {"s": site["STUDYID"]}, log, "Governed measure: Mean Percent Change by arm (R2)")
        mine = next((r for r in rows if r["Arm"] == site["ARMCD"]), {})
        take = (f"This result is one of {mine.get('derived')} in arm {site['ARMCD']}, whose governed mean is "
                f"{mine.get('mean_pct_change')}% under EP-A-WT24.R2.")
    elif trace == "amd1":
        rows = _q(f"SELECT `Site`, MEASURE(`Participants Compared`) AS compared, "
                  f"MEASURE(`Participants Became Derivable`) AS became_derivable FROM {SEM}.amendment_impact_metrics "
                  f"GROUP BY ALL ORDER BY became_derivable DESC LIMIT 5", None, log,
                  "Governed measure: participants Amendment 1 made derivable, top sites")
        tot = _q(f"SELECT MEASURE(`Participants Became Derivable`) AS n FROM {SEM}.amendment_impact_metrics",
                 None, log, "All sites")[0]
        mine = next((r for r in rows if r["Site"] == site["SITEID"]), {})
        take = (f"Amendment 1 made {tot['n']} participants derivable, {mine.get('became_derivable', '—')} of them at "
                f"{site['SITEID']}, this participant's site.")
    else:
        rows = _q(f"SELECT `Site`, MEASURE(`Screened Participants`) AS screened, "
                  f"MEASURE(`Rule Eligible Participants`) AS rule_eligible, MEASURE(`Enrolled In Error`) AS enrolled_in_error "
                  f"FROM {SEM}.participant_population_metrics WHERE `Study` = :s AND `Site` = :t GROUP BY ALL",
                  {"s": site["STUDYID"], "t": site["SITEID"]}, log, "Governed measures for this participant's site")
        r = rows[0] if rows else {}
        take = (f"{site['SITEID']} screened {r.get('screened')}; {r.get('rule_eligible')} met every criterion. "
                f"Enrolled although the rules exclude them: {r.get('enrolled_in_error')}.")
    return {"what": "Semantic layer: the certified metric view this datum rolls into.", "takeaway": take,
            "source": SEM, "sections": [{"label": "Governed measure", "kind": "table", "rows": rows}]}


def _page(u, log, trace):
    from .stage_detail import genie_stage
    return genie_stage(_question(u, trace) + " Cite any ontology page you used.", log, DEMO)


def _rag(u, log, trace):
    from .rag import search  # the same Lakebase hybrid retriever as HEDIS, in the clinical_study corpus
    q = TRACES[trace]["rag_question"]
    r = search(q, corpus="clinical_study")
    log.append({"label": f"Hybrid retrieval over rag.chunks, corpus clinical_study ({r.get('mode')}, k=5)",
                "sql": f"search_documents(question={q!r}, k=5, corpus='clinical_study')"})
    rows = [{"document": x.get("title"), "section": x.get("section_path"),
             "score": round(float(x["score"]), 3) if x.get("score") is not None else None} for x in r.get("results", [])]
    top = (r.get("results") or [{}])[0]
    return {"what": "Unstructured context: study-document passages retrieved by meaning and keywords.",
            "takeaway": (f"RAG returns {len(rows)} passages (top: {top.get('title')}). It says what the rule is and "
                         f"where it's written; it can't evaluate this participant."),
            "source": "Lakebase rag.chunks · corpus clinical_study",
            "sections": [{"label": "The retrieval question", "kind": "quote", "text": q},
                         {"label": "Passages returned", "kind": "table", "rows": rows},
                         {"label": "Top passage", "kind": "quote",
                          "text": html.unescape(re.sub(r"\s+", " ", top.get("content") or ""))[:700]}]}


def _closure_ret(u, log, trace):
    if trace == "lb":
        rows = _q(f"SELECT e.subject AS dataset_variable, e.predicate, e.object AS ct_term, k.notation AS submission_value, "
                  f"k.label FROM {STD}.kb_edge e LEFT JOIN {STD}.kb_concept k ON k.concept_id = e.object "
                  f"WHERE e.subject = 'COSMOS_DSSVAR:WEIGHT.VSORRESU' AND e.predicate = 'cosmos:allowedValue' "
                  f"ORDER BY 4", None, log, "COSMoS WEIGHT specialization: the units VSORRESU may take")
        take = f"The WEIGHT specialization allows {', '.join(str(r['submission_value']) for r in rows)} for VSORRESU."
        secs = [{"label": "Allowed units (COSMoS DSS WEIGHT → CDISC CT)", "kind": "table", "rows": rows}]
    elif trace == "amd1":
        rv = _q(f"SELECT endpoint_version, protocol_version, sap_version, window_half_width_days, target_offset_days, "
                f"tie_breaker, review_state, approved_on, source_document, source_section FROM {STD}.rule_version "
                f"WHERE endpoint_id = 'EP-A-WT24' ORDER BY 1", None, log, "The two approved rule versions")
        sv = _q(f"SELECT protocol_version, sap_version, effective_date, amendment, change_summary FROM {STD}.study_version "
                f"WHERE study_id = 'CSL-A' ORDER BY effective_date", None, log, "CSL-A study versions")
        asr = _q(f"SELECT document_id, section_number, value, review_state, review_note FROM {CS}.rule_assertion "
                 f"WHERE assertion_type = 'FOLLOWUP_WINDOW_HALF_WIDTH' ORDER BY document_id", None, log,
                 "Window statements extracted from the documents, with their review state")
        take = ("R1 (±7, SAP 1.0) and R2 (±14, SAP 2.0) are both approved and both derived for everyone; the "
                "document statements behind them carry a review state.")
        secs = [{"label": "Rule versions", "kind": "table", "rows": rv},
                {"label": "Study versions", "kind": "table", "rows": sv},
                {"label": "Reviewed document assertions", "kind": "table", "rows": asr}]
    else:
        m = _mh_term(u)
        rows = _q(f"SELECT r.class_id, r.concept_id AS root, k.label AS root_label, c.depth FROM {STD}.class_root r "
                  f"JOIN {STD}.mondo_closure c ON c.ancestor_code = r.concept_id AND c.descendant_code = :d "
                  f"LEFT JOIN {STD}.kb_concept k ON k.concept_id = r.concept_id WHERE r.kind IN ('root', 'exclude_root')",
                  {"d": m.get("CPL_MONDO_ID")}, log, "Class membership as one fixed-shape join (class_root × closure)")
        take = (f"One join answers membership: {m.get('CPL_MONDO_ID')} is under "
                + (", ".join(f"{r['class_id']} root {r['root_label']}" for r in rows) or "no class root") + ".")
        secs = [{"label": "Classes the term belongs to", "kind": "table", "rows": rows}]
    return {"what": "Structured context: standards and rule tables queried with fixed-shape joins.", "takeaway": take,
            "source": STD, "sections": secs}


def _graph_out(subject: str, log, label: str) -> list[dict]:
    return _q(f"SELECT predicate, object FROM {G} WHERE subject = :s AND predicate NOT LIKE '%rdf-syntax-ns#type' "
              f"ORDER BY predicate", {"s": subject}, log, label)


def _ontobricks(u, log, trace):
    if trace in ("lb", "amd1"):
        rows = []
        for rv in ("R1", "R2"):
            res = f"{NS}EndpointResult/{u}.EP-A-WT24.{rv}"
            for r in _graph_out(res, log, f"EndpointResult {rv} in the graph"):
                rows.append({"node": _short(res), "predicate": _short(r["predicate"]), "object": _short(r["object"])})
        fu = next((r["object"] for r in rows if r["predicate"] == "usesFollowupObservation"
                   and r["node"].endswith("R2")), None)
        obs = [{"predicate": _short(r["predicate"]), "object": _short(r["object"])}
               for r in _graph_out(f"{NS}{fu}", log, "The Week 24 observation node")] if fu else []
        secs = [{"label": "The participant's endpoint results (live triples)", "kind": "table", "rows": rows},
                {"label": f"{fu or 'Follow-up observation'}", "kind": "table", "rows": obs}]
        if trace == "amd1":
            rvs = []
            for rv in ("R1", "R2"):
                for r in _graph_out(f"{NS}EndpointRuleVersion/EP-A-WT24.{rv}", log, f"Rule version {rv}"):
                    if _short(r["predicate"]) in ("windowHalfWidthDays", "amends", "appliesTo", "reviewState"):
                        rvs.append({"rule": f"EP-A-WT24.{rv}", "predicate": _short(r["predicate"]),
                                    "object": _short(r["object"])})
            secs.insert(0, {"label": "The two rule versions", "kind": "table", "rows": rvs})
            take = "The graph holds both rule versions (R2 amends R1) and both of the participant's results."
        else:
            unit = next((o["object"] for o in obs if o["predicate"] == "rawUnit"), "—")
            kg = next((o["object"] for o in obs if o["predicate"] == "standardValueKg"), "—")
            take = f"The graph holds the observation with its raw unit ({unit}) and the standardized value ({_num(kg, 2)} kg)."
        return {"what": "The published ClinicalStudyLab graph, queried live.", "takeaway": take,
                "source": G, "sections": secs}
    # mh: walk subClassOf from the coded term until a root of the exclusion class
    m = _mh_term(u)
    rec = f"{NS}MedicalHistoryRecord/{m.get('CPL_SOURCE_RECORD_ID')}"
    coded = _q(f"SELECT object FROM {G} WHERE subject = :s AND predicate = '{NS}codedAs'", {"s": rec}, log,
               "MedicalHistoryRecord → codedAs → Disease")
    roots = {r["object"] for r in _q(f"SELECT object FROM {G} WHERE subject = '{NS}ConceptClass/EXCL-MH-V1' "
                                     f"AND predicate = '{NS}hasRoot'", None, log, "EXCL-MH-V1 → hasRoot")}
    path, node, seen = [], coded[0]["object"] if coded else None, set()
    while node and node not in seen and len(path) < 10:
        seen.add(node)
        path.append(node)
        if node in roots:
            break
        up = _q(f"SELECT object FROM {G} WHERE subject = :s AND predicate = '{NS}subClassOf' ORDER BY object",
                {"s": node}, log, f"subClassOf from {_short(node)}")
        nxt = next((x["object"] for x in up if x["object"] in roots), None) or (up[0]["object"] if up else None)
        node = nxt
    hit = path[-1] in roots if path else False
    return {"what": "The published ClinicalStudyLab graph: the record, its code, and a subClassOf walk at query time.",
            "takeaway": ((f"From the record, codedAs → {_short(path[0])}, then subClassOf to {_short(path[-1])}, "
                          f"a root of EXCL-MH-V1: the graph reaches the exclusion itself.") if hit else
                         "The walk did not reach an EXCL-MH-V1 root in this graph version."),
            "source": G,
            "sections": [{"label": "The walk", "kind": "table",
                          "rows": [{"step": i, "node": _short(n), "is exclusion root": "✓" if n in roots else ""}
                                   for i, n in enumerate([rec] + path)]}]}


_STAGES = {"protocol": ("Source — study documents", _protocol), "raw": ("Source — EDC export", _raw),
           "bronze": ("Bronze — landed rows", _bronze), "silver": ("Silver — SDTM-shaped", _silver),
           "closure": ("Terminology — MONDO hierarchy", _closure), "cohort": ("Eligibility — criteria", _cohort),
           "gold": ("Gold — endpoint derivation", _gold), "metric": ("Semantic — certified metric view", _metric),
           "page": ("Retrieval — Genie Ontology (live Genie One run)", _page),
           "rag": ("Retrieval — RAG index (Lakebase)", _rag),
           "closure_ret": ("Retrieval — standards + rule tables", _closure_ret),
           "ontobricks": ("Retrieval — Ontobricks graph (live)", _ontobricks)}


@router.get("/{usubjid}/stage/{key}")
def stage(usubjid: str, key: str, trace: str = "lb"):
    t = _check(usubjid, trace)
    if key not in t["stages"]:
        raise HTTPException(404, f"stage {key!r} is not part of trace {trace!r}")
    title, fn = _STAGES[key]
    log: list = []
    t0 = time.time()
    try:
        out = fn(usubjid, log, trace)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 — surface the real failure to the click-in
        raise HTTPException(502, f"{key} retrieval failed: {type(e).__name__}: {str(e)[:300]}")
    return {"demo_id": DEMO, "key": key, "title": title, "patient_id": usubjid, "trace": trace, "queries": log,
            "latency_s": round(time.time() - t0, 2), **out}


# ------------------------------------------------------------------------------------------------ journey
def _st(key, concept, short, note=""):
    return {"key": key, "title": _STAGES[key][0], "semantic_concept": concept, "status": "live", "data": {},
            "note": note, "short": short, "detail": concept}


def _claim(cid, before, chip, kind, stage_path, modes, suffix=None):
    c = {"id": cid, "before": before, "chip": chip, "kind": kind, "stage_path": stage_path, "modes": modes}
    if suffix:
        c["suffix"] = suffix
    return c


def _answer(u: str, trace: str) -> tuple[list, dict]:
    if trace == "lb":
        f = _followup(u, "R2")
        r = run_sql(f"SELECT round(BASE, 2) AS b, round(AVAL_FU, 2) AS w, round(PCHG, 2) AS p FROM {CS}.gold_endpoint_result "
                    f"WHERE USUBJID = :u AND endpoint_version = 'EP-A-WT24.R2'", {"u": u})[0]
        claims = [
            _claim("raw", f"{u}'s Week 24 weight was keyed as ", f"{f.get('VSORRES')} {f.get('CPL_RAW_UNIT')}", "evidence",
                   ["raw", "bronze"], []),
            _claim("unit", ", mapped to the CDISC unit ", f"{f.get('VSORRESU')} = {_num(f.get('VSSTRESN'), 2)} kg",
                   "definition", ["silver", "protocol", "closure_ret"], ["closure", "rag", "genie_ontology", "graph"]),
            _claim("selected", ". It is the observation the rule selects: ",
                   f"{f.get('visit')}, {f.get('days_from_target')} days from target", "evidence", ["gold"], ["graph"]),
            _claim("result", ", giving ", f"{r['b']} → {r['w']} kg = {r['p']}% under EP-A-WT24.R2", "verdict",
                   ["gold", "metric"], ["metric_view", "genie_ontology", "graph"], suffix="."),
        ]
        summary = {"protocol": "DMS §2.2 · SAP §9.4.1", "raw": f"“{f.get('VSORRES')} {f.get('CPL_RAW_UNIT')}”",
                   "bronze": f"{f.get('VSORRES')} {f.get('CPL_RAW_UNIT')} (text)",
                   "silver": f"{f.get('VSORRESU')} → {_num(f.get('VSSTRESN'), 2)} kg", "gold": f"{r['p']}% (R2)",
                   "metric": "Mean % change by arm", "closure_ret": "allowed units", "ontobricks": "observation node"}
    elif trace == "amd1":
        f1, f2 = _followup(u, "R1"), _followup(u, "R2")
        res = {x["endpoint_version"]: x for x in run_sql(
            f"SELECT endpoint_version, result_status, round(PCHG, 2) AS p FROM {CS}.gold_endpoint_result "
            f"WHERE USUBJID = :u", {"u": u})}
        r1, r2 = res.get("EP-A-WT24.R1", {}), res.get("EP-A-WT24.R2", {})
        claims = [
            _claim("visit", f"{u}'s Week 24 visit was ", f"{f2.get('days_from_target')} days after the target date",
                   "evidence", ["silver", "bronze"], ["graph"]),
            _claim("r1", ". Under the original ±7-day rule it ", f"{f1.get('decision', '').lower()} ({f1.get('reason')})",
                   "verdict", ["gold", "closure_ret"], ["closure", "graph"]),
            _claim("amd", "; Amendment 1 (effective 2025-10-27) ", "widened the window to ±14 days", "definition",
                   ["protocol", "closure_ret"], ["rag", "genie_ontology", "closure", "graph"]),
            _claim("r2", ", so under R2 it is ", f"{r2.get('result_status')} at {r2.get('p')}%", "verdict",
                   ["gold", "metric"], ["metric_view", "genie_ontology", "graph"], suffix="."),
        ]
        summary = {"protocol": "AMD1 §1 · SAP 1.0 / 2.0", "bronze": f"{f2.get('visit')} {str(f2.get('vsdtc'))[:10]}",
                   "silver": f"study day {f2.get('VSDY')}", "gold": f"R1 {r1.get('result_status')} · R2 {r2.get('result_status')}",
                   "metric": "Participants Became Derivable", "closure_ret": "R1 ±7 · R2 ±14", "ontobricks": "R2 amends R1"}
    else:
        m = _mh_term(u)
        root = f"{m.get('root_label')} ({m.get('root_code')})" if m.get("root_code") else "—"
        pop = run_sql(f"SELECT d.CPL_SCREEN_OUTCOME AS o FROM {CS}.silver_dm d WHERE d.USUBJID = :u", {"u": u})
        claims = [
            _claim("term", f"{u}'s history records ", repr(m.get("MHTERM")), "evidence", ["raw", "bronze"], []),
            _claim("code", ", coded ", f"{m.get('CPL_MONDO_ID')} ({m.get('mondo_label')})", "code", ["silver"],
                   ["closure", "graph"]),
            _claim("sub", ", which is_a ", root, "subsumption", ["closure", "closure_ret"],
                   ["closure", "graph", "genie_ontology"]),
            _claim("excl", ", a root of the exclusionary history: ", "EXC-MH triggered", "verdict",
                   ["cohort", "protocol"], ["closure", "graph", "rag", "genie_ontology"]),
            _claim("outcome", ". The site recorded ", str((pop or [{}])[0].get("o")), "evidence", ["cohort"],
                   ["metric_view", "genie_ontology"], suffix="."),
        ]
        summary = {"protocol": "PROT §5.2", "raw": f"“{m.get('MHTERM')}”", "bronze": str(m.get("MHTERM")),
                   "silver": str(m.get("CPL_MONDO_ID")), "closure": f"⊑ {root}", "cohort": "EXC-MH triggered",
                   "metric": "screened / eligible by site", "closure_ret": "class_root × closure",
                   "ontobricks": "codedAs → subClassOf*"}
    return claims, summary


@router.get("/{usubjid}/journey")
def journey(usubjid: str, trace: str = "lb"):
    t = _check(usubjid, trace)
    if not run_sql(f"SELECT 1 FROM {CS}.silver_dm WHERE USUBJID = :u", {"u": usubjid}):
        raise HTTPException(404, f"Unknown participant {usubjid}")
    concept = {
        "protocol": ("the approved study documents", "Study documents"),
        "raw": ("the EDC export as delivered (CSV)", "EDC export"),
        "bronze": ("the export landed as text", "Landed rows"),
        "silver": ("SDTM-shaped, CDISC-coded", "SDTM" if trace != "mh" else "Coded history"),
        "closure": ("every MONDO ancestor of the code", "MONDO hierarchy"),
        "cohort": ("each criterion, from the coded history", "Eligibility"),
        "gold": ("candidates, decisions, results per rule version", "Endpoint derivation"),
        "metric": ("the certified metric view", "Certified metric view"),
        "page": ("Pages, inferred snippets, metadata (live)", "Genie Ontology"),
        "rag": ("study-document passages in Lakebase", "RAG index"),
        "closure_ret": ("standards and rule tables, fixed joins", "Standards + rule tables"),
        "ontobricks": ("the published ClinicalStudyLab graph", "Ontobricks graph"),
    }
    claims, summary = _answer(usubjid, trace)
    stages = []
    for k in t["stages"]:
        s = _st(k, concept[k][0], concept[k][1])
        s["summary"] = summary.get(k, {"page": "live Genie One trace", "rag": "study passages"}.get(k, ""))
        stages.append(s)
    return {"demo_id": DEMO, "patient_id": usubjid, "trace": trace, "measurement_year": None, "stages": stages,
            "answer": {"question": _question(usubjid, trace), "claims": claims}}
