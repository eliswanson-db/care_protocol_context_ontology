"""Knowledge stores for the 7 repo-managed Genie spaces (ADR-0027). Single source of truth.

Genie Ontology mines most inferred snippets from Genie-space knowledge stores (measures, filters, expressions, joins,
column settings, example SQL); see docs/benchmark/CONTEXT_CONSISTENCY_AUDIT.md. So this content IS the Genie Ontology
lane's content and follows ADR-0025: every item restates a fact that already exists in code.
  - HEDIS: each snippet restates a metric-view expression (src/semantic/metric_views) or a gold column.
  - Life sciences: rule-version filters come from the approved registry, class membership from class_root/closures,
    the GLP-1 class from the registry, benchmark answers from the hand-authored oracle.
Applied to resources/*.geniespace.json by scripts/genie_knowledge.py (also run by scripts/ls_genie_spaces.py);
validated live with `scripts/genie_knowledge.py --validate`. tests/test_genie_knowledge.py checks parity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
C = "eli_test_classic_catalog"
CP, TERM = f"{C}.care_protocol", f"{C}.care_protocol_terminology"
CS, STD = f"{C}.clinical_study", f"{C}.clinical_study_standards"
MANY_TO_ONE, ONE_TO_MANY, ONE_TO_ONE, MANY_TO_MANY = (f"--rt=FROM_RELATIONSHIP_TYPE_{x}--" for x in
                                                      ("MANY_TO_ONE", "ONE_TO_MANY", "ONE_TO_ONE", "MANY_TO_MANY"))


@dataclass
class Snip:
    kind: str  # measure | filter | expression
    name: str
    sql: str
    alias: str | None = None
    synonyms: list[str] = field(default_factory=list)
    allow_empty: bool = False  # filters that may legitimately match no rows


@dataclass
class Join:
    left: str
    right: str
    on: str
    rt: str


@dataclass
class Bench:
    question: str
    sql: str
    expect: str | None = None  # single scalar (first column of first row), compared as text
    note: str = ""


@dataclass
class Store:
    file: str
    demo: str
    snippets: list[Snip] = field(default_factory=list)
    joins: list[Join] = field(default_factory=list)
    columns: dict[str, dict[str, dict]] = field(default_factory=dict)  # fq table -> column -> config
    benchmarks: list[Bench] = field(default_factory=list)


def M(name, alias, sql, *syn):
    return Snip("measure", name, sql, alias, list(syn))


def F(name, sql, *syn, allow_empty=False):
    return Snip("filter", name, sql, None, list(syn), allow_empty)


def E(name, alias, sql):
    return Snip("expression", name, sql, alias)


def cat(*syn, desc=None, match=True):
    """Column config for a categorical column people name in questions."""
    c = {"enable_format_assistance": True, "enable_entity_matching": match}
    if syn:
        c["synonyms"] = list(syn)
    if desc:
        c["description"] = [desc]
    return c


def note(desc, *syn):
    c = {"description": [desc]}
    if syn:
        c["synonyms"] = list(syn)
    return c


HIDE = {"exclude": True}
CLINIC, PANEL = cat("clinic", "site", "location", "practice"), cat("panel", "pcp panel", "care team", "provider panel")


# =============================================================================================== HEDIS
def gold_benchmarks(tables: set[str]) -> list[Bench]:
    """Gold answer-key queries (src/benchmark/gold_queries.sql) whose tables are all in this space."""
    text = (ROOT / "src/benchmark/gold_queries.sql").read_text()
    out = []
    for block in re.split(r"(?m)^-- @id: ", text)[1:]:
        head, *body = block.split("\n")
        qid = head.strip()
        meta = next((ln for ln in body if ln.startswith("-- class:")), "")
        m = re.search(r"expect:\s*(\S+)", meta)
        sql = "\n".join(ln for ln in body if not ln.startswith("--")).strip().rstrip(";").strip()
        sql = sql.replace("{catalog}", C).replace("{schema}", "care_protocol").replace("{tschema}",
                                                                                      "care_protocol_terminology")
        used = set(re.findall(rf"{C}\.\w+\.\w+", sql))
        desc = " ".join(ln[3:].strip() for ln in body if ln.startswith("-- ") and not ln.startswith("-- class:"))
        if sql and used and used <= tables and m:
            out.append(Bench(desc.split(". ")[0][:240] or qid, sql, m.group(1),
                             f"Gold answer key {qid} (hand-verified, MY2026). Expected value: {m.group(1)}."))
    return out


def _hedis_quality() -> Store:
    g, k, b, s, e, ss = (f"{CP}.gold_adherence_{x}" for x in ("gsd", "ked", "bpd", "spd", "eed", "ssd"))
    bp_ok = "gold_adherence_bpd.systolic < 140 AND gold_adherence_bpd.diastolic < 90"
    ked_ok = "gold_adherence_ked.egfr_datetime IS NOT NULL AND gold_adherence_ked.uacr_datetime IS NOT NULL"
    st = Store("resources/care_protocol.geniespace.json", "healthcare_hedis")
    st.snippets = [
        M("GSD compliance rate (Blood Sugar Controlled: last A1c <= 9%)", "gsd_compliance_rate",
          "COUNT_IF(gold_adherence_gsd.evidence_value <= 9.0) / COUNT(*)", "GSD rate", "blood sugar controlled rate"),
        M("GSD good control rate (last A1c < 8%, of eligible)", "gsd_good_control_rate",
          "COUNT_IF(gold_adherence_gsd.evidence_value < 8.0) / COUNT(*)", "good glycemic control", "controlled diabetes"),
        M("GSD poor control rate (last A1c > 9% or no test, of eligible)", "gsd_poor_control_rate",
          "COUNT_IF(gold_adherence_gsd.evidence_value > 9.0 OR gold_adherence_gsd.evidence_datetime IS NULL) / COUNT(*)",
          "poor glycemic control", "uncontrolled diabetes"),
        M("GSD A1c testing rate (any A1c in the measurement year)", "gsd_testing_rate",
          "COUNT_IF(gold_adherence_gsd.evidence_datetime IS NOT NULL) / COUNT(*)", "A1c testing rate"),
        M("Average latest A1c among tested", "avg_latest_a1c", "AVG(gold_adherence_gsd.evidence_value)", "mean A1c"),
        M("KED compliance rate (patient level)", "ked_compliance_rate", f"COUNT_IF({ked_ok}) / COUNT(*)",
          "kidney health evaluation rate"),
        M("KED uACR test rate", "ked_uacr_rate", "COUNT_IF(gold_adherence_ked.uacr_datetime IS NOT NULL) / COUNT(*)",
          "uACR rate", "albumin creatinine test rate"),
        M("BPD compliance rate (patient level)", "bpd_compliance_rate", f"COUNT_IF({bp_ok}) / COUNT(*)",
          "blood pressure control rate"),
        M("SPD compliance rate (patient level)", "spd_compliance_rate",
          "COUNT_IF(gold_adherence_spd.evidence_datetime IS NOT NULL) / COUNT(*)", "statin therapy rate"),
        M("EED compliance rate (patient level)", "eed_compliance_rate",
          "COUNT_IF(gold_adherence_eed.evidence_datetime IS NOT NULL) / COUNT(*)", "eye exam rate"),
        M("SSD compliance rate (patient level)", "ssd_compliance_rate",
          "COUNT_IF(gold_adherence_ssd.evidence_datetime IS NOT NULL) / COUNT(*)",
          "diabetes screening rate for antipsychotic users"),
        F("GSD care gaps (last A1c > 9% or no A1c test)",
          "gold_adherence_gsd.evidence_value > 9.0 OR gold_adherence_gsd.evidence_datetime IS NULL", "GSD gaps"),
        F("GSD no A1c test in the measurement year", "gold_adherence_gsd.evidence_datetime IS NULL", "no A1c"),
        F("GSD tested, last A1c above 9%", "gold_adherence_gsd.evidence_value > 9.0", "poor control"),
        F("KED care gaps (missing eGFR and/or uACR)", f"NOT ({ked_ok})", "KED gaps"),
        F("KED missing only uACR (eGFR done)",
          "gold_adherence_ked.egfr_datetime IS NOT NULL AND gold_adherence_ked.uacr_datetime IS NULL",
          "uACR gap", "close the uACR gap"),
        F("BPD care gaps (uncontrolled or no reading)", f"NOT coalesce({bp_ok}, false)", "BPD gaps"),
        F("BPD no blood-pressure reading", "gold_adherence_bpd.bp_datetime IS NULL", "no BP reading"),
        F("SPD care gaps (no statin dispensed)", "gold_adherence_spd.evidence_datetime IS NULL", "statin gap"),
        F("EED care gaps (no diabetic eye exam)", "gold_adherence_eed.evidence_datetime IS NULL", "eye exam gap"),
        F("SSD care gaps (no glucose or HbA1c screen)", "gold_adherence_ssd.evidence_datetime IS NULL", "SSD gap"),
        F("Latest measurement year (GSD)",
          f"gold_adherence_gsd.measurement_year = (SELECT MAX(measurement_year) FROM {g})", "current year", "this year"),
        E("GSD glycemic control band", "gsd_control_band",
          "CASE WHEN gold_adherence_gsd.evidence_datetime IS NULL THEN 'Not tested' WHEN gold_adherence_gsd.evidence_value "
          "< 8.0 THEN 'Good (<8%)' WHEN gold_adherence_gsd.evidence_value > 9.0 THEN 'Poor (>9%)' ELSE 'Moderate (8-9%)' END"),
        E("KED gap reason (matches the KED metric view)", "ked_gap_reason",
          f"CASE WHEN {ked_ok} THEN 'Met' WHEN gold_adherence_ked.egfr_datetime IS NULL AND "
          "gold_adherence_ked.uacr_datetime IS NULL THEN 'No eGFR or uACR test' WHEN gold_adherence_ked.uacr_datetime IS "
          "NULL THEN 'Missing uACR' ELSE 'Missing eGFR' END"),
        E("BPD gap reason (matches the BPD metric view)", "bpd_gap_reason",
          f"CASE WHEN {bp_ok} THEN 'Met' WHEN gold_adherence_bpd.bp_datetime IS NULL THEN 'No BP reading in measurement "
          "year' ELSE 'BP not controlled (>=140/90)' END"),
        E("Statin ingredient", "statin_ingredient", "INITCAP(SPLIT(gold_adherence_spd.evidence_drug, ' ')[0])"),
    ]
    for t in ("ked", "bpd", "spd", "eed"):
        st.joins.append(Join(f"{CP}.gold_adherence_{t}", g,
                             f"gold_adherence_{t}.patient_id = gold_adherence_gsd.patient_id AND "
                             f"gold_adherence_{t}.measurement_year = gold_adherence_gsd.measurement_year", MANY_TO_ONE))
    for t in (g, k, b, s, e, ss):
        st.columns[t] = {"clinic_id": CLINIC, "panel_id": PANEL, "eligible_flag": HIDE}
    st.columns[g]["evidence_value"] = note("Latest measurement-year HbA1c result in percent (7.4 = 7.4%); NULL when "
                                           "no A1c test.", "A1c", "HbA1c", "latest A1c")
    st.columns[g]["evidence_code"] = cat("A1c LOINC code")
    st.columns[k]["egfr_code"] = cat("eGFR LOINC code")
    st.columns[k]["uacr_code"] = cat("uACR LOINC code")
    st.columns[s]["evidence_drug"] = cat("statin", "statin drug", "medication")
    st.columns[e]["evidence_exam"] = cat("eye exam type", "retinal exam")
    st.columns[ss]["antipsychotic_desc"] = cat("antipsychotic", "antipsychotic drug")
    st.columns[ss]["smi_dx_code"] = cat("SMI diagnosis", "schizophrenia or bipolar code")
    st.benchmarks = gold_benchmarks({g, k, b, s, e, ss})
    return st


def _hedis_protocol() -> Store:
    pa, mad = f"{CP}.gold_protocol_adherence", f"{CP}.gold_adherence_mad"
    st = Store("resources/protocol_adherence.geniespace.json", "healthcare_hedis")
    st.snippets = [
        M("Protocol Step 3 adherence rate (closed obligations)", "step3_adherence_rate",
          "COUNT_IF(gold_protocol_adherence.window_closed AND gold_protocol_adherence.followup_within_90d) / "
          "COUNT_IF(gold_protocol_adherence.window_closed)", "step 3 rate", "recheck rate", "follow-up rate"),
        M("Step 3 closed obligations (denominator)", "step3_trigger_events",
          "COUNT_IF(gold_protocol_adherence.window_closed)", "trigger events", "high A1c obligations"),
        M("Step 3 open obligations", "step3_open",
          "COUNT_IF(NOT gold_protocol_adherence.followup_within_90d AND NOT gold_protocol_adherence.window_closed)",
          "open windows", "still closable"),
        M("Average days to follow-up", "avg_days_to_followup", "AVG(gold_protocol_adherence.followup_days)"),
        M("MAD adherence rate (PDC >= 80%)", "mad_adherence_rate", "COUNT_IF(gold_adherence_mad.pdc >= 0.8) / COUNT(*)",
          "medication adherence rate", "PDC rate"),
        M("Average PDC", "avg_pdc", "AVG(gold_adherence_mad.pdc)", "proportion of days covered"),
        F("Step 3 missed (window closed, no recheck in 90 days)",
          "gold_protocol_adherence.window_closed AND NOT gold_protocol_adherence.followup_within_90d",
          "missed recheck", "not followed up"),
        F("Step 3 open obligations (window not closed yet)",
          "NOT gold_protocol_adherence.window_closed AND NOT gold_protocol_adherence.followup_within_90d", allow_empty=True),
        F("Step 3 closed obligations only", "gold_protocol_adherence.window_closed", "closed windows"),
        F("MAD non-adherent (PDC < 80%)", "gold_adherence_mad.pdc < 0.8", "refill gap", "adherence gap"),
        F("Panels with a PCP handoff", "panel_roster.is_handoff", "PCP turnover", "handoff panels"),
        E("Step 3 status (matches the protocol adherence metric view)", "step3_status",
          "CASE WHEN gold_protocol_adherence.followup_within_90d THEN 'MET' WHEN gold_protocol_adherence.window_closed "
          "THEN 'NOT_MET' ELSE 'OPEN' END"),
        E("Trigger month", "trigger_month", "DATE_TRUNC('MONTH', gold_protocol_adherence.trigger_ts)"),
    ]
    st.joins = [
        Join(pa, f"{CP}.panel_roster", "gold_protocol_adherence.patient_id = panel_roster.patient_id", MANY_TO_ONE),
        Join(mad, f"{CP}.panel_roster", "gold_adherence_mad.patient_id = panel_roster.patient_id", MANY_TO_ONE),
        Join(f"{CP}.panel_pcp_transition", f"{CP}.protocol_watch_findings",
             "panel_pcp_transition.clinic_id = protocol_watch_findings.clinic_id", ONE_TO_MANY),
    ]
    st.columns = {pa: {"clinic_id": CLINIC, "panel_id": PANEL, "followup_type": cat("follow-up type", "recheck type")},
                  mad: {"clinic_id": CLINIC, "panel_id": PANEL, "eligible_flag": HIDE},
                  f"{CP}.panel_roster": {"clinic_id": CLINIC, "panel_id": PANEL},
                  f"{CP}.protocol_watch_findings": {"clinic_id": CLINIC, "severity": cat("severity", "alert level"),
                                                    "finding_type": cat("finding type")},
                  f"{CP}.panel_pcp_transition": {"clinic_id": CLINIC, "change_type": cat("change type", "PCP change")}}
    st.benchmarks = gold_benchmarks({pa, mad, f"{CP}.panel_roster", f"{CP}.panel_pcp_transition",
                                     f"{CP}.protocol_watch_findings"})
    return st


def _hedis_labs() -> Store:
    lr, lp = f"{CP}.gold_lab_result", f"{TERM}.loinc_parts"

    def comp(part):
        return (f"gold_lab_result.loinc_code IN (SELECT loinc_code FROM {lp} WHERE predicate = 'has_component' "
                f"AND part = '{part}')")
    st = Store("resources/lab_measures.geniespace.json", "healthcare_hedis")
    st.snippets = [
        M("Lab observations", "observations", "COUNT(gold_lab_result.result_ts)", "results", "lab results"),
        M("Patients tested", "patients_tested", "COUNT(DISTINCT gold_lab_result.patient_id)"),
        M("Average result", "avg_result", "AVG(gold_lab_result.value_num)", "mean value"),
        F("HbA1c results (any LOINC code with component LP-HBA1C)", comp("LP-HBA1C"), "A1c results", "all A1c"),
        F("eGFR results (component LP-EGFR)", comp("LP-EGFR"), "eGFR results", allow_empty=True),
        F("uACR results (component LP-UACR)", comp("LP-UACR"), "uACR results", allow_empty=True),
        F("Latest measurement year (labs)",
          f"gold_lab_result.measurement_year = (SELECT MAX(measurement_year) FROM {lr})", "current year"),
        E("Lab concept (matches the lab metric view)", "lab_concept",
          "COALESCE(gold_lab_result.component, 'Uncoded (no LOINC Part)')"),
    ]
    st.joins = [Join(lr, lp, "gold_lab_result.loinc_code = loinc_parts.loinc_code", MANY_TO_MANY)]
    st.columns = {lr: {"component": cat("lab concept", "analyte"), "loinc_code": cat("LOINC", "test code"),
                       "description": cat("lab test", "test name"), "specimen_system": cat("specimen", "system"),
                       "method": cat("method"), "units": cat("units", match=False)},
                  lp: {"predicate": cat("LOINC axis"), "part": cat("LOINC part"), "part_name": cat("part name")}}
    st.benchmarks = gold_benchmarks({lr, lp})
    return st


def _hedis_terms() -> Store:
    t = {x: f"{TERM}.{x}" for x in ("icd10_closure", "icd10_hier", "loinc", "loinc_parts", "protocol_edges",
                                    "rxnorm_closure", "rxnorm_hier", "rxnorm_statin", "value_set_segment")}
    st = Store("resources/terminology.geniespace.json", "healthcare_hedis")
    st.snippets = [
        M("Distinct descendant codes", "descendant_codes", "COUNT(DISTINCT icd10_closure.descendant_code)"),
        F("Proper descendants only (exclude the code itself)", "icd10_closure.depth > 0", "subtypes", "children"),
        F("Drug class membership edges", "rxnorm_hier.relationship = 'class_member'", "drug class members"),
        F("Ingredient-to-clinical-drug edges", "rxnorm_hier.relationship = 'ingredient_of'", "products"),
        F("Protocol recommendations", "protocol_edges.predicate IN ('recommendedFor', 'firstLineFor')",
          "recommended for", "first-line"),
        F("Protocol contraindications", "protocol_edges.predicate IN ('contraindicatedWith', 'contraindicatedWhen')",
          "contraindicated"),
        F("Protocol thresholds", "protocol_edges.predicate IN ('hasThreshold', 'definedBy')", "threshold", "cutoff"),
        F("MY2026 value-set version", "value_set_segment.measurement_year = 2026", "2026 value set"),
        F("MY2025 value-set version", "value_set_segment.measurement_year = 2025", "2025 value set"),
    ]
    st.joins = [
        Join(t["icd10_closure"], t["icd10_hier"], "icd10_closure.descendant_code = icd10_hier.code", MANY_TO_MANY),
        Join(t["value_set_segment"], t["icd10_hier"], "value_set_segment.code = icd10_hier.code", MANY_TO_MANY),
        Join(t["rxnorm_closure"], t["rxnorm_hier"], "rxnorm_closure.descendant_code = rxnorm_hier.code", MANY_TO_MANY),
        Join(t["loinc_parts"], t["loinc"], "loinc_parts.loinc_code = loinc.loinc_code", MANY_TO_ONE),
        Join(t["protocol_edges"], t["value_set_segment"], "protocol_edges.object = value_set_segment.segment_id",
             MANY_TO_MANY),
    ]
    st.columns = {t["protocol_edges"]: {"predicate": cat("relationship", "edge type"), "subject": cat("drug class"),
                                         "object": cat("target")},
                  t["value_set_segment"]: {"segment_id": cat("value set", "segment", "cohort"),
                                           "code_system": cat("code system")},
                  t["rxnorm_hier"]: {"relationship": cat("relationship")},
                  t["icd10_hier"]: {"name": cat("diagnosis name", "condition")},
                  t["loinc_parts"]: {"part": cat("LOINC part"), "predicate": cat("LOINC axis")}}
    st.benchmarks = gold_benchmarks(set(t.values()))
    return st


# =============================================================================================== Life sciences
def _registry() -> dict:
    return yaml.safe_load((ROOT / "src/clinical_study/rules/registry.yaml").read_text())


def _oracle() -> dict:
    return yaml.safe_load((ROOT / "tests/fixtures/life_sciences/expected_endpoints.yaml").read_text())["expected"]


def _ls_analytics() -> Store:
    reg, orc = _registry(), _oracle()
    r, p, a, c = (f"{CS}.gold_endpoint_result", f"{CS}.gold_participant_population", f"{CS}.gold_amendment_impact",
                  f"{CS}.gold_endpoint_candidate")
    st = Store("resources/ls_study_analytics.geniespace.json", "life_sciences_clinical")
    st.snippets = [
        M("Participants with a derived Week 24 result", "n_derived",
          "COUNT_IF(gold_endpoint_result.result_status = 'DERIVED')", "evaluable participants", "derived"),
        M("Mean percent change in body weight (derived only)", "mean_pchg", "AVG(gold_endpoint_result.PCHG)",
          "mean weight change", "average % change"),
        M("Endpoint missingness rate", "missingness",
          "1 - COUNT_IF(gold_endpoint_result.result_status = 'DERIVED') / COUNT(*)", "missing rate", "not evaluable"),
        M("Excluded observations", "n_excluded", "COUNT_IF(gold_endpoint_candidate.decision = 'EXCLUDED')"),
        M("Participants who became derivable (R1 -> R2)", "n_recovered",
          "COUNT_IF(gold_amendment_impact.endpoint_became_derivable)", "recovered by amendment 1"),
        M("Enrolled in error", "n_enrolled_in_error",
          "COUNT_IF(gold_participant_population.reconciliation = 'ENROLLED_BUT_RULE_INELIGIBLE')",
          "eligibility violations"),
        M("FAS participants", "n_fas", "COUNT_IF(gold_participant_population.FASFL = 'Y')", "full analysis set"),
        M("PPS participants", "n_pps", "COUNT_IF(gold_participant_population.PPSFL = 'Y')", "per protocol set"),
        F("Derived results only", "gold_endpoint_result.result_status = 'DERIVED'", "evaluable"),
        F("Full analysis set (endpoint rows)", "gold_endpoint_result.analysis_population_status = 'IN_FAS'", "FAS"),
        F("Named fixture participants", "gold_endpoint_result.USUBJID LIKE '%-FX-%'", "edge cases", "tracers"),
        F("Excluded observations", "gold_endpoint_candidate.decision = 'EXCLUDED'", "excluded"),
        F("Follow-up candidates", "gold_endpoint_candidate.role = 'FOLLOWUP'", "week 24 candidates"),
        F("Amendment 1 changed the selected record",
          "gold_amendment_impact.selected_followup_changed", "changed selection"),
        F("Enrolled in error", "gold_participant_population.reconciliation = 'ENROLLED_BUT_RULE_INELIGIBLE'"),
        E("Weight change in kg", "weight_change_kg", "gold_endpoint_result.AVAL_FU - gold_endpoint_result.BASE"),
        E("Exclusion reason category", "exclusion_category", "SPLIT(gold_endpoint_result.exclusion_reason, ':')[0]"),
        E("Absolute days from Week 24 target", "abs_days_from_target", "ABS(gold_endpoint_candidate.days_from_target)"),
    ]
    for ep_id, ep in reg["endpoints"].items():  # one filter per approved rule version, words from the registry
        for rv, rule in ep["rule_versions"].items():
            if rule.get("review_state") != "approved":
                continue
            hw = rule["followup"]["window_half_width_days"]
            st.snippets.append(F(f"{ep_id}.{rv}: {ep['study']} protocol {rule['protocol_version']} / SAP "
                                 f"{rule['sap_version']} (±{hw}-day Week 24 window)",
                                 f"gold_endpoint_result.endpoint_version = '{ep_id}.{rv}'",
                                 f"{ep['study']} {rv}", f"±{hw} day window", f"protocol {rule['protocol_version']}"))
    for sid in reg["studies"]:
        st.snippets.append(F(f"Study {sid}", f"gold_participant_population.STUDYID = '{sid}'", sid))
    st.joins = [
        Join(r, p, "gold_endpoint_result.USUBJID = gold_participant_population.USUBJID", MANY_TO_ONE),
        Join(c, r, "gold_endpoint_candidate.USUBJID = gold_endpoint_result.USUBJID AND gold_endpoint_candidate."
                   "endpoint_id = gold_endpoint_result.endpoint_id AND gold_endpoint_candidate.rule_version = "
                   "gold_endpoint_result.rule_version", MANY_TO_ONE),
        Join(a, p, "gold_amendment_impact.USUBJID = gold_participant_population.USUBJID", ONE_TO_ONE),
        Join(r, f"{STD}.rule_version", "gold_endpoint_result.endpoint_version = rule_version.endpoint_version",
             MANY_TO_ONE),
    ]
    st.columns = {
        r: {"STUDYID": cat("study"), "endpoint_version": cat("rule version", "endpoint version", "derivation version"),
            "result_status": cat("status", "result status"), "PCHG": note("Percent change in body weight from "
            "baseline, unrounded; negative = weight loss.", "percent change", "% change in body weight", "weight change"),
            "BASE": note("Baseline body weight (kg).", "baseline weight"),
            "AVAL_FU": note("Week 24 follow-up body weight (kg).", "week 24 weight", "follow-up weight"),
            "exclusion_reason": cat("why not derived", match=False)},
        p: {"STUDYID": cat("study"), "ARMCD": cat("arm", "treatment arm"), "SITEID": cat("site", "center"),
            "COUNTRY": cat("country"), "reconciliation": cat("eligibility reconciliation"),
            "FASFL": cat("FAS flag"), "PPSFL": cat("PPS flag")},
        c: {"decision": cat("decision"), "reason": cat("reason", "why excluded"), "role": cat("role"),
            "visit": cat("visit")},
        a: {"STUDYID": cat("study")},
    }
    st.benchmarks = [
        Bench("What is CSL-A-FX-05's Week 24 percent change under EP-A-WT24.R2?",
              f"SELECT ROUND(PCHG, 6) FROM {r} WHERE USUBJID = 'CSL-A-FX-05' AND endpoint_version = 'EP-A-WT24.R2'",
              str(round(orc["CSL-A-FX-05"]["R2"]["value"], 6)), "Oracle fixture (hand-authored)."),
        Bench("Why does CSL-A-FX-05 have no Week 24 result under EP-A-WT24.R1?",
              f"SELECT exclusion_reason FROM {r} WHERE USUBJID = 'CSL-A-FX-05' AND endpoint_version = 'EP-A-WT24.R1'",
              orc["CSL-A-FX-05"]["R1"]["exclusion_reason"], "Oracle fixture (hand-authored)."),
        Bench("What is CSL-B-FX-18's Week 24 percent change under EP-B-WT24.R1?",
              f"SELECT ROUND(PCHG, 6) FROM {r} WHERE USUBJID = 'CSL-B-FX-18' AND endpoint_version = 'EP-B-WT24.R1'",
              str(round(orc["CSL-B-FX-18"]["R1"]["value"], 6)), "Oracle fixture (hand-authored)."),
        Bench("How many CSL-A participants became derivable under Amendment 1 (R1 -> R2)?",
              f"SELECT COUNT_IF(endpoint_became_derivable) FROM {a}", None,
              "Computed from gold; compare with the Amendment Lab."),
    ]
    return st


def _ls_protocol() -> Store:
    reg = _registry()
    d, s, ra, rv, rs = (f"{CS}.doc_document", f"{CS}.doc_section", f"{CS}.rule_assertion", f"{STD}.rule_version",
                        f"{STD}.rule_document_support")
    st = Store("resources/ls_protocol_evidence.geniespace.json", "life_sciences_clinical")
    st.snippets = [
        M("Rule assertions", "n_assertions", "COUNT(rule_assertion.assertion_id)", "assertions"),
        F("Approved executable rule versions", "rule_version.review_state = 'approved'", "approved rules", "executable"),
        F("Assertions that are not approved", "rule_assertion.review_state <> 'approved'", "unapproved"),
        F("Candidate assertions (never executed)", "rule_assertion.review_state = 'candidate'", "candidate", "draft rule",
          "proposed"),
        F("Superseded assertions", "rule_assertion.review_state = 'superseded'", "superseded", "replaced"),
        F("Draft documents", "doc_document.status = 'DRAFT'", "draft", "not approved document"),
        F("Week 24 window statements", "rule_assertion.assertion_type = 'FOLLOWUP_WINDOW_HALF_WIDTH'",
          "analysis window", "visit window"),
        E("Citation", "citation", "CONCAT(doc_section.document_id, ' §', doc_section.section_number)"),
    ]
    for sid in reg["studies"]:
        st.snippets.append(F(f"Study {sid} documents", f"doc_document.study_id = '{sid}'", sid))
    st.joins = [
        Join(s, d, "doc_section.document_id = doc_document.document_id", MANY_TO_ONE),
        Join(ra, d, "rule_assertion.document_id = doc_document.document_id", MANY_TO_ONE),
        Join(ra, s, "rule_assertion.section_id = doc_section.section_id", MANY_TO_ONE),
        Join(rs, rv, "rule_document_support.rule_id = rule_version.endpoint_version", MANY_TO_ONE),
        Join(rs, s, "rule_document_support.document_id = doc_section.document_id AND rule_document_support.section = "
                    "doc_section.section_number", MANY_TO_ONE),
        Join(f"{STD}.study_version", f"{STD}.study", "study_version.study_id = study.study_id", MANY_TO_ONE),
    ]
    st.columns = {
        ra: {"review_state": cat("review state", "approval status"), "assertion_type": cat("rule parameter"),
             "document_id": cat("document")},
        d: {"document_id": cat("document"), "status": cat("document status"), "doc_type": cat("document type"),
            "study_id": cat("study")},
        rv: {"endpoint_version": cat("rule version"), "review_state": cat("review state"), "study_id": cat("study")},
        f"{STD}.study_version": {"protocol_version": cat("protocol version"), "study_id": cat("study")},
        f"{STD}.eligibility_criterion": {"criterion_id": cat("criterion"), "eligibility_rule_id": cat("eligibility rule"),
                                         "criterion_type": cat("inclusion or exclusion")},
    }
    st.benchmarks = [
        Bench("What is the review state of the proposed ±21-day Week 24 window?",
              f"SELECT review_state FROM {ra} WHERE assertion_type = 'FOLLOWUP_WINDOW_HALF_WIDTH' AND value = '21'",
              "candidate", "Draft Amendment 3 memo; never executed."),
        Bench("What Week 24 window half-width does EP-A-WT24.R2 use?",
              f"SELECT window_half_width_days FROM {rv} WHERE endpoint_version = 'EP-A-WT24.R2'",
              str(reg["endpoints"]["EP-A-WT24"]["rule_versions"]["R2"]["followup"]["window_half_width_days"]),
              "From the approved registry; stated in CSL-A-SAP-v2.0 §9.4.1."),
        Bench("Which document section supports EP-A-WT24.R2?",
              f"SELECT CONCAT(document_id, ' §', section) FROM {rs} WHERE rule_id = 'EP-A-WT24.R2'",
              "{document} §{section}".format(**reg["endpoints"]["EP-A-WT24"]["rule_versions"]["R2"]["source_section"])),
    ]
    return st


def _ls_standards() -> Store:
    reg = _registry()
    glp = reg["concept_classes"]["CI-STUDY-DRUG-CLASS"]["drug_class"]
    k, e, mc, cr, gc, vs = (f"{STD}.kb_concept", f"{STD}.kb_edge", f"{STD}.mondo_closure", f"{STD}.class_root",
                            f"{CS}.gold_eligibility_criterion", f"{CS}.silver_vs")
    st = Store("resources/ls_standards_semantics.geniespace.json", "life_sciences_clinical")

    def member(cls):  # membership derived from class_root (exclusion wins), never a hand-typed code list
        return (f"mondo_closure.ancestor_code IN (SELECT concept_id FROM {cr} WHERE class_id = '{cls}' AND kind = 'root') "
                f"AND mondo_closure.descendant_code NOT IN (SELECT x.descendant_code FROM {mc} x JOIN {cr} r ON "
                f"x.ancestor_code = r.concept_id WHERE r.class_id = '{cls}' AND r.kind = 'exclude_root')")
    st.snippets = [
        M("Distinct concepts reached", "n_descendants", "COUNT(DISTINCT mondo_closure.descendant_code)"),
        M("Direct facts", "n_edges", "COUNT(kb_edge.edge_id)", "edges", "relationships"),
        F("WRC-V1 weight-related comorbidity members (closure; carve-outs applied)", member("WRC-V1"),
          "weight-related comorbidity", "comorbidity class"),
        F("EXCL-MH-V1 exclusionary history members (closure)",
          f"mondo_closure.ancestor_code IN (SELECT concept_id FROM {cr} WHERE class_id = 'EXCL-MH-V1' AND kind = 'root')",
          "exclusionary conditions"),
        F("Official facts only (no demo extension)", "kb_edge.predicate NOT LIKE 'cpl:%'", "official"),
        F("Demo-extension facts (cpl:)", "kb_edge.predicate LIKE 'cpl:%'", "demo extension", "custom"),
        F("Direct is-a edges", "kb_edge.predicate = 'rdfs:subClassOf'", "is a", "parent"),
        F("MED-RT contraindications", "kb_edge.predicate = 'medrt:CI_with'", "contraindicated with"),
        F("GLP-1 receptor agonist class members (MED-RT)",
          f"kb_edge.predicate = 'medrt:memberOf' AND kb_edge.object = '{glp}'", "GLP-1 RA", "GLP-1 drugs"),
        F("Body weight observations", "silver_vs.VSTESTCD = 'WEIGHT'", "weight records"),
        F("Unmapped or missing units", "silver_vs.CPL_UNIT_MAPPING_STATUS <> 'MAPPED'", "unsupported units"),
        F("Criteria that excluded or failed", "gold_eligibility_criterion.outcome IN ('TRIGGERED', 'NOT_MET')",
          "why ineligible"),
        E("Ontology path (readable)", "path_text", "ARRAY_JOIN(gold_eligibility_criterion.path_labels, ' → ')"),
    ]
    st.joins = [
        Join(e, k, "kb_edge.subject = kb_concept.concept_id", MANY_TO_ONE),
        Join(mc, k, "mondo_closure.descendant_code = kb_concept.concept_id", MANY_TO_ONE),
        Join(cr, k, "class_root.concept_id = kb_concept.concept_id", MANY_TO_ONE),
        Join(cr, f"{STD}.concept_class", "class_root.class_id = concept_class.class_id", MANY_TO_ONE),
    ]
    st.columns = {
        k: {"label": cat("name", "concept name", "term"), "scheme": cat("vocabulary", "code system"),
            "concept_type": cat("concept type")},
        e: {"predicate": cat("relationship", "edge type"), "source_artifact": cat("source")},
        cr: {"class_id": cat("concept class"), "kind": cat("root kind")},
        gc: {"criterion_id": cat("criterion"), "outcome": cat("outcome")},
        vs: {"VSTESTCD": cat("test code"), "VSORRESU": cat("unit"), "CPL_UNIT_MAPPING_STATUS": cat("unit mapping")},
    }
    st.benchmarks = [
        Bench("Is familial hypercholesterolemia (MONDO:0005439) a WRC-V1 weight-related comorbidity?",
              f"SELECT CASE WHEN COUNT(*) > 0 THEN 'yes' ELSE 'no' END FROM {mc} WHERE descendant_code = 'MONDO:0005439' "
              f"AND {member('WRC-V1')}", "yes", "Expected from expected_eligibility.yaml (FX-21)."),
        Bench("Is obstructive sleep apnea (MONDO:0007147) a WRC-V1 member?",
              f"SELECT CASE WHEN COUNT(*) > 0 THEN 'yes' ELSE 'no' END FROM {mc} WHERE descendant_code = 'MONDO:0007147' "
              f"AND {member('WRC-V1')}", "no", "Added only by Amendment 2 (WRC-V2)."),
        Bench("Which criterion excluded CSL-A-FX-25?",
              f"SELECT criterion_id FROM {gc} WHERE USUBJID = 'CSL-A-FX-25' AND outcome = 'TRIGGERED'", "EXC-CI",
              "Diabetic ketoacidosis: MED-RT CI_with on a GLP-1 RA (expected_eligibility.yaml)."),
    ]
    return st


def stores() -> dict[str, Store]:
    return {"care_protocol": _hedis_quality(), "protocol_adherence": _hedis_protocol(),
            "lab_measures": _hedis_labs(), "terminology": _hedis_terms(),
            "ls_study_analytics": _ls_analytics(), "ls_protocol_evidence": _ls_protocol(),
            "ls_standards_semantics": _ls_standards()}
