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
import re
import time
from concurrent.futures import ThreadPoolExecutor

import yaml
from fastapi import APIRouter, HTTPException

from ..config import (
    CATALOG, MEASUREMENT_YEAR, ONTOBRICKS_CATALOG, ONTOBRICKS_NS, ONTOBRICKS_SCHEMA, ONTOBRICKS_TABLE,
    SCHEMA, SCHEMA_SEMANTIC, SCHEMA_TERM,
)
from ..warehouse import run_sql

router = APIRouter()

C, S, SM, ST = CATALOG, SCHEMA, SCHEMA_SEMANTIC, SCHEMA_TERM
NS = ONTOBRICKS_NS
GRAPH = f"{ONTOBRICKS_CATALOG}.{ONTOBRICKS_SCHEMA}.{ONTOBRICKS_TABLE}_graph"
A1C_CODES = f"(SELECT code FROM {C}.{ST}.value_set_segment WHERE segment_id = 'GSD_A1C_TEST')"
PAGES_VOL = f"/Volumes/{C}/{S}/ontology_pages"
MV_GSD = f"{C}.{SM}.gsd_compliance_metrics"

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


# --------------------------------------------------- stages ----------------------------------------------------
def _protocol(pid, my, log):
    ev = _evidence(pid, my)
    dx = _primary_dx(pid)["dx"]
    passage, meta, warn = None, {}, []
    try:
        from .rag import _AS_USER, _retriever  # the same A4 Lakebase retriever the RAG lens uses (RLS on)
        sql = ("SELECT d.title, c.section_path, c.page_start, c.content FROM rag.chunks c "
               "JOIN rag.documents d USING (document_id) WHERE d.title ILIKE %s AND c.content ILIKE %s "
               "ORDER BY c.page_start LIMIT 1")
        log.append({"label": "Retrieve the GSD specification chunk (A4 Lakebase RAG corpus, doc-level RLS)",
                    "sql": sql.replace("%s", "'Care Protocol%Comprehensive%'", 1).replace("%s", "'%Glycemic Status%'", 1)})
        rows = _retriever()._run(sql, ("Care Protocol%Comprehensive%", "%Glycemic Status%"), _AS_USER)
        if rows:
            r0 = rows[0]
            passage = html.unescape(re.sub(r"\s+", " ", r0["content"])).strip()
            meta = {"document": r0["title"], "section": r0["section_path"], "page": r0["page_start"],
                    "corpus": "rag.chunks (chunked from /Volumes/.../documents/pdf/diabetes_care_protocol.pdf)"}
    except Exception as e:  # noqa: BLE001 — degrade to the vendored excerpt, but SAY so
        warn.append(f"RAG corpus unreachable ({type(e).__name__}); showing the vendored protocol excerpt.")
    if not passage:
        passage = ("GSD — Glycemic Status Assessment. Eligible ages 18–75. Numerator (compliant when): ≥1 HbA1c "
                   "test in the measurement year. Good control < 8.0%; poor control > 9.0%; general target < 7.0%.")
        meta = {"document": "CP-DM-2025.1 — Comprehensive Diabetes Management (v2025.1)",
                "section": "2. Quality Measure Specifications", "page": 4, "corpus": "vendored fallback"}
    age = ev.get("age")
    in_window = age is not None and 18 <= int(age) <= 75
    return {
        "what": "The human-authored rule. Everything downstream is an instance of this definition.",
        "takeaway": (f"The protocol defines GSD as ≥1 HbA1c in MY{my}. Patient {pid[:8]} (age {age}, {dx}) "
                     f"{'is in scope' if in_window else 'is outside the 18–75 window'}."),
        "source": meta.get("corpus"),
        "sections": [
            {"label": f"Retrieved passage — {meta.get('document')} · §{meta.get('section')} · p.{meta.get('page')}",
             "kind": "quote", "text": passage},
            {"label": "Does this rule apply to this patient?", "kind": "kv", "data": {
                "Diagnosis": f"{dx} (a descendant of the E10/E11/E13 roots — see Closure)",
                "Age at end of MY": age, "Eligible window": "18–75",
                "In scope": "yes" if in_window else "no"}},
        ],
        "warnings": warn,
    }


def _bronze(pid, my, log):
    p = {"pid": pid, "my": my}
    stats = _q(f"""SELECT count(*) AS raw_rows, count(icd10_code) AS with_icd10, count(DISTINCT snomed_code) AS snomed_codes
                   FROM {C}.{S}.bronze_pat_enc_dx WHERE patient_id = :pid""", p, log, "Raw encounter-diagnosis rows")[0]
    dx = _q(f"""SELECT onset_date, encounter_id, snomed_code, icd10_code, description
                FROM {C}.{S}.bronze_pat_enc_dx WHERE patient_id = :pid
                ORDER BY (icd10_code LIKE 'E1%') DESC, onset_date LIMIT 6""", p, log, "Sample raw diagnosis rows")
    a1c = _q(f"""SELECT result_ts, loinc_code, description, value, units FROM {C}.{S}.care_order_results
                 WHERE patient_id = :pid AND loinc_code IN {A1C_CODES} AND year(result_ts) = :my
                 ORDER BY result_ts DESC LIMIT 6""", p, log, "Raw HbA1c results landed in the measurement year")
    n_a1c = _q(f"""SELECT count(*) AS n FROM {C}.{S}.care_order_results
                   WHERE patient_id = :pid AND loinc_code IN {A1C_CODES} AND year(result_ts) = :my""",
               p, log, "Count raw HbA1c results")[0]["n"]
    return {
        "what": "Clarity-shaped rows exactly as they landed: SNOMED as emitted, values stored as text.",
        "takeaway": (f"{stats['raw_rows']} raw encounter-diagnosis rows ({stats['snomed_codes']} SNOMED concepts); "
                     f"only {stats['with_icd10']} carry an ICD-10 code. {n_a1c} raw HbA1c result{'' if str(n_a1c) == '1' else 's'} in MY{my}."),
        "source": f"{C}.{S}.bronze_pat_enc_dx · care_order_results (landed lab feed: Clarity results + care-behavior events)",
        "sections": [
            {"label": "Encounter diagnoses (raw)", "kind": "table", "rows": dx},
            {"label": f"HbA1c results (raw, latest {len(a1c)} of {n_a1c})", "kind": "table", "rows": a1c,
             "empty": f"No HbA1c result landed in MY{my} — this is where a GSD care gap originates."},
        ],
    }


def _silver(pid, my, log):
    p = {"pid": pid, "my": my}
    raw = run_sql(f"SELECT count(*) AS n FROM {C}.{S}.bronze_pat_enc_dx WHERE patient_id = :pid", p)[0]["n"]
    cond = _q(f"""SELECT icd10_code, description, onset_date FROM {C}.{S}.silver_condition
                  WHERE patient_id = :pid ORDER BY icd10_code""", p, log, "Conformed conditions (ICD-10)")
    obs = _q(f"""SELECT result_ts, loinc_code, value_num, units, description,
                        CASE WHEN encounter_id IS NULL THEN 'follow-up (care-behavior model)'
                             ELSE 'EHR encounter' END AS origin
                 FROM {C}.{S}.silver_observation
                 WHERE patient_id = :pid AND loinc_code IN {A1C_CODES} AND year(result_ts) = :my
                 ORDER BY result_ts DESC LIMIT 8""", p, log, "Conformed HbA1c observations (typed, LOINC-resolved)")
    modeled = sum(1 for r in obs if str(r.get("origin", "")).startswith("follow-up"))
    return {
        "what": "Conformance: map to ICD-10, drop unmapped noise, type values, resolve LOINC.",
        "takeaway": (f"{raw} raw diagnosis rows → {len(cond)} conformed ICD-10 conditions. HbA1c values typed to "
                     f"numbers{f'; {modeled} is a protocol follow-up emitted by the care-behavior model' if modeled else ''}."),
        "source": f"{C}.{S}.silver_condition · silver_observation",
        "sections": [
            {"label": f"Conformed conditions ({len(cond)})", "kind": "table", "rows": cond},
            {"label": "HbA1c observations (typed value_num)", "kind": "table", "rows": obs,
             "empty": f"No conformed HbA1c in MY{my}."},
        ],
    }


def _closure(pid, my, log):
    dx = _primary_dx(pid)["dx"]
    chain = _q(f"""SELECT ancestor_code, ancestor_name, depth FROM {C}.{ST}.icd10_closure
                   WHERE descendant_code = :dx ORDER BY depth DESC""", {"dx": dx}, log,
               "Ancestor chain for the patient's diagnosis (one equality on descendant_code)")
    root = next((r["ancestor_code"] for r in chain if r["ancestor_code"] in ("E10", "E11", "E13")), None)
    covers = _q(f"SELECT count(*) AS n FROM {C}.{ST}.icd10_closure WHERE ancestor_code = :r",
                {"r": root}, log, f"How many codes the {root} root subsumes")[0]["n"] if root else 0
    allpx = _q(f"""SELECT DISTINCT d.icd10_code AS patient_code, c.ancestor_code AS diabetes_root, c.depth
                   FROM {C}.{S}.bronze_pat_enc_dx d JOIN {C}.{ST}.icd10_closure c ON c.descendant_code = d.icd10_code
                   WHERE d.patient_id = :pid AND c.ancestor_code IN ('E10','E11','E13') ORDER BY 1""",
               {"pid": pid}, log, "All of this patient's codes that resolve to a diabetes root")
    nodes = [{"code": r["ancestor_code"], "name": r["ancestor_name"], "depth": r["depth"]} for r in chain]
    return {
        "what": "Pre-materialized transitive closure: every ancestor of a code is one row away.",
        "takeaway": (f"{dx} ⊑ {' ⊑ '.join(n['code'] for n in sorted(nodes, key=lambda n: int(n['depth'])) if int(n['depth']) > 0)} — one equality join "
                     f"(ancestor_code = '{root}') catches it. {root} subsumes {covers} codes; a flat list would "
                     f"have to enumerate them all."),
        "source": f"{C}.{ST}.icd10_closure",
        "sections": [
            {"label": "Subsumption chain (root → patient's code)", "kind": "chain", "nodes": list(reversed(nodes))},
            {"label": "This patient's diabetes-rooted codes", "kind": "table", "rows": allpx},
        ],
    }


def _cohort(pid, my, log):
    p = {"pid": pid, "my": my}
    size = int(_q(f"SELECT count(*) AS n FROM {C}.{S}.silver_diabetes_cohort", None, log, "Diabetes cohort size")[0]["n"])
    age = _q(f"""SELECT CAST(datediff(DATE'{my}-12-31', birth_date) / 365.25 AS INT) AS age
                 FROM {C}.{S}.bronze_patient WHERE patient_id = :pid""", p, log, "Age at end of measurement year")
    age = age[0]["age"] if age else None
    union = " UNION ALL ".join(f"SELECT '{m}' AS m FROM {C}.{S}.{t} WHERE patient_id = :pid" for m, _, _, t in WINDOWS)
    elig = {r["m"] for r in _q(union, p, log, "Which measure denominators include this patient")}
    rows = [{"measure": m, "name": n, "eligible window": w, "eligible": "✓" if m in elig else "—"}
            for m, n, w, _ in WINDOWS]
    return {
        "what": "The denominator: cohort membership (earned by subsumption) × each measure's age window.",
        "takeaway": (f"In the {size:,}-patient diabetes cohort; age {age} → in {len(elig)} measure denominators "
                     f"({', '.join(m for m, *_ in WINDOWS if m in elig)})."),
        "source": f"{C}.{S}.silver_diabetes_cohort · bronze_patient",
        "sections": [{"label": "Measure eligibility for this patient", "kind": "table", "rows": rows}],
    }


def _gold(pid, my, log):
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
    return {
        "what": "One evidence row per eligible patient — facts only. The verdict is NOT computed here.",
        "takeaway": f"Gold assembled the evidence: {ev_txt}. "
                    f"{'⚠ gold still carries a verdict column' if has_verdict else 'No status / numerator column exists in gold — the rule is applied in the metric view.'}",
        "source": f"{C}.{S}.gold_adherence_gsd",
        "sections": [
            {"label": "Evidence row", "kind": "kv", "data": ev},
            {"label": "Gold columns (no verdict)", "kind": "chips", "items": names},
        ],
        "warnings": warns,
    }


def _metric(pid, my, log):
    p = {"pid": pid, "my": my}
    meta = _q(f"DESCRIBE TABLE EXTENDED {MV_GSD} AS JSON", None, log, "Read the metric view's own definition")
    m = json.loads(meta[0]["json_metadata"])
    spec = yaml.safe_load(m.get("view_text") or "") or {}
    dims = {d["name"]: d["expr"] for d in spec.get("dimensions", [])}
    meas = {d["name"]: d["expr"] for d in spec.get("measures", [])}
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
    return {
        "what": "The governed rule lives here — retrieved from the view definition and executed live.",
        "takeaway": (f"The certified metric view computes {a0.get('status')} for this patient"
                     f"{' (' + a0['gap_reason'] + ')' if a0.get('gap_reason') and a0.get('gap_reason') != 'Met' else ''}; "
                     f"{clinic} GSD rate {_pct(r0.get('rate'))}, poor control {_pct(r0.get('poor'))}."),
        "source": MV_GSD,
        "sections": [
            {"label": "The rule (from the metric view definition)", "kind": "code", "text": rule},
            {"label": "Rule applied to this patient's evidence", "kind": "kv", "data": {
                "Compliance Status": a0.get("status"), "Gap Reason": a0.get("gap_reason"),
                "Latest HbA1c": a0.get("evidence_value")}},
            {"label": f"{clinic} rollup by computed status", "kind": "table", "rows": roll},
            {"label": "Governance", "kind": "kv", "data": {
                "Certified (system.certification_status)": "✓ certified" if certified else "— not certified",
                "Clinical Domain tag": "✓" if domain else "—"}},
        ],
    }


def _page(pid, my, log):
    raw = _q(f"""SELECT value FROM read_files('{PAGES_VOL}/gsd.md', format => 'text', wholeText => true)""",
             None, log, "Read the Genie Ontology Page from the UC volume")
    text = raw[0]["value"] if raw else ""
    front, body = {}, text
    if text.startswith("---"):
        _, fm, body = text.split("---", 2)
        front = yaml.safe_load(fm) or {}
    meta = _q(f"DESCRIBE TABLE EXTENDED {MV_GSD} AS JSON", None, log,
              "Modeled metadata Genie indexes (metric-view comments + synonyms)")
    cols = json.loads(meta[0]["json_metadata"]).get("columns", [])
    pick = {"GSD Compliance Rate", "Compliance Status", "Poor Control Patients"}
    indexed = [{"field": c["name"], "comment": (c.get("comment") or "")[:140],
                "synonyms": ", ".join((c.get("metadata") or {}).get("synonyms", [])[:6])}
               for c in cols if c["name"] in pick]
    return {
        "what": "Human-modeled context Genie One prioritizes: the Page + the metric view's descriptions.",
        "takeaway": (f"Genie grounds GSD in this Page (domain: {front.get('domain', '—')}, owner: "
                     f"{front.get('owner', '—')}) and the metric view's comments/synonyms — "
                     f"\"{(front.get('synonyms') or [''])[-1]}\" resolves to GSD."),
        "source": f"{PAGES_VOL}/gsd.md",
        "sections": [
            {"label": "Page front matter", "kind": "kv", "data": {
                "name": front.get("name"), "domain": front.get("domain"),
                "synonyms": ", ".join(front.get("synonyms", [])),
                "related assets": ", ".join(a.split(".")[-1] for a in front.get("related_assets", []))}},
            {"label": "Page body (as Genie reads it)", "kind": "markdown", "text": body.strip()},
            {"label": "Metric-view metadata indexed alongside the Page", "kind": "table", "rows": indexed},
        ],
    }


def _ontobricks(pid, my, log):
    dx = _primary_dx(pid)["dx"]
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
    q_guide = (f"SELECT subject, predicate, object FROM {GRAPH} WHERE predicate IN ({gp}) AND "
               f"(subject IN ('{NS}Measure/GSD','{NS}Measure/SPD','{NS}DrugClass/DRUGCLASS-STATIN') "
               f" OR object IN ('{NS}Measure/GSD','{NS}Measure/SPD')) ORDER BY predicate, subject")
    q_asof = (f"SELECT max(last_altered) AS t FROM {ONTOBRICKS_CATALOG}.information_schema.tables "
              f"WHERE table_schema = '{ONTOBRICKS_SCHEMA}' AND table_name = '{ONTOBRICKS_TABLE}_graph'")
    q_path = (f"SELECT rx.object AS rx, i.object AS ing, c.object AS drug_class, r.object AS measure "
              f"FROM {GRAPH} rx JOIN {GRAPH} i ON i.subject = rx.object AND i.predicate = '{NS}hasIngredient' "
              f"JOIN {GRAPH} c ON c.subject = i.object AND c.predicate = '{NS}inDrugClass' "
              f"JOIN {GRAPH} r ON r.subject = c.object AND r.predicate = '{NS}recommendedFor' "
              f"WHERE rx.subject = :s AND rx.predicate = '{NS}prescribed'")
    log += [{"label": "Rationale path: prescribed → hasIngredient → inDrugClass → recommendedFor (4-hop join)",
             "sql": q_path},
            {"label": "Patient's typed edges (live triplestore)", "sql": q_patient},
            {"label": "Graph closure: walk subClassOf* at QUERY time (recursive)", "sql": q_walk},
            {"label": "Guideline edges reachable from the patient's measures", "sql": q_guide}]
    with ThreadPoolExecutor(max_workers=4) as ex:
        f_p = ex.submit(run_sql, q_patient, {"s": subj})
        f_w = ex.submit(run_sql, q_walk, {"n": f"{NS}icd/{dx}"})
        f_g = ex.submit(run_sql, q_guide, None)
        f_t = ex.submit(run_sql, q_asof, None)
        f_c = ex.submit(run_sql, f"SELECT ancestor_code FROM {C}.{ST}.icd10_closure WHERE descendant_code = :d "
                                 f"AND depth > 0 ORDER BY depth", {"d": dx})
        f_r = ex.submit(run_sql, q_path, {"s": subj})
        f_s = ex.submit(run_sql, f"SELECT CASE WHEN evidence_datetime IS NOT NULL THEN 'MET' ELSE 'NOT_MET' END AS s "
                                 f"FROM {C}.{S}.gold_adherence_gsd WHERE patient_id = :p AND measurement_year = :my",
                        {"p": pid, "my": my})
        prow, walk, guide = f_p.result(), f_w.result(), f_g.result()
        asof, mat, live, paths = f_t.result(), f_c.result(), f_s.result(), f_r.result()
    # names for the rx / ingredient nodes (the graph's nodes are opaque codes; RxNorm names come from the hierarchy)
    codes = sorted({_short(r[k]).split("/", 1)[-1] for r in paths for k in ("rx", "ing")} |
                   {_short(r["object"]).split("/", 1)[-1] for r in prow if r["predicate"].endswith("prescribed")})
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
            [{"code": _short(r["ancestor"]).replace("icd/", ""), "name": f"subClassOf* hop {r['hops']}",
              "depth": r["hops"]} for r in walk]
    graph_anc = [n["code"] for n in chain[1:]]
    mat_anc = [r["ancestor_code"] for r in mat]
    agrees = sorted(graph_anc) == sorted(mat_anc)
    guide_rows = [{"subject": _short(r["subject"]), "predicate": _short(r["predicate"]),
                   "object": _short(r["object"])} for r in guide]
    graph_gap = any(e["predicate"] == "hasCareGap" and e["object"] == "Measure/GSD" for e in edges)
    live_status = live[0]["s"] if live else None
    as_of = str(asof[0]["t"])[:16].replace("T", " ") if asof else "?"
    warns = []
    if live_status and graph_gap != (live_status == "NOT_MET"):
        warns.append(f"Graph snapshot (published {as_of} UTC) says GSD care gap = {graph_gap}, but the live metric "
                     f"view computes {live_status}. The triplestore lags the pipeline until Ontobricks republishes.")
    path_txt = ""
    if paths:
        p0 = paths[0]
        drug = names.get(_short(p0["rx"]).split("/", 1)[-1], _short(p0["rx"]))
        cls = _short(p0["drug_class"]).split("/")[-1]
        meas = _short(p0["measure"]).split("/")[-1]
        path_txt = (f"Graph-native path: this patient is prescribed {drug} → ingredient → {cls} → recommendedFor "
                    f"{meas} (4 hops no closure table expresses). ")
    takeaway = (path_txt + f"subClassOf* walked live from icd/{dx}: {' → '.join(n['code'] for n in chain)} "
                f"({len(chain) - 1} hops, query-time) — {'identical to' if agrees else 'differs from'} the "
                f"materialized icd10_closure.")
    return {
        "what": "The explicit OWL graph, queried live: typed edges + a closure computed by traversal.",
        "takeaway": takeaway,
        "source": f"{GRAPH} (published {as_of} UTC)",
        "sections": [
            *([{"label": "Rationale path — why this patient's drug connects to a measure (graph-native, 4 hops)",
                "kind": "path", "steps": [
                    {"node": f"Patient/{pid[:8]}", "name": "this patient", "edge": "prescribed"},
                    {"node": _short(pth["rx"]), "name": names.get(_short(pth["rx"]).split("/", 1)[-1], ""),
                     "edge": "hasIngredient"},
                    {"node": _short(pth["ing"]), "name": names.get(_short(pth["ing"]).split("/", 1)[-1], ""),
                     "edge": "inDrugClass"},
                    {"node": _short(pth["drug_class"]), "name": "drug class", "edge": "recommendedFor"},
                    {"node": _short(pth["measure"]), "name": "HEDIS measure the patient is eligibleFor", "edge": ""}]}
               for pth in paths[:2]]),
            {"label": "Graph closure — subClassOf* walked live", "kind": "chain", "nodes": chain},
            {"label": "Closure comparison", "kind": "kv", "data": {
                "Graph (traversal, query-time)": " → ".join(graph_anc) or "—",
                "icd10_closure (materialized, build-time)": " → ".join(mat_anc) or "—",
                "Same ancestors": "✓" if agrees else "✗"}},

            {"label": "Patient's typed edges (grouped)", "kind": "kv", "data": {
                "hasDiagnosis": ", ".join(e["object"].replace("icd/", "") for e in edges if e["predicate"] == "hasDiagnosis"),
                "eligibleFor": ", ".join(e["object"].replace("Measure/", "") for e in edges if e["predicate"] == "eligibleFor"),
                "hasCareGap (graph snapshot)": ", ".join(e["object"].replace("Measure/", "") for e in edges
                                                         if e["predicate"] == "hasCareGap") or "none",
                "prescribed": f"{sum(e['predicate'] == 'prescribed' for e in edges)} drugs — " + ", ".join(
                    names.get(e["object"].split("/", 1)[-1], e["object"]) for e in edges
                    if e["predicate"] == "prescribed")[:220]}},
            {"label": "Guideline knowledge for GSD / SPD (cross-vocabulary)", "kind": "triples", "rows": guide_rows},
        ],
        "warnings": warns,
    }


_STAGES = {"protocol": ("Source — care-protocol document", _protocol),
           "bronze": ("Bronze — raw EHR rows", _bronze),
           "silver": ("Silver — conformed condition + observations", _silver),
           "closure": ("Terminology — ICD-10 subsumption", _closure),
           "cohort": ("Cohort — measure denominators", _cohort),
           "gold": ("Gold — per-patient evidence", _gold),
           "metric": ("Semantic — certified metric view", _metric),
           "page": ("Ontology — Genie Ontology Page", _page),
           "ontobricks": ("Ontology — Ontobricks graph (live)", _ontobricks)}


@router.get("/patient/{patient_id}/stage/{key}")
def stage_detail(patient_id: str, key: str):
    if key not in _STAGES:
        raise HTTPException(404, f"Unknown stage {key!r}; known: {', '.join(_STAGES)}")
    title, fn = _STAGES[key]
    log: list = []
    t0 = time.time()
    try:
        out = fn(patient_id, MEASUREMENT_YEAR, log)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 — surface the real failure to the click-in
        raise HTTPException(502, f"{key} retrieval failed: {type(e).__name__}: {str(e)[:300]}")
    return {"key": key, "title": title, "patient_id": patient_id, "queries": log,
            "latency_s": round(time.time() - t0, 1), "warnings": out.pop("warnings", []), **out}
