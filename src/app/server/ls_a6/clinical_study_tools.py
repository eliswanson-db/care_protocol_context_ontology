"""Governed, deterministic tools for the Clinical Study lab (A6 custom MCP, demo_id life_sciences_clinical).

Same contract as care_protocol_tools: each tool is a fixed, reviewed query over the governed layer, takes a
`query(sql) -> list[dict]` callable, and never lets an LLM write SQL. Inputs are validated against whitelists
(identifiers match strict patterns or the live registry) BEFORE they reach SQL, so nothing user-typed is ever
interpolated unchecked. SYNTHETIC demo; results are descriptive.

Tools return evidence alongside every answer (rule version, document section, source records, ontology path),
and refuse questions that would pool studies or rule versions.
"""

from __future__ import annotations

import re

DEMO_ID = "life_sciences_clinical"
DISCLAIMER = "SYNTHETIC demo (Clinical Study lab). Descriptive only; not evidence of efficacy."

RULE_VERSIONS = {"EP-A-WT24.R1", "EP-A-WT24.R2", "EP-B-WT24.R1"}
STUDIES = {"CSL-A", "CSL-B"}
CLASSES = {"WRC-V1", "WRC-V2", "EXCL-MH-V1"}
GLP1_EPC = "MEDRT:N0000178480"
_USUBJID = re.compile(r"^CSL-[AB]-(?:\d{3}-\d{4}|FX-\d{2})$")
_CONCEPT = re.compile(
    r"^(MONDO:\d{7}|RXNORM:\d+|MEDRT:N\d{10}|MESH:[CD]\d{6,9}|COSMOS_BC:C\d+|COSMOS_DSS:[A-Z0-9_]+)$"
)


class InputError(ValueError):
    """A tool argument failed validation (returned to the caller as an error, never executed)."""


def _rv(endpoint_version: str) -> str:
    if endpoint_version not in RULE_VERSIONS:
        raise InputError(f"unknown rule version {endpoint_version!r}; one of {sorted(RULE_VERSIONS)}")
    return endpoint_version


def _subj(usubjid: str) -> str:
    if not _USUBJID.match(usubjid or ""):
        raise InputError(f"invalid participant id {usubjid!r}")
    return usubjid


def _concept(cid: str) -> str:
    if not _CONCEPT.match(cid or ""):
        raise InputError(f"invalid concept id {cid!r}")
    return cid


def make_tools(catalog: str):
    cs, std, sem = (
        f"{catalog}.clinical_study",
        f"{catalog}.clinical_study_standards",
        f"{catalog}.clinical_study_semantic",
    )

    def _rule(query, ev: str) -> dict:
        r = query(
            f"SELECT v.*, s.document_id, s.section FROM {std}.rule_version v LEFT JOIN {std}.rule_document_support s "
            f"ON s.rule_id = v.endpoint_version WHERE v.endpoint_version = '{ev}'"
        )
        if not r:
            raise InputError(f"rule version {ev} not loaded")
        return r[0]

    def _cite(r: dict) -> dict:
        return {
            "rule_version": r["endpoint_version"],
            "protocol_version": r["protocol_version"],
            "sap_version": r["sap_version"],
            "document": r["document_id"],
            "section": r["section"],
            "review_state": r["review_state"],
            "approved_by": r["approved_by"],
        }

    def endpoint_summary(query, endpoint_version: str, population: str = "FAS") -> dict:
        """Week 24 % change summary for ONE study and rule version, by arm (governed metric view)."""
        ev = _rv(endpoint_version)
        if population not in ("FAS", "PPS"):
            raise InputError("population must be FAS or PPS")
        flag = "`In FAS` = 'Y'" if population == "FAS" else "`In PPS` = 'Y'"
        rows = query(
            f"SELECT `Arm` AS arm, MEASURE(`Participants Evaluated`) AS n, MEASURE(`Participants With Valid Baseline`) "
            f"AS valid_baseline, MEASURE(`Participants With Qualifying Week 24 Observation`) AS qualifying_week24, "
            f"MEASURE(`Participants With Derived Endpoint`) AS derived, MEASURE(`Mean Percent Change`) AS mean_pchg, "
            f"MEASURE(`Median Percent Change`) AS median_pchg FROM {sem}.endpoint_result_metrics WHERE `Rule Version` "
            f"= '{ev}' AND {flag} GROUP BY ALL ORDER BY arm"
        )
        r = _rule(query, ev)
        out = []
        for x in rows:
            n, d = int(x["n"]), int(x["derived"])
            out.append(
                {
                    "arm": x["arm"],
                    "population_n": n,
                    "valid_baseline": int(x["valid_baseline"]),
                    "qualifying_week24": int(x["qualifying_week24"]),
                    "derived": d,
                    "missingness": round(1 - d / n, 4) if n else None,
                    "mean_pct_change": None if x["mean_pchg"] is None else round(float(x["mean_pchg"]), 2),
                    "median_pct_change": None
                    if x["median_pchg"] is None
                    else round(float(x["median_pchg"]), 2),
                }
            )
        return {
            "study_id": r["study_id"],
            "population": population,
            "by_arm": out,
            "citation": _cite(r),
            "note": DISCLAIMER,
        }

    def participant_trace(query, usubjid: str, endpoint_version: str) -> dict:
        """One participant's endpoint under one rule version: every candidate observation with its decision and
        reason, the source records, the calculation and the rule citation."""
        u, ev = _subj(usubjid), _rv(endpoint_version)
        res = query(
            f"SELECT * FROM {cs}.gold_endpoint_result WHERE USUBJID = '{u}' AND endpoint_version = '{ev}'"
        )
        if not res:
            return {
                "usubjid": u,
                "endpoint_version": ev,
                "error": "no result row (not randomized, or other study)",
            }
        r = res[0]
        rv = ev.split(".")[1]
        cands = query(
            f"SELECT c.obs_id, c.source_record_id, c.vsseq, c.visit, c.vsdtc, c.study_day, c.weight_kg, c.role, "
            f"c.decision, c.reason, c.days_from_target, v.VSORRES AS orres, v.CPL_RAW_UNIT AS raw_unit, "
            f"v.VSORRESU AS ct_unit FROM {cs}.gold_endpoint_candidate c LEFT JOIN {cs}.silver_vs v ON v.CPL_OBS_ID = "
            f"c.obs_id WHERE c.USUBJID = '{u}' AND c.endpoint_id = '{ev.split('.')[0]}' AND c.rule_version = '{rv}' "
            f"ORDER BY c.vsdtc, c.vsseq"
        )
        calc = None
        if r["result_status"] == "DERIVED":
            calc = (
                f"100 * ({float(r['AVAL_FU']):.4f} - {float(r['BASE']):.4f}) / {float(r['BASE']):.4f} = "
                f"{float(r['PCHG']):.6f} (display {r['PCHG_DISPLAY']})"
            )
        return {
            "usubjid": u,
            "endpoint_version": ev,
            "result_status": r["result_status"],
            "exclusion_reason": r["exclusion_reason"],
            "reference_date": r["reference_date"],
            "target_date": r["followup_target_date"],
            "baseline_kg": r["BASE"],
            "followup_kg": r["AVAL_FU"],
            "pct_change": r["PCHG"],
            "calculation": calc,
            "candidates": cands,
            "execution_run_id": r["execution_run_id"],
            "citation": _cite(_rule(query, ev)),
        }

    def amendment_impact(query, site_id: str | None = None, limit: int = 20) -> dict:
        """CSL-A Amendment 1 (R1 ±7 d -> R2 ±14 d): counts, top sites, and the affected participants."""
        if site_id is not None and not re.match(r"^SITE-\d{3}$", site_id):
            raise InputError(f"invalid site {site_id!r}")
        where = f"WHERE `Site` = '{site_id}'" if site_id else ""
        tot = query(
            f"SELECT MEASURE(`Participants Compared`) AS compared, MEASURE(`Participants Became Derivable`) AS became, "
            f"MEASURE(`Participants With Changed Selected Observation`) AS changed_selection, MEASURE(`Participants "
            f"With Changed Endpoint Value`) AS changed_value, MEASURE(`Participants With Changed Eligible Candidates`) "
            f"AS more_candidates FROM {sem}.amendment_impact_metrics {where}"
        )[0]
        sites = query(
            f"SELECT `Site` AS site, MEASURE(`Participants Became Derivable`) AS recovered FROM "
            f"{sem}.amendment_impact_metrics GROUP BY ALL ORDER BY recovered DESC LIMIT 5"
        )
        sfilter = f"AND d.SITEID = '{site_id}'" if site_id else ""
        aff = query(
            f"SELECT a.USUBJID, d.SITEID AS site, a.status_from, a.status_to, a.pchg_to, a.explanation FROM "
            f"{cs}.gold_amendment_impact a JOIN {cs}.silver_dm d USING (USUBJID) WHERE (a.endpoint_became_derivable "
            f"OR a.selected_followup_changed OR a.eligible_candidates_changed) {sfilter} "
            f"ORDER BY (a.USUBJID LIKE '%-FX-%') DESC, a.USUBJID "
            f"LIMIT {max(1, min(int(limit), 200))}"
        )
        return {
            "comparison": "EP-A-WT24.R1 -> EP-A-WT24.R2",
            "site": site_id,
            "counts": {k: int(v) for k, v in tot.items()},
            "top_sites_recovered": sites,
            "affected": aff,
            "citations": [_cite(_rule(query, "EP-A-WT24.R1")), _cite(_rule(query, "EP-A-WT24.R2"))],
            "note": "Closest-to-target selection: a wider window can add a record but never replace one that "
            "already qualified.",
        }

    def rule_definition(query, endpoint_version: str) -> dict:
        """The executable rule, the document section that states it, and the approved assertions that agree."""
        ev = _rv(endpoint_version)
        r = _rule(query, ev)
        sec = query(
            f"SELECT heading, text FROM {cs}.doc_section WHERE document_id = '{r['document_id']}' AND "
            f"section_number = '{r['section']}'"
        )
        asr = query(
            f"SELECT assertion_type, value, review_state FROM {cs}.rule_assertion WHERE rule_ref = '{ev}' "
            f"ORDER BY assertion_type"
        )
        keys = [
            "baseline_method",
            "baseline_window_start",
            "baseline_window_end",
            "same_day_predose",
            "target_offset_days",
            "window_half_width_days",
            "tie_breaker",
            "formula",
            "population",
        ]
        return {
            "rule": {k: r[k] for k in keys},
            "citation": _cite(r),
            "section_text": sec[0] if sec else None,
            "assertions": asr,
        }

    def rule_status(query, study_id: str, assertion_type: str = "FOLLOWUP_WINDOW_HALF_WIDTH") -> dict:
        """Every extracted rule statement of one type for a study, with its review state. Answers 'has the wider
        window been approved?': only approved statements correspond to executable rules."""
        if study_id not in STUDIES:
            raise InputError(f"study must be one of {sorted(STUDIES)}")
        if not re.match(r"^[A-Z_]+$", assertion_type):
            raise InputError("invalid assertion type")
        rows = query(
            f"SELECT a.document_id, d.status AS document_status, a.section_number, a.value, a.review_state, "
            f"a.rule_ref, a.superseded_by, a.review_note FROM {cs}.rule_assertion a JOIN {cs}.doc_document d USING "
            f"(document_id) WHERE d.study_id = '{study_id}' AND a.assertion_type = '{assertion_type}' "
            f"ORDER BY a.review_state, a.document_id"
        )
        executable = query(
            f"SELECT endpoint_version, window_half_width_days FROM {std}.rule_version WHERE "
            f"study_id = '{study_id}' AND review_state = 'approved' ORDER BY endpoint_version"
        )
        return {
            "study_id": study_id,
            "assertion_type": assertion_type,
            "statements": rows,
            "executable_rules": executable,
            "note": "Candidates and rejected statements never execute; reviews are demo fixtures.",
        }

    def compare_endpoints(query, a: str, b: str) -> dict:
        """Parameter-by-parameter comparison of two endpoint rule versions (are they equivalent?)."""
        ra, rb = _rule(query, _rv(a)), _rule(query, _rv(b))
        keys = [
            "study_id",
            "biomedical_concept",
            "formula",
            "population",
            "baseline_method",
            "baseline_window_start",
            "baseline_window_end",
            "same_day_predose",
            "target_offset_days",
            "window_half_width_days",
            "tie_breaker",
        ]
        diff = [{"parameter": k, a: ra[k], b: rb[k]} for k in keys if str(ra[k]) != str(rb[k])]
        same = [k for k in keys if str(ra[k]) == str(rb[k])]
        return {
            "a": a,
            "b": b,
            "equivalent": not [d for d in diff if d["parameter"] != "study_id"],
            "differences": diff,
            "same": same,
            "citations": [_cite(ra), _cite(rb)],
            "note": "Same biomedical concept and formula do not make two endpoints equivalent; never pool them.",
        }

    def class_membership(query, class_id: str, concept_id: str) -> dict:
        """Is a MONDO concept a member of a concept class? is_a* via mondo_closure, minus carve-outs (exclusion
        wins); WRC-V2 inherits WRC-V1 roots."""
        if class_id not in CLASSES:
            raise InputError(f"class must be one of {sorted(CLASSES)}")
        c = _concept(concept_id)
        cls_ids = "('WRC-V1', 'WRC-V2')" if class_id == "WRC-V2" else f"('{class_id}')"
        hits = query(
            f"SELECT r.class_id, c.ancestor_code AS root, c.ancestor_name AS root_label, c.depth, r.kind FROM "
            f"{std}.mondo_closure c JOIN {std}.class_root r ON r.concept_id = c.ancestor_code AND r.class_id IN "
            f"{cls_ids} AND r.kind IN ('root', 'exclude_root') WHERE c.descendant_code = '{c}' ORDER BY r.kind, c.depth"
        )
        label = query(f"SELECT label FROM {std}.kb_concept WHERE concept_id = '{c}'")
        roots = [h for h in hits if h["kind"] == "root"]
        excl = [h for h in hits if h["kind"] == "exclude_root"]
        return {
            "class_id": class_id,
            "concept_id": c,
            "label": label[0]["label"] if label else None,
            "member": bool(roots) and not excl,
            "via_roots": roots,
            "excluded_by": excl,
            "method": "transitive closure (mondo_closure), exclusion wins",
        }

    def contraindication_check(query, concept_id: str) -> dict:
        """Is a MONDO condition contraindicated for any GLP-1 RA class member? Sound (broadening-only) multi-hop:
        condition -> is_a* ancestors -> equivalent MeSH record -> broader MeSH records -> MeSH concept <- CI_with
        <- drug in class. Product-specific hypersensitivity (D004342) is excluded by the study rule."""
        c = _concept(concept_id)
        rows = query(f"""
WITH anc AS (SELECT ancestor_code AS d, depth FROM {std}.mondo_closure WHERE descendant_code = '{c}'),
eq AS (SELECT a.d AS via_disease, a.depth, e.object AS rec, e.predicate FROM anc a JOIN {std}.kb_edge e
       ON e.subject = a.d AND e.predicate IN ('skos:exactMatch', 'oboInOwl:hasDbXref', 'cpl:curatedEquivalent')
       WHERE e.object LIKE 'MESH:%'),
rec1 AS (SELECT via_disease, depth, rec AS start_rec, rec FROM eq
         UNION SELECT q.via_disease, q.depth, q.rec, h.object FROM eq q JOIN {std}.kb_edge h
         ON h.subject = q.rec AND h.predicate = 'mesh:headingMappedTo'),
rec2 AS (SELECT r.via_disease, r.depth, r.start_rec, coalesce(m.ancestor_code, r.rec) AS rec
         FROM rec1 r LEFT JOIN {std}.mesh_closure m ON m.descendant_code = r.rec
         UNION SELECT via_disease, depth, start_rec, rec FROM rec1),
excluded AS (SELECT concept_id FROM {std}.class_root WHERE class_id = 'CI-STUDY-DRUG-CLASS' AND kind = 'excluded_ci_target')
SELECT DISTINCT r.via_disease, r.depth, r.start_rec, r.rec AS mesh_record, mc.subject AS mesh_concept,
       ci.subject AS drug, dk.label AS drug_label
FROM rec2 r
JOIN {std}.kb_edge mc ON mc.object = r.rec AND mc.predicate = 'mesh:conceptOf'
JOIN {std}.kb_edge ci ON ci.object = mc.subject AND ci.predicate = 'medrt:CI_with'
JOIN {std}.kb_edge mem ON mem.subject = ci.subject AND mem.predicate = 'medrt:memberOf' AND mem.object = '{GLP1_EPC}'
JOIN {std}.kb_concept dk ON dk.concept_id = ci.subject
WHERE r.rec NOT IN (SELECT concept_id FROM excluded)
ORDER BY drug_label, r.depth""")
        label = query(f"SELECT label FROM {std}.kb_concept WHERE concept_id = '{c}'")
        return {
            "concept_id": c,
            "label": label[0]["label"] if label else None,
            "contraindicated_for_class": bool(rows),
            "drugs": sorted({r["drug_label"] for r in rows}),
            "paths": rows[:20],
            "policy": "any class member contraindicated -> class contraindication (CSL rule)",
        }

    def dataset_mapping(query, concept_id: str = "COSMOS_BC:C81328") -> dict:
        """Biomedical concept -> dataset specialization -> SDTM variables -> allowed CT values -> physical columns."""
        c = _concept(concept_id)
        rows = query(
            f"SELECT s.subject AS specialization, b.subject AS binding, v.object AS variable, "
            f"array_sort(collect_set(u.notation)) AS allowed_values FROM {std}.kb_edge s JOIN {std}.kb_edge h ON "
            f"h.subject = s.subject AND h.predicate = 'cosmos:hasVariableBinding' JOIN {std}.kb_edge b ON b.subject = "
            f"h.object AND b.predicate = 'cosmos:constrains' JOIN {std}.kb_edge v ON v.subject = b.subject AND "
            f"v.predicate = 'cosmos:constrains' LEFT JOIN {std}.kb_edge a ON a.subject = b.subject AND a.predicate = "
            f"'cosmos:allowedValue' LEFT JOIN {std}.kb_concept u ON u.concept_id = a.object WHERE s.predicate = "
            f"'cosmos:specializes' AND s.object = '{c}' GROUP BY ALL ORDER BY variable"
        )
        cols = {
            r["column_name"].upper()
            for r in query(
                f"SELECT column_name FROM {catalog}.information_schema.columns WHERE table_schema = 'clinical_study' "
                f"AND table_name = 'silver_vs'"
            )
        }
        for r in rows:
            var = r["variable"].split(".")[-1]
            r["physical_column"] = f"{cs}.silver_vs.{var}" if var.upper() in cols else None
        return {"concept_id": c, "filter": "VSTESTCD = 'WEIGHT'", "mappings": rows}

    def eligibility_explain(query, usubjid: str) -> dict:
        """Each eligibility criterion's outcome for one participant with evidence records and ontology path."""
        u = _subj(usubjid)
        rows = query(
            f"SELECT protocol_version, eligibility_rule_id, criterion_id, criterion_type, outcome, evidence, "
            f"path_labels, detail FROM {cs}.gold_eligibility_criterion WHERE USUBJID = '{u}' ORDER BY "
            f"criterion_type DESC, criterion_id"
        )
        pop = query(
            f"SELECT rule_eligible, edc_eligible, FASFL, PPSFL, reconciliation, deviations FROM "
            f"{cs}.gold_participant_population WHERE USUBJID = '{u}'"
        )
        return {"usubjid": u, "criteria": rows, "population": pop[0] if pop else None}

    return {
        "endpoint_summary": endpoint_summary,
        "participant_trace": participant_trace,
        "amendment_impact": amendment_impact,
        "rule_definition": rule_definition,
        "rule_status": rule_status,
        "compare_endpoints": compare_endpoints,
        "class_membership": class_membership,
        "contraindication_check": contraindication_check,
        "dataset_mapping": dataset_mapping,
        "eligibility_explain": eligibility_explain,
    }
