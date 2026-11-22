"""The Tracer Journey API: three pieces of information, each followed through every layer (server/traces.py).

  GET /api/tracers                          the three traces, each with its hero patient (picked from the data)
  GET /api/patient/{pid}/journey?trace=     the stages that trace passes through + an answer whose every claim
                                            links back to the stages and retrieval modes that hold it

Stage contents are retrieved live on click (routes/stage_detail.py, same ?trace=). This module only lays out the
spine and composes the answer from real rows.
"""
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException

from .. import traces
from ..config import CATALOG, MEASUREMENT_YEAR, SCHEMA, SCHEMA_SEMANTIC, SCHEMA_TERM
from ..warehouse import run_sql

router = APIRouter()

C, S, SM, ST = CATALOG, SCHEMA, SCHEMA_SEMANTIC, SCHEMA_TERM
_hero_cache: dict = {"t": 0.0, "v": None}


def _hero(key: str) -> dict | None:
    rows = run_sql(traces.TRACES[key]["hero_sql"])
    return rows[0] if rows else None


@router.get("/tracers")
def list_tracers():
    """The three traces with their hero patients (cached 10 minutes; the hero queries scan gold)."""
    if not _hero_cache["v"] or time.time() - _hero_cache["t"] > 600:
        with ThreadPoolExecutor(max_workers=3) as ex:
            heroes = dict(zip(traces.TRACES, ex.map(_hero, traces.TRACES)))
        out = []
        for key, t in traces.TRACES.items():
            h = heroes[key]
            if not h:
                continue  # no qualifying patient in the current data: leave the trace out rather than fake one
            out.append({"trace": key, "title": t["title"], "summary": t["summary"], "patient_id": h["patient_id"],
                        "chips": t["chips"](h), "question": t["question"](h)})
        _hero_cache.update(t=time.time(), v=out)
    return {"measurement_year": MEASUREMENT_YEAR, "traces": _hero_cache["v"]}


def _stage(key, title, concept, status, data, note=""):
    return {"key": key, "title": title, "semantic_concept": concept, "status": status, "data": data, "note": note}


def _claim(cid, before, chip, kind, stage_path, modes, suffix=None):
    c = {"id": cid, "before": before, "chip": chip, "kind": kind, "stage_path": stage_path, "modes": modes}
    if suffix:
        c["suffix"] = suffix
    return c


def _pct(x) -> str:
    try:
        f = float(x)
        return f"{f * 100:.0f}%" if f <= 1 else f"{f:.0f}%"
    except (TypeError, ValueError):
        return "—"


def _answer_a1c(pid: str, my: int) -> dict:
    p = {"pid": pid, "my": my}
    g = run_sql(f"""SELECT evidence_value, evidence_datetime, evidence_code, clinic_id FROM {C}.{S}.gold_adherence_gsd
                    WHERE patient_id = :pid AND measurement_year = :my""", p)
    g0 = g[0] if g else {}
    step = run_sql(f"""SELECT followup_within_90d, window_closed, followup_days FROM {C}.{S}.gold_protocol_adherence
                       WHERE patient_id = :pid AND trigger_ts = :ts""",
                   {"pid": pid, "ts": g0.get("evidence_datetime")}) if g0.get("evidence_datetime") else []
    s0 = step[0] if step else {}
    clinic = g0.get("clinic_id")
    rate = run_sql(f"""SELECT MEASURE(`GSD Compliance Rate`) AS rate, MEASURE(`Poor Control Rate`) AS poor
                       FROM {C}.{SM}.gsd_compliance_metrics WHERE `Clinic` = :c AND `Measurement Year` = :my""",
                   {"c": clinic, "my": my}) if clinic else []
    r0 = rate[0] if rate else {}
    v, d = g0.get("evidence_value"), str(g0.get("evidence_datetime") or "")[:10]
    tested, poor = v is not None, v is not None and float(v) > 9.0
    if s0.get("followup_within_90d") in (True, "true"):
        step_txt = f"a recheck followed within 90 days ({s0.get('followup_days')} days): Step 3 met"
    elif s0.get("window_closed") in (True, "true"):
        step_txt = "the 90-day window closed with no recheck: Step 3 not met"
    else:
        step_txt = "the 90-day recheck window is still open"
    claims = [
        _claim("verdict", f"Patient {pid[:8]} ", "meets GSD" if tested else "has a GSD care gap", "verdict",
               ["metric", "gold", "silver", "bronze", "protocol"], ["genie_ontology", "graph"]),
        _claim("evidence", " because an A1c test was recorded in MY" + str(my) + " — ", f"{v}% on {d}", "evidence",
               ["gold", "silver", "bronze", "raw"], ["genie_ontology", "graph"]),
    ]
    if poor:
        claims.append(_claim("poor", ". That value is ", "poor control (A1c > 9%)", "definition",
                             ["metric", "protocol"], ["metric_view", "rag", "genie_ontology", "closure", "graph"]))
        claims.append(_claim("step3", ", which triggers Protocol Step 3; ", step_txt, "evidence",
                             ["gold", "metric", "protocol"], ["metric_view", "rag", "genie_ontology"]))
    if r0:
        claims.append(_claim("rate", ". It rolls into ", f"{clinic}: GSD {_pct(r0.get('rate'))}, poor control "
                             f"{_pct(r0.get('poor'))}", "rate", ["metric", "gold"], ["metric_view", "genie_ontology"]))
    claims.append(_claim("definition", ". Defined by the ", "care protocol CP-GLY-1 and the GSD spec", "definition",
                         ["protocol"], ["rag", "genie_ontology"], suffix="."))
    step_short = ("Step 3 met" if s0.get("followup_within_90d") in (True, "true")
                  else "Step 3 not met" if s0.get("window_closed") in (True, "true") else "Step 3 open")
    summary = {"protocol": "CP-GLY-1 · GSD spec", "raw": "Synthea lab rows", "bronze": f"A1c “{v}” (text)",
               "silver": f"A1c {v}% · {g0.get('evidence_code')}", "gold": f"A1c {v}% · Step-3 trigger" if poor else f"A1c {v}%",
               "metric": f"GSD {'MET' if tested else 'NOT_MET'} · {'poor control · ' if poor else ''}{step_short}",
               "closure_ret": f"{g0.get('evidence_code')} → thresholds", "ontobricks": "observation + thresholds"}
    return {"question": None, "claims": claims, "summary": summary}


def _answer_dx(pid: str, my: int) -> dict:
    code = traces.DX_CODE
    parents = run_sql(f"SELECT parent_code FROM {C}.{ST}.icd10_hier WHERE code = :c ORDER BY 1", {"c": code})
    vsets = run_sql(f"""SELECT DISTINCT v.segment_id, v.code FROM {C}.{ST}.icd10_closure c
                        JOIN {C}.{ST}.value_set_segment v ON v.code = c.ancestor_code AND v.code_system = 'ICD10CM'
                        WHERE c.descendant_code = :c ORDER BY 1""", {"c": code})
    union = " UNION ALL ".join(f"SELECT '{m}' AS m FROM {C}.{S}.gold_adherence_{m.lower()} "
                               f"WHERE patient_id = :pid AND measurement_year = :my"
                               for m in ("GSD", "KED", "BPD", "SPD", "EED", "MAD"))
    measures = sorted({r["m"] for r in run_sql(union, {"pid": pid, "my": my})})
    recs = run_sql(f"""SELECT DISTINCT e.subject, e.object FROM {C}.{ST}.protocol_edges e
                       WHERE e.predicate = 'recommendedFor' AND e.object IN
                         (SELECT v.segment_id FROM {C}.{ST}.icd10_closure c
                          JOIN {C}.{ST}.value_set_segment v ON v.code = c.ancestor_code AND v.code_system = 'ICD10CM'
                          WHERE c.descendant_code = :c) ORDER BY 1""", {"c": code})
    pars = " and ".join(r["parent_code"] for r in parents)
    claims = [
        _claim("code", f"Patient {pid[:8]} is coded ", code, "code", ["bronze", "silver", "raw"], []),
        _claim("subsumption", ", which has two parents in ICD-10: ", pars or "—", "subsumption",
               ["closure", "silver"], ["closure", "graph", "genie_ontology"]),
        _claim("cohorts", ". Through them it is in the value sets ",
               ", ".join(sorted({r["segment_id"] for r in vsets})) or "—", "subsumption",
               ["closure", "cohort"], ["closure", "graph"]),
        _claim("measures", ", so the patient is in the denominators of ", ", ".join(measures) or "—", "verdict",
               ["cohort", "closure"], ["genie_ontology", "graph"]),
    ]
    if recs:
        claims.append(_claim("rec", ". The protocol recommends ",
                             "; ".join(f"{r['subject'].replace('DRUGCLASS-', '')} for {r['object']}" for r in recs),
                             "definition", ["closure_ret", "protocol"], ["closure", "rag", "genie_ontology", "graph"],
                             suffix="."))
    nvs = len({r["segment_id"] for r in vsets})
    summary = {"protocol": "§1 Scope · descendants", "raw": "Synthea SNOMED rows", "bronze": code, "silver": code,
               "closure": f"{code} → {', '.join(r['parent_code'] for r in parents)}",
               "cohort": f"{nvs} value sets · {len(measures)} measures",
               "closure_ret": "; ".join(f"{r['subject'].replace('DRUGCLASS-', '')} → {r['object']}" for r in recs) or "—",
               "ontobricks": "subClassOf* walk + value sets"}
    return {"question": None, "claims": claims, "summary": summary}


def _answer_rule(pid: str, my: int) -> dict:
    med = run_sql(f"""SELECT max_by(m.description, m.start_ts) AS drug, max(m.start_ts) AS since
                      FROM {C}.{S}.bronze_order_med m
                      JOIN {C}.{ST}.rxnorm_closure c ON c.descendant_code = m.rxnorm_code
                                                     AND c.ancestor_code = 'DRUGCLASS-BIGUANIDE'
                      WHERE m.patient_id = :pid""", {"pid": pid})
    eg = run_sql(f"""SELECT max_by(value_num, result_ts) AS v, max(result_ts) AS ts, max_by(loinc_code, result_ts) AS code
                     FROM {C}.{S}.silver_observation WHERE patient_id = :pid AND loinc_code IN {traces.EGFR_CODES}""",
                 {"pid": pid})
    rule = run_sql(f"""SELECT e.value, e.source FROM {C}.{ST}.protocol_edges e WHERE e.subject = 'DRUGCLASS-BIGUANIDE'
                       AND e.predicate = 'contraindicatedWhen' AND e.object = 'eGFR_LT_30'""")
    m0, e0, r0 = (med or [{}])[0], (eg or [{}])[0], (rule or [{}])[0]
    conflict = e0.get("v") is not None and r0.get("value") is not None and float(e0["v"]) < float(r0["value"])
    claims = [
        _claim("code", f"Patient {pid[:8]} is on ", str(m0.get("drug") or "—"), "code", ["bronze", "silver"], []),
        _claim("subsumption", ", a ", "biguanide (metformin)", "subsumption", ["closure_ret"],
               ["closure", "genie_ontology"]),
        _claim("evidence", ". Their latest eGFR is ", f"{e0.get('v')} on {str(e0.get('ts'))[:10]} ({e0.get('code')})",
               "evidence", ["silver", "bronze"], ["genie_ontology", "graph"]),
        _claim("definition", ". The care protocol says ",
               f"metformin is contraindicated when eGFR < {r0.get('value')} ({r0.get('source')})", "definition",
               ["protocol", "closure_ret"], ["rag", "genie_ontology", "closure", "graph"]),
        _claim("verdict", ", so this order ", "conflicts with the protocol" if conflict else "does not conflict",
               "verdict", ["closure_ret", "silver", "protocol"], ["closure", "genie_ontology"], suffix="."),
    ]
    summary = {"protocol": "CP-GLY-2 · eGFR < 30", "bronze": f"metformin order · eGFR “{e0.get('v')}”",
               "silver": f"eGFR {e0.get('v')} · {e0.get('code')}",
               "closure_ret": f"biguanide · eGFR < 30 → {'violated' if conflict else 'ok'}",
               "ontobricks": "rule + order"}
    return {"question": None, "claims": claims, "summary": summary}


_ANSWERS = {"a1c": _answer_a1c, "dx": _answer_dx, "rule": _answer_rule}


@router.get("/patient/{patient_id}/journey")
def patient_journey(patient_id: str, trace: str = "a1c"):
    if trace not in traces.TRACES:
        raise HTTPException(404, f"Unknown trace {trace!r}; known: {', '.join(traces.TRACES)}")
    t = traces.TRACES[trace]
    my = MEASUREMENT_YEAR
    exists = run_sql(f"SELECT count(*) AS n FROM {C}.{S}.bronze_patient WHERE patient_id = :pid", {"pid": patient_id})
    if not exists or int(exists[0]["n"]) == 0:
        raise HTTPException(404, f"Unknown patient {patient_id}")

    lab = {"a1c": "HbA1c results", "dx": "diagnosis codes", "rule": "metformin orders + eGFR results"}[trace]
    spec = {"a1c": "§2 GSD spec + CP-GLY-1 (A1c > 9% → recheck within 3 months)",
            "dx": "§1 Scope: E10 / E11 / E13 and ALL descendant codes",
            "rule": "CP-GLY-2: metformin contraindicated when eGFR < 30"}[trace]
    stages = {
        "protocol": _stage("protocol", "Source — care-protocol document", spec, "doc", {},
                           "The source of meaning: the care-protocol document (the PDF in a UC volume, also the RAG "
                           "corpus). Every datum downstream is an instance of what it defines."),
        "raw": _stage("raw", "Source — raw EHR extract", "Synthea CSV: SNOMED conditions + LOINC observations", "live",
                      {}, "The extract as generated, before epicize maps SNOMED to ICD-10 and reshapes it into "
                          "Clarity tables."),
        "bronze": _stage("bronze", "Bronze — landed rows", f"Clarity-shaped {lab}, exactly as they arrived", "live",
                         {}, "Codes and values as landed: no meaning attached yet."),
        "silver": _stage("silver", "Silver — conformed",
                         "Conformed eGFR results: typed, LOINC-resolved" if trace == "rule"
                         else f"Conformed {lab}: typed, coded, deduplicated", "live", {},
                         "Bronze rows conformed into clean, typed, code-resolved records."),
        "closure": _stage("closure", "Terminology — ICD-10 hierarchy", f"{traces.DX_CODE}: parents and ancestors",
                          "live", {}, "The is-a hierarchy and its transitive closure: every ancestor of a code is "
                                      "one row away."),
        "cohort": _stage("cohort", "Cohort — value sets and denominators", "Which cohorts the code reaches", "live",
                         {}, "Membership earned by subsumption, not a hand-maintained list."),
        "gold": _stage("gold", "Gold — per-patient evidence", "GSD evidence row + the Step-3 trigger row", "live", {},
                       "Gold assembles the facts. The MET / NOT_MET rules are applied in the certified metric views."),
        "metric": _stage("metric", "Semantic — certified metric views", "gsd_compliance_metrics · "
                         "protocol_adherence_metrics", "live", {},
                         "The governed rules, read from the views' own definitions and executed on this patient."),
        "page": _stage("page", "Retrieval — Genie Ontology", "Pages, inferred snippets, metadata (live Genie One run)",
                       "live", {}, "What Genie One retrieves from the Genie Ontology for this trace's question."),
        "rag": _stage("rag", "Retrieval — RAG index", "Protocol passages in Lakebase (hybrid, doc-level RLS)", "live",
                      {}, "Unstructured context: the protocol text, retrieved by meaning and keywords."),
        "closure_ret": _stage("closure_ret", "Retrieval — closure + edge tables",
                              "icd10 / rxnorm closures, loinc_parts, value sets, protocol_edges", "live", {},
                              "Structured context: materialized hierarchies and typed edges, queried with "
                              "fixed-shape joins."),
        "ontobricks": _stage("ontobricks", "Retrieval — Ontobricks graph", "Published OWL triplestore (clinicaldomain)",
                             "live", {}, "The explicit graph: typed, cross-vocabulary edges traversed at query time."),
    }
    hero = next((h for h in list_tracers()["traces"] if h["trace"] == trace), None)
    answer = _ANSWERS[trace](patient_id, my)
    summary = answer.pop("summary", {})
    short = {"protocol": "Care protocol", "raw": "Raw EHR extract", "bronze": "Landed rows", "silver": "Conformed",
             "closure": "ICD-10 hierarchy", "cohort": "Value sets + denominators", "gold": "Patient evidence",
             "metric": "Certified metric views", "page": "Genie Ontology", "rag": "RAG index",
             "closure_ret": "Closure + edge tables", "ontobricks": "Ontobricks graph"}
    for k, st in stages.items():
        st["short"], st["detail"] = short[k], st["semantic_concept"]
        st["summary"] = summary.get(k, {"page": "live Genie One trace", "rag": "protocol passages"}.get(k, ""))
    answer["question"] = (hero["question"] if hero and hero["patient_id"] == patient_id
                          else f"Trace “{t['title']}” for patient {patient_id[:8]}")
    return {"patient_id": patient_id, "trace": trace, "measurement_year": my,
            "stages": [stages[k] for k in t["stages"]], "answer": answer}
