"""Tracer Journey — the RETRIEVED piece of one hero patient's journey at each Build stage (lazy, per click).

GET /api/patient/{patient_id}/stage/{key}  ->  what this layer did for THIS patient, retrieved live:

  protocol    the actual care-protocol passage (A4 RAG corpus chunk, from the PDF in the documents volume) +
              whether the rule applies to this patient
  bronze      raw rows as landed: encounter diagnoses (SNOMED as emitted, ICD-10 where mapped) + raw A1c results
  silver      what conformance did: N raw dx rows -> M conformed ICD-10 conditions; A1c typed + LOINC-resolved
  closure     the patient's ICD-10 ancestor CHAIN from the materialized closure (and how much one root covers)
  cohort      why the patient is in the denominator: cohort root + age vs each measure's eligibility window
  gold        the per-patient EVIDENCE row (no verdict) + proof the gold table carries no verdict column
  metric      the RULE retrieved from the certified metric view's own definition, executed on this patient's
              evidence, the clinic rollup it feeds, and its governance tags
  page        the Genie Ontology Page read live from the UC volume + the modeled metadata Genie indexes
  ontobricks  live triplestore: the patient's typed edges, the subClassOf* closure WALKED at query time, and the
              guideline edges for the patient's measures (with the graph's as-of date vs the live layer)

Every section is real query output; each response also returns the queries that produced it, so the click-in
shows HOW it was retrieved, not just a value.
"""
import html
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

import yaml
from fastapi import APIRouter, HTTPException

from ..config import (
    CATALOG, MEASUREMENT_YEAR, ONTOBRICKS_CATALOG, ONTOBRICKS_NS, ONTOBRICKS_SCHEMA, get_ontobricks_table,
    SCHEMA, SCHEMA_SEMANTIC, SCHEMA_TERM,
)
from .. import traces
from ..config import get_workspace_client
from ..warehouse import run_sql

router = APIRouter()

C, S, SM, ST = CATALOG, SCHEMA, SCHEMA_SEMANTIC, SCHEMA_TERM
NS = ONTOBRICKS_NS
A1C_CODES = f"(SELECT code FROM {C}.{ST}.value_set_segment WHERE segment_id = 'GSD_A1C_TEST')"
PAGES_VOL = f"/Volumes/{C}/{S}/ontology_pages"
MV_GSD = f"{C}.{SM}.gsd_compliance_metrics"
MV_STEP3 = f"{C}.{SM}.protocol_adherence_metrics"
EGFR = traces.EGFR_CODES

# Eligibility windows per measure (mirrors the gold denominators in src/pipelines/measures.py).
WINDOWS = [("GSD", "Glycemic Status Assessment", "18–75", "gold_adherence_gsd"),
           ("KED", "Kidney Health Evaluation", "18–85", "gold_adherence_ked"),
           ("BPD", "Blood Pressure Control", "18–75", "gold_adherence_bpd"),
           ("SPD", "Statin Therapy", "40–75", "gold_adherence_spd"),
           ("EED", "Eye Exam", "18–75", "gold_adherence_eed"),
           ("MAD", "Medication Adherence", "18+ with ≥2 fills", "gold_adherence_mad")]


# ---------------------------------------------------------------------------------------------------------------
def _q(sql: str, params: dict | None, log: list, label: str) -> list[dict]:
    """Run + record the query (shown in the click-in under 'How this was retrieved')."""
    log.append({"label": label, "sql": re.sub(r"\n\s+", "\n  ", sql.strip())})
    return run_sql(sql, params)


def _short(iri: str | None) -> str:
    if not iri:
        return ""
    s = iri[len(NS):] if iri.startswith(NS) else iri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
    if s.startswith("Patient/") and len(s) > 16:
        s = "Patient/" + s[len("Patient/"):][:8]
    return s


def _primary_dx(pid: str) -> dict:
    """Same 'primary diagnosis' the hero picker shows (lowest diabetes code with onset by MY end)."""
    r = run_sql(f"""SELECT MIN(icd10_code) FILTER (WHERE onset_date <= DATE'{MEASUREMENT_YEAR}-12-31') AS dx,
                           MIN(icd10_code) AS any_dx
                    FROM {C}.{S}.bronze_pat_enc_dx
                    WHERE patient_id = :pid AND (icd10_code LIKE 'E10%' OR icd10_code LIKE 'E11%'
                                                 OR icd10_code LIKE 'E13%')""", {"pid": pid})
    dx = (r[0]["dx"] or r[0]["any_dx"]) if r else None
    if not dx:
        raise HTTPException(404, f"No diabetes-coded encounter for patient {pid}")
    return {"dx": dx}


def _evidence(pid: str, my: int) -> dict:
    r = run_sql(f"""SELECT age, evidence_datetime, evidence_code, evidence_value, clinic_id, panel_id
                    FROM {C}.{S}.gold_adherence_gsd WHERE patient_id = :pid AND measurement_year = :my""",
                {"pid": pid, "my": my})
    return r[0] if r else {}


def _pct(x) -> str:
    try:
        f = float(x)
        return f"{f * 100:.1f}%" if f <= 1 else f"{f:.1f}%"
    except (TypeError, ValueError):
        return "—"


_DOC = os.path.join(os.path.dirname(__file__), "..", "protocol_docs", "diabetes_care_protocol.html")


def _inline(fragment: str) -> str:
    """HTML inline -> plain text with **bold** markers (the click-in renders bold)."""
    t = re.sub(r"<\s*(b|strong)\s*>(.*?)<\s*/\s*\1\s*>", r"**\2**", fragment, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def _protocol_doc(stop_section: str = "4.", row_prefix: str | None = "GSD",
                  rule_prefix: str | None = "**CP-GLY-1.**", para_has: str | None = None) -> list[dict]:
    """The care-protocol document up to `stop_section`, as blocks (heading / paragraph / table / rule), with the
    trace's own table row, rule or paragraph highlighted."""
    src = open(os.path.normpath(_DOC), encoding="utf-8").read()
    body = src[src.find("<h2"):]
    blocks: list[dict] = []
    for m in re.finditer(r"<h2[^>]*>(.*?)</h2>|<table>(.*?)</table>|<div class=\"rule\">(.*?)</div>|<p[^>]*>(.*?)</p>",
                         body, flags=re.S):
        h, tbl, rule, para = m.groups()
        if h is not None:
            title = _inline(h)
            if title.startswith(stop_section):
                break
            blocks.append({"type": "h", "text": title})
        elif tbl is not None:
            rows = []
            for tr in re.findall(r"<tr>(.*?)</tr>", tbl, flags=re.S):
                cells = [_inline(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, flags=re.S)]
                rows.append(cells)
            hi = [i for i, r in enumerate(rows)
                  if row_prefix and r and r[0].replace("*", "").startswith(row_prefix)]
            blocks.append({"type": "table", "rows": rows, "highlight_rows": hi})
        elif rule is not None:
            t = _inline(rule)
            blocks.append({"type": "rule", "text": t, "highlight": bool(rule_prefix) and t.startswith(rule_prefix)})
        elif para is not None:
            t = _inline(para)
            blocks.append({"type": "p", "text": t, **({"highlight": True} if para_has and para_has in t else {})})
    return blocks


# --------------------------------------------------- stages ----------------------------------------------------
_PROTO = {  # per trace: the passage to retrieve from the RAG corpus and what to highlight in the document
    "a1c": {"chunk": "%Glycemic Status%", "stop": "4.", "row": "GSD", "rule": "**CP-GLY-1.**", "para": None,
            "label": "the GSD specification"},
    "dx": {"chunk": "%descendant codes%", "stop": "2.", "row": None, "rule": None, "para": "descendant codes",
           "label": "§1 Scope"},
    "rule": {"chunk": "%contraindicated when eGFR%", "stop": "5.", "row": "Metformin", "rule": "**CP-GLY-2.**",
             "para": None, "label": "CP-GLY-2"},
}


def _latest_egfr(pid: str) -> dict:
    r = run_sql(f"""SELECT max_by(value_num, result_ts) AS v, max(result_ts) AS ts, max_by(loinc_code, result_ts) AS code
                    FROM {C}.{S}.silver_observation WHERE patient_id = :pid AND loinc_code IN {EGFR}""", {"pid": pid})
    return r[0] if r else {}


def _metformin(pid: str) -> dict:
    r = run_sql(f"""SELECT max_by(m.description, m.start_ts) AS drug, max_by(m.rxnorm_code, m.start_ts) AS rx,
                           max(m.start_ts) AS since
                    FROM {C}.{S}.care_order_med m
                    JOIN {C}.{ST}.rxnorm_closure c ON c.descendant_code = m.rxnorm_code
                                                   AND c.ancestor_code = 'DRUGCLASS-BIGUANIDE'
                    WHERE m.patient_id = :pid""", {"pid": pid})
    return r[0] if r and r[0].get("drug") else {}


def _protocol(pid, my, log, trace="a1c"):
    cfg = _PROTO.get(trace, _PROTO["a1c"])
    passage, meta, warn = None, {}, []
    try:
        from .rag import _AS_USER, _retriever  # the same A4 Lakebase retriever the RAG lens uses (RLS on)
        sql = ("SELECT d.title, c.section_path, c.page_start, c.content FROM rag.chunks c "
               "JOIN rag.documents d USING (document_id) WHERE d.title ILIKE %s AND c.content ILIKE %s "
               "ORDER BY c.page_start LIMIT 1")
        log.append({"label": f"Retrieve the chunk holding {cfg['label']} (A4 Lakebase RAG corpus, doc-level RLS)",
                    "sql": sql.replace("%s", "'Care Protocol%Comprehensive%'", 1).replace("%s", f"'{cfg['chunk']}'", 1)})
        rows = _retriever()._run(sql, ("Care Protocol%Comprehensive%", cfg["chunk"]), _AS_USER)
        if rows:
            r0 = rows[0]
            passage = html.unescape(re.sub(r"\s+", " ", r0["content"])).strip()
            meta = {"document": r0["title"], "section": r0["section_path"], "page": r0["page_start"],
                    "corpus": "rag.chunks (chunked from /Volumes/.../documents/pdf/diabetes_care_protocol.pdf)"}
    except Exception as e:  # noqa: BLE001 — say so rather than show a stale copy as if it were retrieved
        warn.append(f"RAG corpus unreachable ({type(e).__name__}); the retrieved chunk can't be shown.")
    if trace == "dx":
        code = traces.DX_CODE
        anc = [r["ancestor_code"] for r in run_sql(
            f"SELECT ancestor_code FROM {C}.{ST}.icd10_closure WHERE descendant_code = :c AND depth > 0 ORDER BY depth",
            {"c": code})]
        root = next((a for a in anc if a in ("E10", "E11", "E13")), None)
        applies = {"Code": f"{code} (type 2 diabetes with diabetic chronic kidney disease)",
                   "Scope rule": "E10 / E11 / E13 and all descendant codes",
                   "In scope": f"yes: {code} is a descendant of {root} (see Terminology)" if root else "no"}
        take = (f"§1 puts every descendant of E10 / E11 / E13 in scope, without listing them. {code} is in scope "
                f"through {root}.")
    elif trace == "rule":
        med, eg = _metformin(pid), _latest_egfr(pid)
        v = eg.get("v")
        hit = v is not None and float(v) < 30
        applies = {"Drug": f"{med.get('drug')} (RxNorm {med.get('rx')}), latest order {str(med.get('since'))[:10]}",
                   "Latest eGFR": f"{v} on {str(eg.get('ts'))[:10]} (LOINC {eg.get('code')})",
                   "Rule": "Metformin is contraindicated when eGFR < 30 mL/min/1.73m² (CP-GLY-2)",
                   "Applies": "yes: eGFR is below 30" if hit else "no"}
        take = (f"CP-GLY-2 contraindicates metformin below eGFR 30. Patient {pid[:8]} is on metformin with eGFR {v}"
                f"{', so the rule is violated' if hit else ''}.")
    else:
        ev = _evidence(pid, my)
        age, v = ev.get("age"), ev.get("evidence_value")
        in_window = age is not None and 18 <= int(age) <= 75
        applies = {"Age at end of MY": age, "GSD eligible window": "18–75",
                   "In scope": "yes" if in_window else "no",
                   "Latest A1c": f"{v}% on {str(ev.get('evidence_datetime'))[:10]}" if v is not None else "none",
                   "CP-GLY-1": "A1c > 9.0% is poorly controlled and triggers escalation within 3 months",
                   "MY2026 update": "Payer memo (MY2026): a CGM-derived GMI (LOINC 97506-0) also satisfies the GSD "
                                    "numerator; the protocol text is v2025.1, the value set carries the change"}
        take = (f"The protocol defines poor control as A1c > 9.0%, and GSD counts the last A1c of MY{my}. Patient "
                f"{pid[:8]} (age {age}) is in scope; their last A1c is {v}%.")
    return {
        "what": "The human-authored care protocol. Everything downstream is an instance of these definitions.",
        "takeaway": take,
        "source": meta.get("corpus"),
        "sections": [
            {"label": "CP-DM-2025.1, rendered from the PDF's version-controlled source", "kind": "doc",
             "blocks": _protocol_doc(cfg["stop"], cfg["row"], cfg["rule"], cfg["para"])},
            *([{"label": f"How the RAG index stores it: chunk from §{meta.get('section')}, p.{meta.get('page')}",
                "kind": "quote", "text": passage}] if passage else []),
            {"label": "Does this rule apply to this patient?", "kind": "kv", "data": applies},
        ],
        "warnings": warn,
    }


def _dx_order(trace: str) -> str:
    return ("(icd10_code = 'E11.22' OR icd10_code LIKE 'N18%') DESC, " if trace in ("dx", "rule")
            else "(icd10_code LIKE 'E1%') DESC, ")


def _bronze(pid, my, log, trace="a1c"):
    p = {"pid": pid, "my": my}
    stats = _q(f"""SELECT count(*) AS raw_rows, count(icd10_code) AS with_icd10, count(DISTINCT snomed_code) AS snomed_codes
                   FROM {C}.{S}.bronze_pat_enc_dx WHERE patient_id = :pid""", p, log, "Raw encounter-diagnosis rows")[0]
    dx = _q(f"""SELECT onset_date, encounter_id, snomed_code, icd10_code, description
                FROM {C}.{S}.bronze_pat_enc_dx WHERE patient_id = :pid
                ORDER BY {_dx_order(trace)}onset_date LIMIT 6""", p, log, "Sample raw diagnosis rows")
    dx_sec = {"label": "Encounter diagnoses (raw)", "kind": "table", "rows": dx}
    take = (f"{stats['raw_rows']} raw encounter-diagnosis rows ({stats['snomed_codes']} SNOMED concepts); "
            f"{stats['with_icd10']} carry an ICD-10 code (epicize's SNOMED → ICD-10 crosswalk).")
    if trace == "rule":
        meds = _q(f"""SELECT m.start_ts, m.stop_ts, m.rxnorm_code, m.description FROM {C}.{S}.bronze_order_med m
                      JOIN {C}.{ST}.rxnorm_closure c ON c.descendant_code = m.rxnorm_code
                                                     AND c.ancestor_code = 'DRUGCLASS-BIGUANIDE'
                      WHERE m.patient_id = :pid ORDER BY m.start_ts DESC LIMIT 6""", p, log,
                  "Metformin orders as landed (bronze_order_med, RxNorm clinical-drug codes)")
        labs = _q(f"""SELECT result_ts, loinc_code, description, value, units FROM {C}.{S}.bronze_order_results
                      WHERE patient_id = :pid AND loinc_code IN {EGFR} ORDER BY result_ts DESC LIMIT 6""", p, log,
                  "eGFR results as landed (bronze_order_results; value is text)")
        return {
            "what": "Clarity-shaped rows exactly as they landed: RxNorm orders and lab results, values stored as text.",
            "takeaway": (f"{len(meds)} recent metformin orders (RxNorm {meds[0]['rxnorm_code'] if meds else '—'}) and "
                         f"eGFR results as text. The lab reports CKD-EPI 2021 (98979-8) since 2022-07-01; older "
                         f"results carry MDRD (33914-3)."),
            "source": f"{C}.{S}.bronze_order_med · bronze_order_results",
            "sections": [{"label": "Metformin orders (raw)", "kind": "table", "rows": meds},
                         {"label": "eGFR results (raw, latest 6)", "kind": "table", "rows": labs}, dx_sec],
        }
    if trace == "dx":
        return {"what": "Clarity-shaped diagnosis rows exactly as they landed: SNOMED as emitted, ICD-10 where mapped.",
                "takeaway": take, "source": f"{C}.{S}.bronze_pat_enc_dx", "sections": [dx_sec]}
    a1c = _q(f"""SELECT result_ts, loinc_code, description, value, units FROM {C}.{S}.care_order_results
                 WHERE patient_id = :pid AND loinc_code IN {A1C_CODES} AND year(result_ts) = :my
                 ORDER BY result_ts DESC LIMIT 6""", p, log, "Raw HbA1c results landed in the measurement year")
    n_a1c = _q(f"""SELECT count(*) AS n FROM {C}.{S}.care_order_results
                   WHERE patient_id = :pid AND loinc_code IN {A1C_CODES} AND year(result_ts) = :my""",
               p, log, "Count raw HbA1c results")[0]["n"]
    return {
        "what": "Clarity-shaped rows exactly as they landed: SNOMED as emitted, values stored as text.",
        "takeaway": f"{n_a1c} raw HbA1c result{'' if str(n_a1c) == '1' else 's'} in MY{my}; the value is text. {take}",
        "source": f"{C}.{S}.care_order_results (landed lab feed: Clarity results + care-behavior events) · "
                  f"bronze_pat_enc_dx",
        "sections": [
            {"label": f"HbA1c results (raw, latest {len(a1c)} of {n_a1c})", "kind": "table", "rows": a1c,
             "empty": f"No HbA1c result landed in MY{my}: this is where a GSD care gap originates."},
            dx_sec,
        ],
    }


def _silver(pid, my, log, trace="a1c"):
    p = {"pid": pid, "my": my}
    raw = run_sql(f"SELECT count(*) AS n FROM {C}.{S}.bronze_pat_enc_dx WHERE patient_id = :pid", p)[0]["n"]
    cond = _q(f"""SELECT icd10_code, description, onset_date FROM {C}.{S}.silver_condition
                  WHERE patient_id = :pid ORDER BY {_dx_order(trace)}icd10_code""", p, log,
              "Conformed conditions (ICD-10)")
    cond_sec = {"label": f"Conformed conditions ({len(cond)})", "kind": "table", "rows": cond}
    if trace == "dx":
        return {"what": "Conformance: map to ICD-10, drop unmapped noise, one condition per code.",
                "takeaway": f"{raw} raw diagnosis rows → {len(cond)} conformed ICD-10 conditions, {traces.DX_CODE} among them.",
                "source": f"{C}.{S}.silver_condition", "sections": [cond_sec]}
    codes = EGFR if trace == "rule" else A1C_CODES
    obs = _q(f"""SELECT result_ts, loinc_code, value_num, units, description,
                        CASE WHEN encounter_id IS NULL THEN 'follow-up (care-behavior model)'
                             ELSE 'EHR encounter' END AS origin
                 FROM {C}.{S}.silver_observation
                 WHERE patient_id = :pid AND loinc_code IN {codes}
                   {'AND year(result_ts) = :my' if trace == 'a1c' else ''}
                 ORDER BY result_ts DESC LIMIT 8""", p, log,
             f"Conformed {'eGFR' if trace == 'rule' else 'HbA1c'} observations (typed value_num, LOINC-resolved)")
    if trace == "rule":
        fills = _q(f"""SELECT m.start_ts, m.stop_ts, m.rxnorm_code, m.description FROM {C}.{S}.care_order_med m
                       JOIN {C}.{ST}.rxnorm_closure c ON c.descendant_code = m.rxnorm_code
                                                      AND c.ancestor_code = 'DRUGCLASS-BIGUANIDE'
                       WHERE m.patient_id = :pid ORDER BY m.start_ts DESC LIMIT 6""", p, log,
                   "Metformin fills in the effective layer (care_order_med: 30-day fills, what the measures use)")
        return {"what": "Conformance: values typed to numbers, LOINC resolved; diabetes-drug orders become 30-day fills.",
                "takeaway": (f"eGFR typed to a number: latest {obs[0]['value_num'] if obs else '—'} "
                             f"({obs[0]['loinc_code'] if obs else '—'}). Metformin becomes 30-day fills in "
                             f"care_order_med (the care-behavior model's effective layer, which the measures read)."),
                "source": f"{C}.{S}.silver_observation · care_order_med · silver_condition",
                "sections": [{"label": "eGFR observations (typed value_num)", "kind": "table", "rows": obs},
                             {"label": "Metformin fills (effective layer)", "kind": "table", "rows": fills}, cond_sec]}
    modeled = sum(1 for r in obs if str(r.get("origin", "")).startswith("follow-up"))
    return {
        "what": "Conformance: map to ICD-10, drop unmapped noise, type values, resolve LOINC.",
        "takeaway": (f"HbA1c values typed to numbers; {raw} raw diagnosis rows → {len(cond)} conformed ICD-10 conditions"
                     f"{f'. {modeled} A1c is a protocol follow-up emitted by the care-behavior model' if modeled else ''}."),
        "source": f"{C}.{S}.silver_observation · silver_condition",
        "sections": [
            {"label": "HbA1c observations (typed value_num)", "kind": "table", "rows": obs,
             "empty": f"No conformed HbA1c in MY{my}."},
            cond_sec,
        ],
    }


def _trace_code(pid: str, trace: str) -> str:
    return traces.DX_CODE if trace == "dx" else _primary_dx(pid)["dx"]


def _routes(code: str, log: list) -> list[list[dict]]:
    """Every route from the code up to a root over the direct is-a edges (icd10_hier), root first."""
    rows = _q(f"""WITH RECURSIVE up (code, route) AS (
                    SELECT :c, :c
                    UNION ALL
                    SELECT h.parent_code, concat(u.route, '>', h.parent_code)
                    FROM up u JOIN {C}.{ST}.icd10_hier h ON h.code = u.code WHERE h.parent_code IS NOT NULL)
                  SELECT route FROM up u WHERE NOT EXISTS (
                    SELECT 1 FROM {C}.{ST}.icd10_hier h WHERE h.code = u.code AND h.parent_code IS NOT NULL)
                  ORDER BY route""", {"c": code}, log, "Every route up the direct is-a edges (icd10_hier, recursive)")
    codes = sorted({c for r in rows for c in r["route"].split(">")})
    names = {r["code"]: r["name"] for r in run_sql(
        f"SELECT code, name FROM {C}.{ST}.icd10_hier WHERE code IN ({', '.join(repr(c) for c in codes)})")} if codes else {}
    out = []
    for r in rows:
        path = r["route"].split(">")
        out.append([{"code": c, "name": names.get(c, ""), "depth": len(path) - 1 - k}
                    for k, c in enumerate(reversed(path))])
    return out


def _closure(pid, my, log, trace="a1c"):
    dx = _trace_code(pid, trace)
    anc = _q(f"""SELECT ancestor_code, ancestor_name, depth FROM {C}.{ST}.icd10_closure
                 WHERE descendant_code = :dx AND depth > 0 ORDER BY depth, ancestor_code""", {"dx": dx}, log,
             "Every ancestor of the code (icd10_closure: one equality on descendant_code)")
    routes = _routes(dx, log)
    parents = [r["ancestor_code"] for r in anc if int(r["depth"]) == 1]
    root = next((r["ancestor_code"] for r in anc if r["ancestor_code"] in ("E10", "E11", "E13")), None)
    covers = _q(f"SELECT count(*) AS n FROM {C}.{ST}.icd10_closure WHERE ancestor_code = :r",
                {"r": root}, log, f"How many codes the {root} root subsumes")[0]["n"] if root else 0
    route_txt = "; ".join(" → ".join(n["code"] for n in rt) for rt in routes)
    two = len(parents) > 1
    return {
        "what": "The is-a hierarchy (direct parents) and its pre-materialized transitive closure (every ancestor).",
        "takeaway": ((f"{dx} has {len(parents)} parents ({', '.join(parents)}), so it sits on {len(routes)} routes: "
                      f"{route_txt}. " if two else f"{dx} rolls up {route_txt}. ") +
                     f"The closure lists every ancestor ({', '.join(r['ancestor_code'] for r in anc)}), so one equality "
                     f"join (ancestor_code = '{root}') puts the patient in the diabetes cohort; {root} subsumes "
                     f"{covers} codes a flat list would have to enumerate."),
        "source": f"{C}.{ST}.icd10_hier · icd10_closure",
        "sections": [
            *[{"label": f"Route {k + 1} of {len(routes)} (root → code)", "kind": "chain", "nodes": rt}
              for k, rt in enumerate(routes)],
            {"label": "Closure rows for the code (ancestor, depth)", "kind": "table", "rows": anc},
        ],
    }


def _value_sets(code: str, log: list) -> list[dict]:
    return _q(f"""SELECT DISTINCT v.segment_id AS value_set, v.segment_name AS name, c.ancestor_code AS via_code,
                         c.depth
                  FROM {C}.{ST}.icd10_closure c
                  JOIN {C}.{ST}.value_set_segment v ON v.code = c.ancestor_code AND v.code_system = 'ICD10CM'
                  WHERE c.descendant_code = :c ORDER BY 1""", {"c": code}, log,
              "Value sets the code reaches through the closure (code or any ancestor listed)")


def _cohort(pid, my, log, trace="a1c"):
    p = {"pid": pid, "my": my}
    code = _trace_code(pid, trace)
    size = int(_q(f"SELECT count(*) AS n FROM {C}.{S}.silver_diabetes_cohort", None, log, "Diabetes cohort size")[0]["n"])
    age = _q(f"""SELECT CAST(datediff(DATE'{my}-12-31', birth_date) / 365.25 AS INT) AS age
                 FROM {C}.{S}.bronze_patient WHERE patient_id = :pid""", p, log, "Age at end of measurement year")
    age = age[0]["age"] if age else None
    union = " UNION ALL ".join(f"SELECT '{m}' AS m FROM {C}.{S}.{t} WHERE patient_id = :pid" for m, _, _, t in WINDOWS)
    elig = {r["m"] for r in _q(union, p, log, "Which measure denominators include this patient")}
    rows = [{"measure": m, "name": n, "eligible window": w, "eligible": "✓" if m in elig else "—"}
            for m, n, w, _ in WINDOWS]
    vsets = _value_sets(code, log)
    names = sorted({r["value_set"] for r in vsets})
    return {
        "what": "The denominators: value-set membership earned by subsumption × each measure's age window.",
        "takeaway": (f"{code} reaches {len(names)} value sets ({', '.join(names)}). The patient is in the "
                     f"{size:,}-patient diabetes cohort; age {age} → in {len(elig)} measure denominators "
                     f"({', '.join(m for m, *_ in WINDOWS if m in elig)})."),
        "source": f"{C}.{ST}.icd10_closure · value_set_segment · {C}.{S}.silver_diabetes_cohort",
        "sections": [{"label": f"Value sets {code} reaches", "kind": "table", "rows": vsets},
                     {"label": "Measure eligibility for this patient", "kind": "table", "rows": rows}],
    }


def _gold(pid, my, log, trace="a1c"):
    p = {"pid": pid, "my": my}
    row = _q(f"""SELECT measure_id, measurement_year, age, eligible_flag, evidence_datetime, evidence_code,
                        evidence_value, clinic_id, panel_id
                 FROM {C}.{S}.gold_adherence_gsd WHERE patient_id = :pid AND measurement_year = :my""",
             p, log, "This patient's GSD evidence row")
    cols = _q(f"""SELECT column_name FROM {C}.information_schema.columns
                  WHERE table_schema = '{S}' AND table_name = 'gold_adherence_gsd' ORDER BY ordinal_position""",
              None, log, "Gold table schema")
    names = [c["column_name"] for c in cols]
    has_verdict = any(n in names for n in ("status", "numerator_flag", "gap_reason"))
    ev = row[0] if row else {}
    warns = []
    if ev.get("evidence_datetime"):
        obs = run_sql(f"""SELECT value_num FROM {C}.{S}.silver_observation WHERE patient_id = :pid
                          AND result_ts = :ts AND loinc_code IN {A1C_CODES} LIMIT 1""",
                      {"pid": pid, "ts": ev["evidence_datetime"]})
        seen = obs[0]["value_num"] if obs else None
        if seen is not None and float(seen) != float(ev["evidence_value"]):
            warns.append(f"Gold's evidence_value ({ev['evidence_value']}%) is the care-behavior model's MODELED "
                         f"A1c, not the observed result on {str(ev['evidence_datetime'])[:10]} ({seen}%). The "
                         f"synthetic A1c stream isn't calibrated to the patient's control status yet.")
    ev_txt = (f"latest HbA1c {ev.get('evidence_value')}% on {str(ev.get('evidence_datetime'))[:10]}"
              if ev.get("evidence_datetime") else f"no HbA1c in MY{my}")
    trig = _q(f"""SELECT measure_id, trigger_ts, trigger_a1c, followup_ts, followup_days, followup_within_90d,
                         window_closed FROM {C}.{S}.gold_protocol_adherence
                  WHERE patient_id = :pid AND trigger_ts = :ts""",
              {"pid": pid, "ts": ev.get("evidence_datetime")}, log,
              "The Step-3 trigger row for the same A1c (gold_protocol_adherence)") if ev.get("evidence_datetime") else []
    return {
        "what": "One evidence row per eligible patient — facts only. The verdict is NOT computed here.",
        "takeaway": f"Gold assembled the evidence: {ev_txt}"
                    f"{'. The same A1c is a Step-3 trigger (A1c > 9%)' if trig else ''}. "
                    f"{'⚠ gold still carries a verdict column' if has_verdict else 'No status / numerator column exists in gold — the rule is applied in the metric view.'}",
        "source": f"{C}.{S}.gold_adherence_gsd",
        "sections": [
            {"label": "GSD evidence row (gold_adherence_gsd)", "kind": "kv", "data": ev},
            *([{"label": "Step-3 trigger row for the same A1c (gold_protocol_adherence)", "kind": "kv",
                "data": trig[0]}] if trig else []),
            {"label": "GSD gold columns (no verdict)", "kind": "chips", "items": names},
        ],
        "warnings": warns,
    }


def _mv_spec(fqn: str, log: list) -> tuple[dict, dict]:
    """(dimensions, measures) as written in the metric view's own definition."""
    meta = _q(f"DESCRIBE TABLE EXTENDED {fqn} AS JSON", None, log, f"Read {fqn.rsplit('.', 1)[-1]}'s own definition")
    spec = yaml.safe_load(json.loads(meta[0]["json_metadata"]).get("view_text") or "") or {}
    return ({d["name"]: d["expr"] for d in spec.get("dimensions", [])},
            {d["name"]: d["expr"] for d in spec.get("measures", [])})


def _metric(pid, my, log, trace="a1c"):
    p = {"pid": pid, "my": my}
    dims, meas = _mv_spec(MV_GSD, log)
    status_expr = dims.get("Compliance Status", "NULL")
    gap_expr = dims.get("Gap Reason", "NULL")
    applied = _q(f"""SELECT {status_expr} AS status, {gap_expr} AS gap_reason, evidence_value, clinic_id
                     FROM {C}.{S}.gold_adherence_gsd WHERE patient_id = :pid AND measurement_year = :my""",
                 p, log, "Execute the metric view's Compliance Status rule on this patient's evidence")
    a0 = applied[0] if applied else {}
    clinic = a0.get("clinic_id")
    roll = _q(f"""SELECT `Compliance Status`, MEASURE(`Eligible Patients`) AS patients
                  FROM {MV_GSD} WHERE `Clinic` = :c AND `Measurement Year` = :my GROUP BY 1 ORDER BY 1""",
              {"c": clinic, "my": my}, log, f"Clinic {clinic} rollup by the computed status")
    rate = _q(f"""SELECT MEASURE(`GSD Compliance Rate`) AS rate, MEASURE(`Poor Control Rate`) AS poor
                  FROM {MV_GSD} WHERE `Clinic` = :c AND `Measurement Year` = :my""",
              {"c": clinic, "my": my}, log, "Clinic rates")
    tags = _q(f"""SELECT tag_name, tag_value FROM {C}.information_schema.table_tags
                  WHERE schema_name = '{SM}' AND table_name = 'gsd_compliance_metrics'""", None, log, "Governance tags")
    certified = any(t["tag_name"] == "system.certification_status" and t["tag_value"] == "certified" for t in tags)
    domain = any(t["tag_name"] == "Clinical Domain" for t in tags)
    rule = "\n".join(f"{k}: {v}" for k, v in [
        ("Compliance Status", status_expr), ("Compliant Patients", meas.get("Compliant Patients")),
        ("GSD Compliance Rate", meas.get("GSD Compliance Rate")),
        ("Good Control Patients", meas.get("Good Control Patients")),
        ("Poor Control Patients", meas.get("Poor Control Patients"))] if v)
    r0 = rate[0] if rate else {}
    sdims, smeas = _mv_spec(MV_STEP3, log)
    s_expr = sdims.get("Adherence Status", "NULL")
    step = _q(f"""SELECT {s_expr} AS step3_status, trigger_a1c, followup_days FROM {C}.{S}.gold_protocol_adherence
                  WHERE patient_id = :pid AND trigger_ts = (SELECT evidence_datetime FROM {C}.{S}.gold_adherence_gsd
                    WHERE patient_id = :pid AND measurement_year = :my)""", p, log,
              "Execute protocol_adherence_metrics' Adherence Status rule on the same A1c's trigger row")
    s0 = step[0] if step else {}
    srate = _q(f"""SELECT MEASURE(`Protocol Step 3 Adherence Rate`) AS rate, MEASURE(`Trigger Events`) AS triggers
                   FROM {MV_STEP3} WHERE `Clinic` = :c AND `Measurement Year` = :my""",
               {"c": clinic, "my": my}, log, f"{clinic} Step-3 adherence (closed triggers)") if clinic else []
    sr0 = srate[0] if srate else {}
    return {
        "what": "The governed rules live here — read from the views' own definitions and executed live.",
        "takeaway": (f"GSD {a0.get('status')} for this patient" +
                     (f" (latest A1c {a0.get('evidence_value')}%" +
                      (", poor control; the same A1c is a Step-3 trigger: " + str(s0.get("step3_status"))
                       if s0 else "") + ")" if a0.get("evidence_value") is not None else "") +
                     f". {clinic}: GSD {_pct(r0.get('rate'))}, poor control "
                     f"{_pct(r0.get('poor'))}, Step 3 {_pct(sr0.get('rate'))} of {sr0.get('triggers')} closed triggers."),
        "source": MV_GSD,
        "sections": [
            {"label": "The rule (from the metric view definition)", "kind": "code", "text": rule},
            {"label": "Rule applied to this patient's evidence", "kind": "kv", "data": {
                "Compliance Status": a0.get("status"), "Gap Reason": a0.get("gap_reason"),
                "Latest HbA1c": a0.get("evidence_value")}},
            {"label": "Step-3 rule (protocol_adherence_metrics definition)", "kind": "code",
             "text": f"Adherence Status: {s_expr}\nProtocol Step 3 Adherence Rate: "
                     f"{smeas.get('Protocol Step 3 Adherence Rate')}"},
            {"label": "Step-3 rule applied to the same A1c", "kind": "kv", "data": {
                "Step-3 status": s0.get("step3_status"), "Trigger A1c": s0.get("trigger_a1c"),
                "Days to recheck": s0.get("followup_days") if s0.get("followup_days") is not None else "no recheck"}},
            {"label": f"{clinic} rollup by computed status", "kind": "table", "rows": roll},
            {"label": "Governance", "kind": "kv", "data": {
                "Certified (system.certification_status)": "✓ certified" if certified else "— not certified",
                "Clinical Domain tag": "✓" if domain else "—"}},
        ],
    }


def _trace_question(pid: str, trace: str) -> str:
    """The trace's question with the full patient id (Genie One has to find the patient)."""
    from .tracer import list_tracers
    hero = next((h for h in list_tracers()["traces"] if h["trace"] == trace and h["patient_id"] == pid), None)
    q = hero["question"] if hero else f"Is patient {pid[:8]} compliant with GSD for MY {MEASUREMENT_YEAR}, and why?"
    return q.replace(f"Patient {pid[:8]}", f"Patient {pid}", 1)


def _page(pid, my, log, trace="a1c"):
    """Everything Genie Ontology retrieved for THIS trace's question, from a live Genie One run (background)."""
    return genie_stage(_trace_question(pid, trace) + " Cite any ontology page you used.", log)


def genie_stage(question: str, log: list, demo: str = "healthcare_hedis") -> dict:
    """The Genie Ontology stage for any demo: run Genie One live on `question` (background, cached) and report every
    component it retrieved, flagged by whether it is about `demo`. Shared by the HEDIS and life-sciences traces."""
    from ..genie_trace import get_trace
    log.append({"label": "Live Genie One run — retrieval captured from the response stream's tool outputs",
                "sql": f"POST /api/2.0/data-rooms/tools/onechat/responses\n  input: {question!r}"})
    r = get_trace(question, demo)
    if r["status"] == "running":
        return {"pending": True, "what": "Running Genie One live and capturing everything it retrieves (~30-60s).",
                "takeaway": "", "source": None, "sections": []}
    if r["status"] == "error":
        return {"what": "Live Genie One retrieval", "takeaway": "Genie One could not be run from here.",
                "source": None, "sections": [], "warnings": [r["error"]]}
    t = r["trace"]
    snips = [x for ss in t["snippet_searches"] for x in ss["snippets"]]
    pages = [x for ss in t["snippet_searches"] for x in ss["pages"]]
    on_snip = sum(1 for x in snips if x["on_topic"])
    on_page = sum(1 for x in pages if x["on_topic"])
    stale = [a["asset"] for a in t["assets_read"] if a["stale"]]
    host = (get_workspace_client().config.host or "").replace("https://", "").split(".")[0]

    def row(component, layer, what, n, detail):
        return {"component": component, "layer": layer, "what Genie retrieved": what, "count": n, "detail": detail}
    checklist = [
        row("Inferred knowledge snippets", "learned", "snippets Genie mined from Genie agents, metric views, usage",
            len(snips), f"{on_snip} about this demo, {len(snips) - on_snip} from other projects" if snips else "none returned"),
        row("Ontology Pages (ranked)", "modeled", "Pages matched to the question", len(pages),
            f"{on_page} about this demo" if pages else "none"),
        row("Ontology Pages (read in full)", "modeled", "Page bodies Genie opened", len(t["pages_read"]), ""),
        row("UC asset search", "metadata", "tables / metric views found by comments + synonyms",
            len(t["asset_searches"]), "; ".join(str(a["result"]) for a in t["asset_searches"])),
        row("Assets read", "metadata", "metric views, tables, Genie agents inspected", len(t["assets_read"]),
            f"{len(stale)} stale (pre-relocation copy)" if stale else ""),
        row("Skills loaded", "instructions", "Genie skills (content not in the stream)", len(t["skills"]),
            ", ".join(t["skills"])),
        row("Conversation memory", "memory", "prior turns fetched (episodic)", t["memory_fetches"], ""),
        row("Genie agents consulted", "delegation", "Genie spaces it handed the question to", len(t["agents"]),
            ", ".join(a["name"] for a in t["agents"])),
        row("SQL executed", "query", "statements it ran", len(t["sql"]), ""),
        row("MCP tools", "external", "e.g. the Ontobricks MCP", len(t["mcp"]), ", ".join(m["tool"] for m in t["mcp"])),
    ]
    warns = []
    if snips and on_snip == 0:
        warns.append(f"None of the {len(snips)} inferred snippets is about this demo — the inferred layer on this "
                     f"workspace ({host}) surfaced other projects' metric views and Genie spaces for this question.")
    stale_snips = sum(1 for x in snips if x.get("stale"))
    if stale_snips:
        warns.append(f"{stale_snips} inferred snippet(s) were mined from stale pre-relocation metric views, so they "
                     f"may describe rules that no longer hold.")
    if stale:
        warns.append(f"Genie read stale pre-relocation view(s): {', '.join(stale)}. The certified views live in "
                     f"{SCHEMA_SEMANTIC}; the old copies still exist in the base schema (ADR-0013).")
    sections = [
        {"label": "What Genie Ontology retrieved — every component", "kind": "table", "rows": checklist},
        {"label": f"Inferred snippets ({len(snips)})", "kind": "table",
         "rows": [{"about this demo": "✓" if x["on_topic"] else "—", "headline": x["headline"], "type": x["type"],
                   "source": x["source"] + (" (stale copy)" if x.get("stale") else ""), "relevance": x["relevance"]}
                  for x in snips],
         "empty": "Genie's snippet search returned no inferred snippets."},
    ]
    top = next((x for x in snips if x["on_topic"]), None)
    if top:
        sections.append({"label": f"Top on-topic snippet — from {top['source']}", "kind": "quote", "text": top["content"]})
    sections += [
        {"label": f"Ontology Pages ranked ({len(pages)})", "kind": "table",
         "rows": [{"page": x["name"], "domain": x["domain"], "relevance": x["relevance"],
                   "certified": "✓" if x["certified"] else "—"} for x in pages]},
    ]
    for pr in t["pages_read"][:2]:
        sections.append({"label": "Page body, as Genie read it", "kind": "markdown", "text": pr["body"]})
    if t["assets_read"]:
        sections.append({"label": "Assets read", "kind": "table",
                         "rows": [{"asset": a["asset"], "type": a["type"], "note": "stale copy" if a["stale"] else ""}
                                  for a in t["assets_read"]]})
    if t["sql"]:
        sections.append({"label": f"SQL Genie ran ({len(t['sql'])})", "kind": "code", "text": "\n\n".join(t["sql"][:3])})
    return {
        "what": "Everything Genie One retrieved from the Genie Ontology for this patient's question — captured live "
                "from the tool outputs in its response stream, not reconstructed.",
        "takeaway": (f"Genie retrieved {len(snips)} inferred snippets ({on_snip} about this demo), {len(pages)} Pages "
                     f"({len(t['pages_read'])} read in full), {len(t['assets_read'])} assets, and ran "
                     f"{len(t['sql'])} SQL statements" + (f" via {len(t['agents'])} Genie agent" if t["agents"] else "")
                     + f" — on workspace {host}, in {r.get('latency_s')}s."),
        "source": f"Genie One on {host} · cached {int((time.time() - r['t']) // 60)} min ago",
        "sections": sections,
        "warnings": warns,
    }


def _graph_focus(trace: str, pid: str, GRAPH: str, MAIN: str, walk_codes: list[str], log: list) -> tuple[list, list, str]:
    """The trace's own traversal over the published graph: (sections, warnings, takeaway)."""
    subj = f"{NS}Patient/{pid}"
    if trace == "a1c":
        q = (f"SELECT o.object AS obs, t.object AS test FROM {GRAPH} o JOIN {GRAPH} t ON t.subject = o.object "
             f"AND t.predicate = '{NS}ofTest' AND t.object IN ('{NS}LabTest/4548-4', '{NS}LabTest/17856-6', "
             f"'{NS}LabTest/59261-8') WHERE o.subject = :s AND o.predicate = '{NS}hasObservation' "
             f"ORDER BY obs DESC LIMIT 3")
        obs = _q(q, {"s": subj}, log, "Patient → hasObservation → Observation → ofTest (A1c LOINC)")
        last = obs[0]["obs"] if obs else None
        on_node = _q(f"SELECT predicate, object FROM {MAIN} WHERE subject = :o", {"o": last}, log,
                     "Everything on the observation node the edge reaches") if last else []
        thr = _q(f"SELECT t.object AS threshold, v.object AS value FROM {GRAPH} t JOIN {MAIN} v ON v.subject = t.object "
                 f"AND v.predicate = '{NS}thresholdValue' WHERE t.subject = '{NS}Measure/GSD' "
                 f"AND t.predicate = '{NS}hasThreshold'", None, log, "GSD → hasThreshold → Threshold → thresholdValue")
        val = [r for r in on_node if r["predicate"].endswith("resultValue")]
        has_val = bool(val)
        warns = [] if has_val else [(
            "The observation the patient's edge reaches has no resultValue in this graph version, so a traversal "
            "can't compare the result with the threshold (graph versions before clinicaldomain v6 split the "
            "Observation entity and its edges across two IRIs).")]
        sec = [{"label": "The A1c observation, as the graph holds it", "kind": "kv", "data": {
                    "Patient → hasObservation → ofTest": f"{_short(last)} → {_short(obs[0]['test'])}" if obs else "—",
                    "Triples on that node": ", ".join(_short(r["predicate"]) for r in on_node) or "—",
                    "Value": val[0]["object"] if val else "—"}},
               {"label": "GSD thresholds in the graph", "kind": "table",
                "rows": [{"threshold": _short(r["threshold"]), "value": r["value"]} for r in thr]}]
        thr_txt = ", ".join(_short(r["threshold"]) for r in thr)
        return sec, warns, (f"The graph holds the A1c observation (ofTest LabTest/4548-4, value {val[0]['object']}) and "
                            f"GSD's thresholds ({thr_txt}), so a traversal from the patient can compare them. "
                            if has_val else
                            f"The graph holds the A1c observation (ofTest LabTest/4548-4) and GSD's thresholds "
                            f"({thr_txt}), but can't yet reach the value from the patient. ")
    if trace == "dx":
        nodes = ", ".join(f"'{NS}Condition/{c}'" for c in walk_codes)
        rows = _q(f"""SELECT c.subject AS value_set, c.object AS member, r.subject AS drug_class, r.predicate AS rel
                      FROM {GRAPH} c LEFT JOIN {GRAPH} r ON r.object = c.subject
                        AND r.predicate IN ('{NS}recommendedFor', '{NS}contraindicatedWith')
                      WHERE c.predicate = '{NS}contains' AND c.object IN ({nodes}) ORDER BY 1, 3""", None, log,
                  "ValueSet → contains → the code or an ancestor, and the protocol edges into those value sets")
        tbl = [{"value set": _short(r["value_set"]), "contains": _short(r["member"]),
                "protocol edge": f"{_short(r['drug_class'])} {_short(r['rel'])}" if r["drug_class"] else "—"}
               for r in rows]
        return ([{"label": "Value sets the code reaches, and the protocol edges into them (traversal)",
                  "kind": "table", "rows": tbl}], [],
                f"Traversal from Condition/{traces.DX_CODE} reaches {len({r['value set'] for r in tbl})} value sets. ")
    # rule
    rule = _q(f"""SELECT w.subject AS drug_class, w.object AS threshold, v.object AS value, a.object AS measured_on
                  FROM {GRAPH} w JOIN {MAIN} v ON v.subject = w.object AND v.predicate = '{NS}thresholdValue'
                  LEFT JOIN {GRAPH} a ON a.subject = w.object AND a.predicate = '{NS}appliesTo'
                  WHERE w.predicate = '{NS}contraindicatedWhen' ORDER BY 1""", None, log,
              "DrugClass → contraindicatedWhen → Threshold (+ thresholdValue, appliesTo)")
    path = _q(f"""SELECT rx.object AS rx, i.object AS ing, c.object AS drug_class
                  FROM {GRAPH} rx
                  LEFT JOIN {GRAPH} i ON i.subject = rx.object AND i.predicate = '{NS}hasIngredient'
                  LEFT JOIN {GRAPH} c ON c.subject = i.object AND c.predicate = '{NS}inDrugClass'
                  WHERE rx.subject = :s AND rx.predicate = '{NS}prescribed'
                    AND rx.object IN (SELECT subject FROM {GRAPH} WHERE predicate = '{NS}hasIngredient'
                                      AND object = '{NS}Ingredient/6809')""", {"s": subj}, log,
              "Patient → prescribed → rx → hasIngredient → ing → inDrugClass (metformin)")
    reaches = any(r["drug_class"] for r in path)
    applies = any(r["measured_on"] for r in rule)
    warns = []
    if not reaches:
        warns.append("Ingredient/6809 (metformin) has no inDrugClass edge in this graph version, so the patient's order "
                     "can't be connected to the biguanide rule (ONTOBRICKS_REPUBLISH 2026-11-21 item 1).")
    if not applies:
        warns.append("No Threshold → appliesTo → LoincPart edge yet, so a traversal can't tell which lab eGFR_LT_30 "
                     "is compared with (item 3).")
    sec = [{"label": "The rule in the graph", "kind": "table",
            "rows": [{"drug class": _short(r["drug_class"]), "contraindicatedWhen": _short(r["threshold"]),
                      "value": r["value"], "appliesTo": _short(r["measured_on"]) or "— (not mapped)"} for r in rule]},
           {"label": "The patient's metformin order, traversed", "kind": "table",
            "rows": [{"prescribed": _short(r["rx"]), "hasIngredient": _short(r["ing"]),
                      "inDrugClass": _short(r["drug_class"]) or "— (no edge)"} for r in path]}]
    return sec, warns, ("The graph holds the rule (BIGUANIDE contraindicatedWhen eGFR_LT_30, value 30) and the "
                        "patient's metformin order" + ("" if reaches and applies else
                                                       ", but the traversal stops before connecting them") + ". ")


def _ontobricks(pid, my, log, trace="a1c"):
    ONTOBRICKS_TABLE = get_ontobricks_table()           # latest published version (follows republishes)
    GRAPH = f"{ONTOBRICKS_CATALOG}.{ONTOBRICKS_SCHEMA}.{ONTOBRICKS_TABLE}_graph"
    MAIN = f"{ONTOBRICKS_CATALOG}.{ONTOBRICKS_SCHEMA}.{ONTOBRICKS_TABLE}"  # object + literal triples
    dx = _trace_code(pid, trace)
    subj = f"{NS}Patient/{pid}"
    pp = ", ".join(f"'{NS}{x}'" for x in ("hasDiagnosis", "eligibleFor", "hasCareGap", "prescribed"))
    q_patient = (f"SELECT predicate, object FROM {GRAPH} WHERE subject = :s AND predicate IN ({pp}) "
                 f"ORDER BY predicate, object LIMIT 40")
    q_walk = f"""WITH RECURSIVE sc AS (
                   SELECT subject, object FROM {GRAPH} WHERE predicate = '{NS}subClassOf'),
                 walk(node, ancestor, hops) AS (
                   SELECT subject, object, 1 FROM sc WHERE subject = :n
                   UNION ALL SELECT w.node, sc.object, w.hops + 1 FROM walk w JOIN sc ON sc.subject = w.ancestor
                   WHERE w.hops < 8)
                 SELECT ancestor, hops FROM walk ORDER BY hops"""
    gp = ", ".join(f"'{NS}{x}'" for x in ("recommendedFor", "contraindicatedWith", "contraindicatedWhen",
                                           "monitoredBy", "hasThreshold", "inDrugClass"))
    g_subj = {"a1c": ("Measure/GSD",), "dx": ("Measure/KED", "Measure/SPD"),
              "rule": ("DrugClass/DRUGCLASS-BIGUANIDE", "DrugClass/DRUGCLASS-SGLT2")}.get(trace, ("Measure/GSD",))
    q_guide = (f"SELECT subject, predicate, object FROM {GRAPH} WHERE predicate IN ({gp}) AND "
               f"(subject IN ({', '.join(chr(39) + NS + x + chr(39) for x in g_subj)}) "
               f" OR object IN ({', '.join(chr(39) + NS + x + chr(39) for x in g_subj)})) ORDER BY predicate, subject")
    q_asof = (f"SELECT max(last_altered) AS t FROM {ONTOBRICKS_CATALOG}.information_schema.tables "
              f"WHERE table_schema = '{ONTOBRICKS_SCHEMA}' AND table_name = '{ONTOBRICKS_TABLE}_graph'")
    log += [{"label": "Patient's typed edges (live triplestore)", "sql": q_patient},
            {"label": "Graph closure: walk subClassOf* at QUERY time (recursive)", "sql": q_walk},
            {"label": "Guideline edges reachable from the patient's measures", "sql": q_guide}]
    with ThreadPoolExecutor(max_workers=4) as ex:
        f_p = ex.submit(run_sql, q_patient, {"s": subj})
        f_w = ex.submit(run_sql, q_walk, {"n": f"{NS}Condition/{dx}"})
        f_g = ex.submit(run_sql, q_guide, None)
        f_t = ex.submit(run_sql, q_asof, None)
        f_c = ex.submit(run_sql, f"SELECT ancestor_code FROM {C}.{ST}.icd10_closure WHERE descendant_code = :d "
                                 f"AND depth > 0 ORDER BY depth", {"d": dx})
        # the governed rule (gsd_compliance_metrics "Compliance Status", HEDIS GSD): MET = last A1c <= 9%
        f_s = ex.submit(run_sql, f"SELECT CASE WHEN evidence_value <= 9.0 THEN 'MET' ELSE 'NOT_MET' END AS s "
                                 f"FROM {C}.{S}.gold_adherence_gsd WHERE patient_id = :p AND measurement_year = :my",
                        {"p": pid, "my": my})
        prow, walk, guide = f_p.result(), f_w.result(), f_g.result()
        asof, mat, live = f_t.result(), f_c.result(), f_s.result()
    # names for the rx / ingredient nodes (the graph's nodes are opaque codes; RxNorm names come from the hierarchy)
    codes = sorted({_short(r["object"]).split("/", 1)[-1] for r in prow if r["predicate"].endswith("prescribed")})
    names = {}
    if codes:
        names = {r["code"]: r["name"] for r in run_sql(
            f"SELECT code, name FROM {C}.{ST}.rxnorm_hier WHERE code IN ({', '.join(chr(39) + c + chr(39) for c in codes if c.isdigit())})")} \
            if any(c.isdigit() for c in codes) else {}
    missing = [c for c in codes if c.isdigit() and c not in names]
    if missing:
        for r in run_sql(f"SELECT rxnorm_code, MIN(description) AS d FROM {C}.{S}.bronze_order_med WHERE rxnorm_code "
                         f"IN ({', '.join(chr(39) + c + chr(39) for c in missing)}) GROUP BY 1"):
            names[r["rxnorm_code"]] = r["d"]
    edges = [{"subject": f"Patient/{pid[:8]}", "predicate": _short(r["predicate"]), "object": _short(r["object"])}
             for r in prow]
    chain = [{"code": dx, "name": "patient's diagnosis", "depth": 0}] + \
            [{"code": _short(r["ancestor"]).replace("Condition/", ""), "name": f"subClassOf* hop {r['hops']}",
              "depth": r["hops"]} for r in walk]
    graph_anc = list(dict.fromkeys(n["code"] for n in chain[1:]))   # a node reachable by two routes counts once
    mat_anc = [r["ancestor_code"] for r in mat]
    agrees = sorted(graph_anc) == sorted(mat_anc)
    # One parent per hop = a real chain; otherwise (a code with several parents) list ancestors with their hop count,
    # because "A -> B -> C" would claim a route that doesn't exist.
    hops: dict[int, list[str]] = {}
    for n in chain[1:]:
        hops.setdefault(n["depth"], []).append(n["code"])
    is_chain = all(len(set(v)) == 1 for v in hops.values()) and len(graph_anc) == len(chain) - 1

    def show(codes_with_hops):
        return (" → ".join([dx] + [c for c, _ in codes_with_hops]) if is_chain
                else ", ".join(f"{c} [{h}]" for c, h in codes_with_hops))
    walk_txt = show([(n["code"], n["depth"]) for n in chain[1:]])
    sep = " → " if is_chain else ", "
    guide_rows = [{"subject": _short(r["subject"]), "predicate": _short(r["predicate"]),
                   "object": _short(r["object"])} for r in guide]
    graph_gap = any(e["predicate"] == "hasCareGap" and e["object"] == "Measure/GSD" for e in edges)
    live_status = live[0]["s"] if live else None
    as_of = str(asof[0]["t"])[:16].replace("T", " ") if asof else "?"
    warns = []
    if live_status and graph_gap != (live_status == "NOT_MET"):
        warns.append(f"Graph snapshot (published {as_of} UTC) says GSD care gap = {graph_gap}, but the live metric "
                     f"view computes {live_status}. The triplestore lags the pipeline until Ontobricks republishes.")
    focus, fwarn, ftake = _graph_focus(trace, pid, GRAPH, MAIN, [dx] + graph_anc, log)
    warns += fwarn
    takeaway = ftake + (f"subClassOf* walked live from Condition/{dx}: {walk_txt} ({len(graph_anc)} ancestors, query-time) — "
                        f"{'identical to' if agrees else 'differs from'} the materialized icd10_closure."
                        if trace == "dx" else "")
    return {
        "what": "The explicit OWL graph, queried live: typed edges + a closure computed by traversal.",
        "takeaway": takeaway,
        "source": f"{GRAPH} (published {as_of} UTC)",
        "sections": [
            *(focus if trace != "dx" else []),
            *([{"label": "Graph closure — subClassOf* walked live", "kind": "chain", "nodes": chain},
               *focus,
               {"label": "Closure comparison", "kind": "kv", "data": {
                   "Graph (traversal, query-time)": sep.join(graph_anc) or "—",
                   "icd10_closure (materialized, build-time)": sep.join(mat_anc) or "—",
                   "Same ancestors": "✓" if agrees else "✗"}}] if trace == "dx" else []),

            {"label": "Patient's typed edges (grouped)", "kind": "kv", "data": {
                "hasDiagnosis": ", ".join(e["object"].replace("Condition/", "") for e in edges if e["predicate"] == "hasDiagnosis"),
                "eligibleFor": ", ".join(e["object"].replace("Measure/", "") for e in edges if e["predicate"] == "eligibleFor"),
                "hasCareGap (graph snapshot)": ", ".join(e["object"].replace("Measure/", "") for e in edges
                                                         if e["predicate"] == "hasCareGap") or "none",
                "prescribed": f"{sum(e['predicate'] == 'prescribed' for e in edges)} drugs — " + ", ".join(
                    names.get(e["object"].split("/", 1)[-1], e["object"]) for e in edges
                    if e["predicate"] == "prescribed")[:220]}},
            {"label": f"Guideline edges for {', '.join(x.split('/')[-1] for x in g_subj)}", "kind": "triples",
             "rows": guide_rows},
        ],
        "warnings": warns,
    }


def _raw(pid, my, log, trace="a1c"):
    p = {"pid": pid}
    cnt = _q(f"""SELECT count(*) AS conditions, count(DISTINCT CODE) AS snomed_codes,
                        (SELECT count(*) FROM {C}.{S}.raw_synthea_observations o
                          WHERE o.PATIENT = :pid AND o.CODE IN {A1C_CODES}) AS a1c_obs
                 FROM {C}.{S}.raw_synthea_conditions WHERE PATIENT = :pid""", p, log, "Size of the raw extract")[0]
    cond = _q(f"""SELECT START, STOP, SYSTEM, CODE, DESCRIPTION FROM {C}.{S}.raw_synthea_conditions
                  WHERE PATIENT = :pid ORDER BY (DESCRIPTION ILIKE '%diabet%') DESC, START DESC LIMIT 8""",
              p, log, "Raw condition rows (Synthea CSV, as generated)")
    return {
        "what": "The EHR extract as generated — CSV-shaped, SNOMED-CT coded, no ICD-10 and no Clarity structure yet.",
        "takeaway": (f"The raw extract has {cnt['conditions']} condition rows ({cnt['snomed_codes']} SNOMED concepts) "
                     f"and {cnt['a1c_obs']} HbA1c observations for this patient. Nothing is ICD-10 coded yet — "
                     f"epicize maps SNOMED → ICD-10 and reshapes rows into Clarity tables to produce bronze."),
        "source": f"{C}.{S}.raw_synthea_conditions · raw_synthea_observations",
        "sections": [
            {"label": "Raw condition rows (diabetes-related first)", "kind": "table", "rows": cond},
            {"label": "What happens next", "kind": "kv", "data": {
                "Diagnoses": "SNOMED-CT → ICD-10-CM crosswalk (epicize) → bronze_pat_enc_dx",
                "Lab results": "LOINC observations → the landed lab feed (bronze); the demo's care-behavior "
                               "model sets their cadence and level (see Bronze)",
                "Identifiers / demographics": "not shown — the raw patient file carries synthetic PII"}},
        ],
    }


def _rag(pid, my, log, trace="a1c"):
    from .rag import search  # the live A4 Lakebase retriever (doc-level RLS), same as the RAG lens
    r = search(traces.get(trace)["rag_question"])
    log.append({"label": f"Hybrid retrieval over rag.chunks ({r.get('mode')}, k=5, doc-level RLS)",
                "sql": f"search_documents(question={r.get('question')!r}, k=5, mode={r.get('mode')!r})"})
    rows = [{"document": x.get("title"), "MY": x.get("measurement_year"), "section": x.get("section_path"), "page": x.get("page_start"),
             "score": round(float(x["score"]), 3) if x.get("score") is not None else None}
            for x in r.get("results", [])]
    top = (r.get("results") or [{}])[0]
    return {
        "what": "Unstructured context: protocol passages retrieved by meaning + keywords, filtered by document ACLs.",
        "takeaway": (f"RAG returns {len(rows)} passages for the trace's question (top: {top.get('title')} · "
                     f"§{top.get('section_path')}). It explains WHAT the rule is and WHERE it's written; it can't "
                     f"compute this patient's status or count a cohort."),
        "source": "Lakebase rag.chunks (A4) · document-level RLS",
        "sections": [
            {"label": "The retrieval question", "kind": "quote", "text": r.get("question", "")},
            {"label": "Passages returned", "kind": "table", "rows": rows},
            {"label": "Top passage", "kind": "quote",
             "text": html.unescape(re.sub(r"\s+", " ", top.get("content") or ""))[:700]},
        ],
    }


def _closure_ret(pid, my, log, trace="a1c"):
    p = {"pid": pid}
    inv = _q(" UNION ALL ".join(f"SELECT '{t}' AS table_name, count(*) AS rows FROM {C}.{ST}.{t}" for t in
                                ("icd10_closure", "rxnorm_closure", "loinc_parts", "value_set_segment", "protocol_edges")),
             None, log, "Governed closure + edge tables an agent can query")
    inv_sec = {"label": "Tables available to an agent / MCP tool", "kind": "table", "rows": inv}
    src = f"{C}.{ST}.icd10_closure · rxnorm_closure · loinc_parts · value_set_segment · protocol_edges"
    if trace == "rule":
        hit = _q(f"""WITH rx AS (SELECT max_by(rxnorm_code, start_ts) AS rxnorm_code, max_by(description, start_ts) AS drug
                                FROM {C}.{S}.care_order_med WHERE patient_id = :pid
                                  AND start_ts <= TIMESTAMP'2026-10-30 23:59:59'
                                  AND (stop_ts IS NULL OR stop_ts >= TIMESTAMP'2026-10-30')
                                  AND rxnorm_code IN (SELECT descendant_code FROM {C}.{ST}.rxnorm_closure
                                                      WHERE ancestor_code LIKE 'DRUGCLASS-%')),
                          lab AS (SELECT lp.part, max_by(o.loinc_code, o.result_ts) AS loinc_code,
                                         max_by(o.value_num, o.result_ts) AS value, max(o.result_ts) AS ts
                                  FROM {C}.{S}.silver_observation o
                                  JOIN {C}.{ST}.loinc_parts lp ON lp.loinc_code = o.loinc_code AND lp.predicate = 'has_component'
                                  WHERE o.patient_id = :pid AND o.result_ts <= TIMESTAMP'2026-10-30 23:59:59'
                                  GROUP BY lp.part)
                     SELECT rx.drug, rc.ancestor_code AS drug_class, e.object AS threshold, CAST(e.value AS DOUBLE) AS cutoff,
                            a.object AS measured_on, lab.loinc_code, lab.value AS latest_value, CAST(lab.ts AS DATE) AS on_date,
                            e.source AS protocol_section, lab.value < CAST(e.value AS DOUBLE) AS violated
                     FROM rx
                     JOIN {C}.{ST}.rxnorm_closure rc ON rc.descendant_code = rx.rxnorm_code AND rc.ancestor_code LIKE 'DRUGCLASS-%'
                     JOIN {C}.{ST}.protocol_edges e ON e.subject = rc.ancestor_code AND e.predicate = 'contraindicatedWhen'
                     JOIN {C}.{ST}.protocol_edges a ON a.subject = e.object AND a.predicate = 'appliesTo'
                     JOIN lab ON lab.part = a.object
                     ORDER BY lab.ts DESC LIMIT 3""", p, log,
                 "Drug → class → contraindicatedWhen threshold → the lab it is measured on → the patient's last value "
                 "of that lab on or before 2026-10-30, any code (rxnorm_closure, protocol_edges, loinc_parts, "
                 "silver_observation)")
        h0 = hit[0] if hit else {}
        v = h0.get("violated") in (True, "true")
        return {
            "what": "Structured context: the rule applied with one fixed-shape join over the governed edge tables.",
            "takeaway": ((f"{h0.get('drug')} ⊑ {h0.get('drug_class')} → contraindicatedWhen {h0.get('threshold')} "
                          f"(< {h0.get('cutoff')}), measured on {h0.get('measured_on')}: latest {h0.get('loinc_code')} = "
                          f"{h0.get('latest_value')} → {'violated' if v else 'not violated'}. " if hit else
                          "No contraindicatedWhen rule applies to this patient's drugs. ") +
                         "Deterministic and exact, but this join only answers this shape of question."),
            "source": src,
            "sections": [{"label": "The rule applied (fixed-shape join)", "kind": "table", "rows": hit,
                          "empty": "No drug-class threshold rule applies to this patient's latest results."},
                         inv_sec],
        }
    if trace == "dx":
        code = traces.DX_CODE
        recs = _q(f"""SELECT DISTINCT c.ancestor_code AS via_code, c.depth, v.segment_id AS value_set, e.subject AS drug_class,
                             e.predicate, e.source AS protocol_section
                      FROM {C}.{ST}.icd10_closure c
                      JOIN {C}.{ST}.value_set_segment v ON v.code = c.ancestor_code AND v.code_system = 'ICD10CM'
                      JOIN {C}.{ST}.protocol_edges e ON e.object = v.segment_id
                      WHERE c.descendant_code = :c ORDER BY 1, 4""", {"c": code}, log,
                  "Code → ancestors → value sets → protocol edges into them (icd10_closure + value_set_segment + "
                  "protocol_edges)")
        return {
            "what": "Structured context: cohort and protocol knowledge reached from one code with fixed-shape joins.",
            "takeaway": (f"From {code}: " + "; ".join(f"{r['drug_class'].replace('DRUGCLASS-', '')} {r['predicate']} "
                                                        f"{r['value_set']} (via {r['via_code']})" for r in recs) +
                         ". Exact, but each new question shape is a new hand-written join."),
            "source": src,
            "sections": [{"label": "Protocol knowledge the code reaches", "kind": "table", "rows": recs,
                          "empty": "No protocol edge points at a value set containing this code or its ancestors."},
                         inv_sec],
        }
    ev = _evidence(pid, my)
    rule = _q(f"""SELECT lp.loinc_code, lp.part AS component, a.subject AS threshold, h.subject AS measure,
                         CAST(h.value AS DOUBLE) AS cutoff, h.source AS protocol_section
                  FROM {C}.{ST}.loinc_parts lp
                  JOIN {C}.{ST}.protocol_edges a ON a.predicate = 'appliesTo' AND a.object = lp.part
                  JOIN {C}.{ST}.protocol_edges h ON h.object = a.subject AND h.predicate = 'hasThreshold'
                  WHERE lp.loinc_code = :code AND lp.predicate = 'has_component' ORDER BY cutoff""",
              {"code": ev.get("evidence_code")}, log,
              "The result's LOINC code → its component → the measure thresholds on that component (loinc_parts + "
              "protocol_edges)")
    return {
        "what": "Structured context: what the result's code measures and which thresholds apply, via fixed joins.",
        "takeaway": (f"{ev.get('evidence_code')} measures {rule[0]['component'] if rule else '—'}; the thresholds on it are "
                     + ", ".join(f"{r['threshold']} ({r['measure']}, {r['cutoff']})" for r in rule) +
                     f". The latest value is {ev.get('evidence_value')}%"
                     f"{' — above the poor-control cutoff' if ev.get('evidence_value') is not None and float(ev['evidence_value']) > 9 else ''}"
                     f". The direction (above / below) is encoded in the threshold's id, not as a column."),
        "source": src,
        "sections": [{"label": "Code → component → thresholds", "kind": "table", "rows": rule}, inv_sec],
    }


_STAGES = {"protocol": ("Source — care-protocol document", _protocol),
           "bronze": ("Bronze — raw EHR rows", _bronze),
           "silver": ("Silver — conformed condition + observations", _silver),
           "closure": ("Terminology — ICD-10 subsumption", _closure),
           "cohort": ("Cohort — measure denominators", _cohort),
           "gold": ("Gold — per-patient evidence", _gold),
           "metric": ("Semantic — certified metric view", _metric),
           "page": ("Retrieval — Genie Ontology (live Genie One run)", _page),
           "ontobricks": ("Retrieval — Ontobricks graph (live)", _ontobricks),
           "raw": ("Source — raw EHR extract", _raw),
           "rag": ("Retrieval — RAG index (A4 Lakebase)", _rag),
           "closure_ret": ("Retrieval — closure + edge tables", _closure_ret)}


@router.get("/patient/{patient_id}/stage/{key}")
def stage_detail(patient_id: str, key: str, trace: str = "a1c"):
    if trace not in traces.TRACES:
        raise HTTPException(404, f"Unknown trace {trace!r}; known: {', '.join(traces.TRACES)}")
    if key not in _STAGES:
        raise HTTPException(404, f"Unknown stage {key!r}; known: {', '.join(_STAGES)}")
    title, fn = _STAGES[key]
    log: list = []
    t0 = time.time()
    try:
        out = fn(patient_id, MEASUREMENT_YEAR, log, trace)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 — surface the real failure to the click-in
        raise HTTPException(502, f"{key} retrieval failed: {type(e).__name__}: {str(e)[:300]}")
    return {"key": key, "title": title, "patient_id": patient_id, "trace": trace, "queries": log,
            "latency_s": round(time.time() - t0, 1), "warnings": out.pop("warnings", []), **out}
