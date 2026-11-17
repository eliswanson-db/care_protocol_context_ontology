"""Clinical Study lab API (demo_id life_sciences_clinical). Every route is bound to this demo by
`require_demo` in app.py. Read-only. Responses carry `demo_id` so the SPA can refuse a cross-demo payload.

User input never reaches SQL unchecked: participant/concept/rule ids go through the whitelists in the A6 tools
(ls_a6) or are passed as named parameters.
"""

from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException

from ..config import CATALOG
from ..ls_a6 import clinical_study_supervisor as sup
from ..ls_a6.clinical_study_tools import RULE_VERSIONS, InputError, make_tools
from ..readiness import component
from ..warehouse import run_sql

router = APIRouter(prefix="/ls")
DEMO = "life_sciences_clinical"
CS, STD, SEM = (
    f"{CATALOG}.clinical_study",
    f"{CATALOG}.clinical_study_standards",
    f"{CATALOG}.clinical_study_semantic",
)
TOOLS = make_tools(CATALOG)
_cache: dict = {}


def _q(sql: str) -> list[dict]:
    return run_sql(sql)


def _run_id() -> str:
    hit = _cache.get("run_id")
    if hit and time.time() - hit[0] < 60:
        return hit[1]
    r = _q(f"SELECT max(execution_run_id) AS r FROM {CS}.gold_endpoint_result")
    _cache["run_id"] = (time.time(), r[0]["r"] if r else None)
    return _cache["run_id"][1]


def cached(key: tuple, fn, ttl: float = 600):
    """Cache keyed by demo + execution run + arguments: a rerun with new data never serves a stale answer."""
    k = (DEMO, _run_id(), *key)
    hit = _cache.get(k)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    v = fn()
    _cache[k] = (time.time(), v)
    return v


def _stamp(d: dict) -> dict:
    return {"demo_id": DEMO, "execution_run_id": _run_id(), **d}


def parallel(**fns):
    """Run independent queries concurrently (each warehouse statement costs ~0.5-1 s)."""
    with ThreadPoolExecutor(max_workers=min(8, len(fns))) as ex:
        futs = {k: ex.submit(f) for k, f in fns.items()}
        return {k: f.result() for k, f in futs.items()}


def _tool(name: str, **kw):
    try:
        return TOOLS[name](_q, **kw)
    except InputError as e:
        raise HTTPException(400, str(e)) from e


# --------------------------------------------------------------------------------------------- overview
@router.get("/overview")
def overview():
    def build():
        r = parallel(
            studies=lambda: _q(
                f"SELECT study_id, title, phase, duration_weeks FROM {STD}.study ORDER BY study_id"
            ),
            study_versions=lambda: _q(
                f"SELECT study_id, protocol_version, sap_version, effective_date, amendment, "
                f"change_summary FROM {STD}.study_version ORDER BY study_id, effective_date"
            ),
            rule_versions=lambda: _q(
                f"SELECT endpoint_version, study_id, protocol_version, sap_version, "
                f"window_half_width_days, baseline_method, review_state FROM {STD}.rule_version "
                f"ORDER BY endpoint_version"
            ),
            endpoint_summary=lambda: _q(
                f"SELECT `Rule Version` AS rule_version, `Arm` AS arm, MEASURE(`Participants In FAS`) AS fas, "
                f"MEASURE(`Participants With Derived Endpoint`) AS derived, MEASURE(`Endpoint Missingness Rate`) AS "
                f"missingness, MEASURE(`Mean Percent Change`) AS mean_pchg FROM {SEM}.endpoint_result_metrics "
                f"GROUP BY ALL ORDER BY 1, 2"
            ),
            populations=lambda: _q(
                f"SELECT `Study` AS study, MEASURE(`Screened Participants`) AS screened, MEASURE(`Rule Eligible "
                f"Participants`) AS eligible, MEASURE(`Randomized Participants`) AS randomized, MEASURE(`FAS "
                f"Participants`) AS fas, MEASURE(`PPS Participants`) AS pps, MEASURE(`Enrolled In Error`) AS "
                f"enrolled_in_error FROM {SEM}.participant_population_metrics GROUP BY ALL ORDER BY 1"
            ),
            data_quality=lambda: _q(
                f"SELECT check_id, severity, n_violations FROM {CS}.dq_semantic_validation_summary ORDER BY 1"
            ),
            verification=lambda: _q(
                f"SELECT status, n_failures, verified_at FROM {CS}.gold_verification_run ORDER BY "
                f"verified_at DESC LIMIT 1"
            ),
        )
        r["verification"] = r["verification"][0] if r["verification"] else None
        return r

    return _stamp(cached(("overview",), build))


# --------------------------------------------------------------------------------------------- participants
@router.get("/tracers")
def tracers():
    rows = cached(
        ("tracers",),
        lambda: _q(
            f"SELECT t.USUBJID AS usubjid, t.STUDYID AS study_id, t.tracer_id, t.title, p.FASFL AS fas, p.PPSFL AS pps, "
            f"p.rule_eligible FROM {CS}.gold_tracer_registry t LEFT JOIN {CS}.gold_participant_population p USING "
            f"(USUBJID) ORDER BY t.tracer_id"
        ),
    )
    return _stamp({"tracers": rows})


@router.get("/participants")
def search_participants(q: str = "", limit: int = 25):
    if not re.match(r"^[A-Za-z0-9-]{0,20}$", q):
        raise HTTPException(400, "search: letters, digits and '-' only")
    rows = run_sql(
        f"SELECT USUBJID AS usubjid, STUDYID AS study_id, SITEID AS site, ARMCD AS arm, FASFL AS fas "
        f"FROM {CS}.gold_participant_population WHERE upper(USUBJID) LIKE upper(:p) ORDER BY USUBJID "
        f"LIMIT {max(1, min(limit, 50))}",
        {"p": f"%{q}%"},
    )
    return _stamp({"participants": rows})


@router.get("/participant/{usubjid}")
def participant(usubjid: str, rule_version: str | None = None):
    def build():
        if not re.match(r"^CSL-[AB]-(?:\d{3}-\d{4}|FX-\d{2})$", usubjid):
            raise HTTPException(400, f"invalid participant id {usubjid!r}")
        study = usubjid.split("-")[1]
        versions = sorted(v for v in RULE_VERSIONS if v.startswith(f"EP-{study}-"))
        rv = rule_version or versions[-1]
        if rv not in versions:
            raise HTTPException(400, f"rule version {rv} does not apply to study CSL-{study}")
        ep, r_code = rv.split(".")
        fns = {
            f"trace:{v}": (lambda v=v: _tool("participant_trace", usubjid=usubjid, endpoint_version=v))
            for v in versions
        }
        r = parallel(
            **fns,
            el=lambda: _tool("eligibility_explain", usubjid=usubjid),
            rule=lambda: _tool("rule_definition", endpoint_version=rv),
            raw=lambda: run_sql(
                f"SELECT record_id, visit, vsdtc, vstestcd, vsorres, vsorresu, vsstat, _source_file "
                f"FROM {CS}.bronze_edc_vs WHERE usubjid = :u AND vstestcd = 'WEIGHT' ORDER BY vsdtc, "
                f"record_id",
                {"u": usubjid},
            ),
            prov=lambda: run_sql(
                f"SELECT subject, predicate, object FROM {CS}.gold_provenance_edge WHERE subject = :s "
                f"OR subject = :rv OR subject IN (SELECT obs_id FROM {CS}.gold_endpoint_candidate "
                f"WHERE USUBJID = :u AND decision = 'SELECTED' AND endpoint_id = :ep AND rule_version "
                f"= :rc) ORDER BY predicate",
                {"s": f"{usubjid}|{ep}|{r_code}", "u": usubjid, "rv": rv, "ep": ep, "rc": r_code},
            ),
            dm=lambda: run_sql(
                f"SELECT USUBJID, STUDYID, SITEID, COUNTRY, AGE, SEX, ARMCD, RFXSTDTC, DMDTC, "
                f"CPL_SCREEN_OUTCOME FROM {CS}.silver_dm WHERE USUBJID = :u",
                {"u": usubjid},
            ),
            tr=lambda: run_sql(
                f"SELECT tracer_id, title FROM {CS}.gold_tracer_registry WHERE USUBJID = :u", {"u": usubjid}
            ),
        )
        traces = {v: r[f"trace:{v}"] for v in versions}
        t, el, rule, raw, prov, dm, tr = traces[rv], r["el"], r["rule"], r["raw"], r["prov"], r["dm"], r["tr"]
        return {
            "usubjid": usubjid,
            "rule_version": rv,
            "rule_versions": versions,
            "demographics": dm[0] if dm else None,
            "tracer": tr[0] if tr else None,
            "trace": t,
            "by_version": {
                v: {
                    "result_status": x.get("result_status"),
                    "pct_change": x.get("pct_change"),
                    "followup": next(
                        (
                            c["obs_id"]
                            for c in x.get("candidates", [])
                            if c["role"] == "FOLLOWUP" and c["decision"] == "SELECTED"
                        ),
                        None,
                    ),
                    "exclusion_reason": x.get("exclusion_reason"),
                }
                for v, x in traces.items()
            },
            "raw_source": raw,
            "rule": rule,
            "eligibility": el,
            "provenance": prov,
        }

    return _stamp(cached(("participant", usubjid, rule_version), build))


# --------------------------------------------------------------------------------------------- amendment lab
@router.get("/amendment")
def amendment(site: str | None = None):
    def build():
        r = parallel(
            impact=lambda: _tool("amendment_impact", site_id=site, limit=200),
            diff=lambda: _tool("compare_endpoints", a="EP-A-WT24.R1", b="EP-A-WT24.R2"),
            s1=lambda: _tool("endpoint_summary", endpoint_version="EP-A-WT24.R1"),
            s2=lambda: _tool("endpoint_summary", endpoint_version="EP-A-WT24.R2"),
            by_site=lambda: _q(
                f"SELECT `Site` AS site, MEASURE(`Participants Compared`) AS compared, MEASURE(`Participants "
                f"Became Derivable`) AS recovered FROM {SEM}.amendment_impact_metrics GROUP BY ALL HAVING "
                f"recovered > 0 ORDER BY recovered DESC"
            ),
        )
        impact, diff, s1, s2, by_site = r["impact"], r["diff"], r["s1"], r["s2"], r["by_site"]
        return {
            "impact": impact,
            "definition_diff": diff,
            "summary_r1": s1,
            "summary_r2": s2,
            "by_site": by_site,
            "named_examples": [x for x in impact["affected"] if "-FX-" in x["USUBJID"]],
        }

    return _stamp(cached(("amendment", site), build))


# --------------------------------------------------------------------------------------------- standards explorer
_CONCEPT = re.compile(r"^[A-Za-z_]+:[A-Za-z0-9_.\-]+$")


@router.get("/concepts/search")
def concept_search(q: str, limit: int = 30):
    if not 2 <= len(q) <= 60:
        raise HTTPException(400, "query length 2-60")
    rows = run_sql(
        f"SELECT concept_id, scheme, label, concept_type FROM {STD}.kb_concept WHERE lower(label) LIKE "
        f"lower(:p) OR concept_id = :id ORDER BY (lower(label) = lower(:q)) DESC, length(label), concept_id "
        f"LIMIT {max(1, min(limit, 50))}",
        {"p": f"%{q}%", "id": q, "q": q},
    )
    return _stamp({"results": rows})


@router.get("/concepts/node")
def concept_node(id: str):  # noqa: A002
    if not _CONCEPT.match(id):
        raise HTTPException(400, "invalid concept id")

    def build():
        c = run_sql(f"SELECT * FROM {STD}.kb_concept WHERE concept_id = :i", {"i": id})
        if not c:
            raise HTTPException(404, f"{id} not in the knowledge base")
        scheme = c[0]["scheme"]
        clo = {
            "MONDO": "mondo_closure",
            "MEDRT": "medrt_class_closure",
            "MESH": "mesh_closure",
            "COSMOS_BC": "bc_closure",
        }.get(scheme)
        fns = {
            "out_e": lambda: run_sql(
                f"SELECT e.predicate, e.object AS other, k.label, k.scheme, e.authority, e.source_artifact, "
                f"e.release FROM {STD}.kb_edge e LEFT JOIN {STD}.kb_concept k ON k.concept_id = e.object WHERE "
                f"e.subject = :i ORDER BY e.predicate, k.label LIMIT 200",
                {"i": id},
            ),
            "in_e": lambda: run_sql(
                f"SELECT e.predicate, e.subject AS other, k.label, k.scheme, e.authority, e.source_artifact, "
                f"e.release FROM {STD}.kb_edge e LEFT JOIN {STD}.kb_concept k ON k.concept_id = e.subject WHERE "
                f"e.object = :i ORDER BY e.predicate, k.label LIMIT 200",
                {"i": id},
            ),
            "anc": lambda: run_sql(
                f"SELECT ancestor_code, ancestor_name, depth FROM {STD}.{clo} WHERE descendant_code = :i AND "
                f"depth > 0 ORDER BY depth, ancestor_code",
                {"i": id},
            )
            if clo
            else [],
        }
        if scheme == "MONDO":
            for cls in ("WRC-V1", "WRC-V2", "EXCL-MH-V1"):
                fns[cls] = lambda cls=cls: _tool("class_membership", class_id=cls, concept_id=id)
            fns["ci"] = lambda: {"class_id": "CI-STUDY-DRUG-CLASS", **_tool("contraindication_check", concept_id=id)}
        if id.startswith("COSMOS_BC:"):
            fns["mapping"] = lambda: _tool("dataset_mapping", concept_id=id)
        r = parallel(**fns)
        out_e, in_e, anc = r["out_e"], r["in_e"], r["anc"]
        classes = [r[k] for k in ("WRC-V1", "WRC-V2", "EXCL-MH-V1", "ci") if k in r]
        mapping = r.get("mapping")
        return {
            "concept": c[0],
            "outgoing": out_e,
            "incoming": in_e,
            "ancestors": anc,
            "classes": classes,
            "mapping": mapping,
            "custom_namespace": [e for e in out_e + in_e if e["predicate"].startswith("cpl:")],
        }

    return _stamp(cached(("node", id), build))


@router.get("/rules")
def rules():
    def build():
        return {
            "rule_versions": _q(f"SELECT * FROM {STD}.rule_version ORDER BY endpoint_version"),
            "assertions": _q(
                f"SELECT a.*, d.status AS document_status FROM {CS}.rule_assertion a JOIN "
                f"{CS}.doc_document d USING (document_id) ORDER BY a.review_state, a.document_id"
            ),
            "documents": _q(
                f"SELECT document_id, title, study_id, doc_type, version, status, effective_date "
                f"FROM {CS}.doc_document ORDER BY study_id, effective_date"
            ),
        }

    return _stamp(cached(("rules",), build))


# --------------------------------------------------------------------------------------------- arena
@lru_cache(maxsize=1)
def _questions() -> list[dict]:
    return yaml.safe_load((Path(__file__).resolve().parents[1] / "ls_questions.yaml").read_text())[
        "questions"
    ]


@router.get("/arena/questions")
def arena_questions():
    return _stamp({"questions": [{k: q[k] for k in ("qid", "category", "question")} for q in _questions()]})


def _lens_sql(sql: str | None) -> dict | None:
    if not sql:
        return None
    s = sql.replace("{catalog}", CATALOG)
    t0 = time.time()
    try:
        rows = _q(s)
        return {"sql": s, "rows": rows, "latency_s": round(time.time() - t0, 2)}
    except Exception as e:  # noqa: BLE001
        return {"sql": s, "error": str(e)[:300]}


@router.get("/arena/run")
def arena_run(qid: str):
    q = next((x for x in _questions() if x["qid"] == qid), None)
    if q is None:
        raise HTTPException(404, f"unknown question {qid}")

    def build():
        t0 = time.time()
        r = sup.route(q["question"])
        a6 = {"route": r}
        if r["tool"] not in ("abstain", "clarify", "genie_fallback"):
            a6["result"] = TOOLS[r["tool"]](_q, **r["kwargs"])
        a6["latency_s"] = round(time.time() - t0, 2)
        ready = parallel(
            ontology=lambda: component(DEMO, "ontology"), search=lambda: component(DEMO, "search")
        )
        return {
            "qid": qid,
            "question": q["question"],
            "category": q["category"],
            "lenses": {
                "a6_tools": a6,
                "metric_view": _lens_sql(q.get("metric_view"))
                or {"not_applicable": "no governed metric for this question type"},
                "closure": _lens_sql(q.get("closure"))
                or {"not_applicable": "no hierarchy needed, or the closure cannot express it"},
                "graph": {"state": ready["ontology"]["state"], "detail": ready["ontology"]["detail"]},
                "rag": {"state": ready["search"]["state"], "detail": ready["search"]["detail"]},
                "genie": {"deferred": True, "endpoint": f"/api/ls/arena/genie?qid={qid}"},
            },
        }

    return _stamp(cached(("arena", qid), build, ttl=300))


@router.get("/arena/genie")
def arena_genie(qid: str):
    """Genie Ontology lens = Genie One, the workspace front door (same surface as the HEDIS lens), run live in the
    background. We report what it actually retrieved: Pages and inferred snippets, labelled by demo (the workspace
    is shared, so other-demo retrieval is shown, not hidden), the assets it read and the agent it delegated to."""
    from ..genie_trace import get_trace

    q = next((x for x in _questions() if x["qid"] == qid), None)
    if q is None:
        raise HTTPException(404, f"unknown question {qid}")
    question = f"In the Clinical Study Context & Evidence Lab: {q['question']}"
    r = get_trace(question, demo=DEMO)
    if r["status"] != "done":
        return _stamp({"qid": qid, "status": r["status"], "error": r.get("error")})
    t = r["trace"]

    def items(kind: str) -> list[dict]:
        seen, out = set(), []
        for ss in t["snippet_searches"]:
            for x in ss[kind]:
                k = x.get("name") or x.get("headline")
                if k not in seen:
                    seen.add(k)
                    out.append(x)
        return out

    pages, snips = items("pages"), items("snippets")

    def by_demo(xs: list[dict]) -> dict:
        out: dict[str, int] = {}
        for x in xs:
            out[x["demo"]] = out.get(x["demo"], 0) + 1
        return out

    return _stamp({
        "qid": qid, "status": "done", "surface": "Genie One (Genie Ontology), AI-generated", "question": question,
        "answer": t["answer"], "latency_s": r.get("latency_s"),
        "pages": [{"name": x["name"], "relevance": x.get("relevance"), "demo": x["demo"]} for x in pages[:6]],
        "pages_by_demo": by_demo(pages), "snippets_by_demo": by_demo(snips),
        "top_snippets": [{"headline": x["headline"], "type": x.get("type"), "demo": x["demo"]} for x in snips[:4]],
        "pages_read": [x.get("name") for x in t["pages_read"]],
        "agents": [x.get("name") for x in t["agents"]],
        "tool_order": t["tool_order"],
    })
