"""Generate the three Clinical Study Genie space bodies (resources/ls_*.geniespace.json). SYNTHETIC demo.

    .venv/bin/python -I scripts/ls_genie_spaces.py            # write the JSON files
    .venv/bin/python -I scripts/ls_genie_spaces.py --check    # print every example SQL (validate live first)

The space identifiers are the fixed ECT catalog, as for HEDIS (genie_spaces file_path is not variable-substituted).
Each space is scoped to one role (prompt §13) instead of one giant instruction bundle mixing domains.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
C = "eli_test_classic_catalog"
CS, STD, SEM = f"{C}.clinical_study", f"{C}.clinical_study_standards", f"{C}.clinical_study_semantic"

COMMON = [
    "SYNTHETIC educational demo (Clinical Study Context & Evidence Lab). CSL-101 is a fictional GLP-1 receptor "
    "agonist; studies CSL-A and CSL-B are not real. Data are SDTM-/ADaM-shaped, not submission-ready. Results are "
    "descriptive: never state or imply efficacy, superiority or a causal effect.",
    "This space covers ONLY the Clinical Study lab. It has no HEDIS, health-plan, NCQA or care-gap data; if asked "
    "about those, say they are out of scope for this space.",
]

SPACES = {
    "ls_study_analytics": {
        "tables": [
            f"{CS}.gold_endpoint_result",
            f"{CS}.gold_participant_population",
            f"{CS}.gold_amendment_impact",
            f"{CS}.gold_endpoint_candidate",
            f"{CS}.gold_study_summary",
            f"{STD}.rule_version",
        ],
        "metric_views": [
            f"{SEM}.endpoint_result_metrics",
            f"{SEM}.endpoint_candidate_metrics",
            f"{SEM}.amendment_impact_metrics",
            f"{SEM}.participant_population_metrics",
        ],
        "text": COMMON
        + [
            "Approved endpoint results only. Every number must state its study AND endpoint rule version: "
            "EP-A-WT24.R1 (CSL-A, ±7-day Week 24 window, protocol/SAP 1.0), EP-A-WT24.R2 (CSL-A, ±14 days, Amendment "
            "1, protocol/SAP 2.0), EP-B-WT24.R1 (CSL-B, mean baseline, ±10 days). If the user does not say which "
            "version, ask, or show each version separately. Never pool studies or rule versions.",
            "Use the metric views with MEASURE(`<name>`). Every endpoint measure returns NULL unless exactly one "
            "`Rule Version` is in scope: filter WHERE `Rule Version` = '...' or GROUP BY `Rule Version`. A NULL means "
            "the question pooled versions, not that the value is zero.",
            "The endpoint population is the FAS (`In FAS` = 'Y'). Percent change: negative = weight loss. PCHG is "
            "unrounded; round only for display.",
            "Amendment impact: amendment_impact_metrics compares CSL-A R1 with R2 per participant. With closest-to-"
            "target selection a wider window can only add a record, never replace one that already qualified.",
            "To explain one participant, read gold_endpoint_candidate for that USUBJID and rule_version: every "
            "observation has a decision and reason.",
            "Do not recompute endpoint values from silver data; they come from the deterministic engine (gold).",
        ],
        "examples": [
            (
                "What is the Week 24 endpoint summary for CSL-A under rule version 1?",
                f"SELECT `Arm`, MEASURE(`Participants In FAS`) AS fas, MEASURE(`Participants With Derived Endpoint`) AS "
                f"derived, ROUND(MEASURE(`Endpoint Missingness Rate`), 3) AS missingness, ROUND(MEASURE(`Mean Percent "
                f"Change`), 2) AS mean_pct_change FROM {SEM}.endpoint_result_metrics WHERE `Rule Version` = "
                f"'EP-A-WT24.R1' GROUP BY ALL ORDER BY `Arm`",
            ),
            (
                "How did Amendment 1 change the CSL-A Week 24 results?",
                f"SELECT MEASURE(`Participants Compared`) AS compared, MEASURE(`Participants Became Derivable`) AS "
                f"became_derivable, MEASURE(`Participants With Changed Selected Observation`) AS changed_selection, "
                f"MEASURE(`Participants With Changed Endpoint Value`) AS changed_value, MEASURE(`Participants With "
                f"Changed Eligible Candidates`) AS more_candidates FROM {SEM}.amendment_impact_metrics",
            ),
            (
                "Which sites had the most participants recovered by Amendment 1?",
                f"SELECT `Site`, MEASURE(`Participants Became Derivable`) AS recovered FROM {SEM}.amendment_impact_metrics "
                f"GROUP BY ALL ORDER BY recovered DESC LIMIT 5",
            ),
            (
                "Why were Week 24 observations excluded in CSL-A under R1?",
                f"SELECT `Reason`, MEASURE(`Excluded Observations`) AS excluded FROM {SEM}.endpoint_candidate_metrics "
                f"WHERE `Rule Version` = 'EP-A-WT24.R1' AND `Role` = 'FOLLOWUP' GROUP BY ALL ORDER BY excluded DESC",
            ),
            (
                "Which participants have no valid baseline in CSL-B?",
                f"SELECT USUBJID, exclusion_reason FROM {CS}.gold_endpoint_result WHERE endpoint_version = 'EP-B-WT24.R1' "
                f"AND result_status = 'NO_VALID_BASELINE' ORDER BY USUBJID",
            ),
            (
                "How many participants were enrolled in error in each study?",
                f"SELECT `Study`, MEASURE(`Enrolled In Error`) AS enrolled_in_error, MEASURE(`Randomized Participants`) "
                f"AS randomized FROM {SEM}.participant_population_metrics GROUP BY ALL ORDER BY `Study`",
            ),
            (
                "Why was CSL-A-FX-05's Week 24 result different under R1 and R2?",
                f"SELECT rule_version, obs_id, visit, vsdtc, days_from_target, decision, reason FROM "
                f"{CS}.gold_endpoint_candidate WHERE USUBJID = 'CSL-A-FX-05' AND role = 'FOLLOWUP' ORDER BY rule_version, vsseq",
            ),
        ],
    },
    "ls_protocol_evidence": {
        "tables": [
            f"{CS}.doc_document",
            f"{CS}.doc_section",
            f"{CS}.rule_assertion",
            f"{STD}.rule_version",
            f"{STD}.rule_document_support",
            f"{STD}.study",
            f"{STD}.study_version",
            f"{STD}.eligibility_criterion",
            f"{STD}.analysis_population",
        ],
        "metric_views": [],
        "text": COMMON
        + [
            "Answer from the protocols, amendments and SAPs (doc_document, doc_section) and cite the document id, "
            "version and section number for every rule you state (e.g. CSL-A-SAP-v2.0 §9.4.1).",
            "Executable rules live in rule_version (endpoint rules) and eligibility_criterion; only review_state = "
            "'approved' rules are executed. rule_assertion lists rule statements extracted from documents with "
            "review_state approved / superseded / rejected / candidate. A candidate (e.g. the DRAFT Amendment 3 memo "
            "proposing ±21 days) is NOT approved and changes no result. Say so explicitly when asked about it.",
            "Protocol scheduling windows (visit booking) are not endpoint analysis windows; those assertions are "
            "rejected as rules.",
            "Amendments: protocol 2.0 (Amendment 1, effective 2025-09-01) widened the Week 24 analysis window to ±14 "
            "days; protocol 3.0 (Amendment 2, 2025-11-01) added obstructive sleep apnea to the weight-related "
            "comorbidity class for screening on/after that date.",
            "All approvals are seeded demo fixtures (approved_by = demo-fixture), not real human review.",
        ],
        "examples": [
            (
                "Has the wider ±21-day window been approved?",
                f"SELECT a.document_id, d.status, a.section_number, a.value AS window_days, a.review_state, "
                f"a.evidence_text FROM {CS}.rule_assertion a JOIN {CS}.doc_document d USING (document_id) WHERE "
                f"a.assertion_type = 'FOLLOWUP_WINDOW_HALF_WIDTH' ORDER BY a.value, a.document_id",
            ),
            (
                "What does the CSL-A SAP say about the Week 24 analysis window, by version?",
                f"SELECT document_id, section_number, heading, text FROM {CS}.doc_section WHERE document_id IN "
                f"('CSL-A-SAP-v1.0', 'CSL-A-SAP-v2.0') AND section_number = '9.4.1'",
            ),
            (
                "What changed in each CSL-A protocol version?",
                f"SELECT protocol_version, sap_version, effective_date, amendment, change_summary, documents FROM "
                f"{STD}.study_version WHERE study_id = 'CSL-A' ORDER BY effective_date",
            ),
            (
                "Which document section supports each executable endpoint rule?",
                f"SELECT v.endpoint_version, v.review_state, s.document_id, s.section, d.heading FROM {STD}.rule_version v "
                f"JOIN {STD}.rule_document_support s ON s.rule_id = v.endpoint_version JOIN {CS}.doc_section d ON "
                f"d.document_id = s.document_id AND d.section_number = s.section ORDER BY v.endpoint_version",
            ),
            (
                "What are the CSL-A eligibility criteria under protocol 3.0?",
                f"SELECT criterion_id, criterion_type, text, class_id FROM {STD}.eligibility_criterion WHERE "
                f"eligibility_rule_id = 'ELIG-A-V2' ORDER BY criterion_type DESC, criterion_id",
            ),
        ],
    },
    "ls_standards_semantics": {
        "tables": [
            f"{STD}.kb_concept",
            f"{STD}.kb_edge",
            f"{STD}.mondo_closure",
            f"{STD}.medrt_class_closure",
            f"{STD}.mesh_closure",
            f"{STD}.bc_closure",
            f"{STD}.concept_class",
            f"{STD}.class_root",
            f"{STD}.standards_manifest",
            f"{CS}.silver_vs",
            f"{CS}.gold_eligibility_criterion",
        ],
        "metric_views": [],
        "text": COMMON
        + [
            "Standards and semantics: MONDO diseases, MED-RT drug classes / mechanisms / physiologic effects / "
            "contraindications, MeSH (the bridge between MED-RT conditions and MONDO), RxNorm ingredients, CDISC "
            "Controlled Terminology, COSMoS biomedical concepts and SDTM dataset specializations. kb_edge holds DIRECT "
            "facts only; use the *_closure tables for is-a at any depth (WHERE ancestor_code = X).",
            "Concept class membership (e.g. WRC-V1 weight-related comorbidity) = descendant of a class_root kind='root' "
            "and NOT a descendant of any kind='exclude_root' (exclusion wins). WRC-V2 extends WRC-V1 (inherits roots).",
            "Predicates prefixed cpl: are demo extensions, never official CDISC content; standards_manifest lists the "
            "pinned releases. MedDRA, SNOMED CT, ATC and the CDISC Library are not used.",
            "Body Weight is COSMoS BC C81328 -> dataset specialization WEIGHT -> SDTM VS variables; allowed units "
            "(VSORRESU) are LB, g and kg. Physical data: silver_vs WHERE VSTESTCD = 'WEIGHT'.",
            "gold_eligibility_criterion shows the ontology path that decided each participant's criterion.",
        ],
        "examples": [
            (
                "Is familial hypercholesterolemia a weight-related comorbidity (WRC-V1)?",
                f"SELECT c.ancestor_code AS class_root, c.ancestor_name, c.depth FROM {STD}.mondo_closure c JOIN "
                f"{STD}.class_root r ON r.concept_id = c.ancestor_code AND r.kind = 'root' AND r.class_id = 'WRC-V1' "
                f"WHERE c.descendant_code = 'MONDO:0005439' AND NOT EXISTS (SELECT 1 FROM {STD}.mondo_closure x JOIN "
                f"{STD}.class_root e ON e.concept_id = x.ancestor_code AND e.kind = 'exclude_root' AND e.class_id = "
                f"'WRC-V1' WHERE x.descendant_code = c.descendant_code)",
            ),
            (
                "Which drugs are members of the GLP-1 receptor agonist class in MED-RT?",
                f"SELECT k.concept_id, k.label FROM {STD}.kb_edge e JOIN {STD}.kb_concept k ON k.concept_id = e.subject "
                f"WHERE e.predicate = 'medrt:memberOf' AND e.object = 'MEDRT:N0000178480' ORDER BY k.label",
            ),
            (
                "Where is body weight represented in the standardized dataset, and which units are allowed?",
                f"SELECT b.subject AS binding, v.object AS sdtm_variable, u.notation AS allowed_unit FROM {STD}.kb_edge h "
                f"JOIN {STD}.kb_edge b ON b.subject = h.object AND b.predicate = 'cosmos:constrains' LEFT JOIN "
                f"{STD}.kb_edge a ON a.subject = b.subject AND a.predicate = 'cosmos:allowedValue' LEFT JOIN "
                f"{STD}.kb_concept u ON u.concept_id = a.object JOIN {STD}.kb_edge v ON v.subject = b.subject AND "
                f"v.predicate = 'cosmos:constrains' WHERE h.subject = 'COSMOS_DSS:WEIGHT' AND h.predicate = "
                f"'cosmos:hasVariableBinding' ORDER BY sdtm_variable, allowed_unit",
            ),
            (
                "Which standards releases does the lab use?",
                f"SELECT artifact_id, publisher, release_version, license_or_terms_reference FROM {STD}.standards_manifest "
                f"ORDER BY artifact_id",
            ),
            (
                "Why was CSL-A-FX-25 excluded?",
                f"SELECT criterion_id, outcome, detail, path_labels FROM {CS}.gold_eligibility_criterion WHERE USUBJID = "
                f"'CSL-A-FX-25' AND outcome IN ('TRIGGERED', 'NOT_MET')",
            ),
        ],
    },
}


def body(spec: dict) -> dict:
    hexid = lambda n, p="0": f"{p}{n:031x}"  # noqa: E731  (32 hex chars, sequential = sorted)
    return {
        "version": 2,
        "config": {
            "sample_questions": [
                {"id": hexid(i + 1), "question": [q]} for i, (q, _) in enumerate(spec["examples"])
            ]
        },
        "data_sources": {
            "tables": [{"identifier": t} for t in sorted(spec["tables"])],
            **(
                {"metric_views": [{"identifier": m} for m in sorted(spec["metric_views"])]}
                if spec["metric_views"]
                else {}
            ),
        },
        "instructions": {
            "text_instructions": [{"id": hexid(1, "c"), "content": spec["text"]}],
            "example_question_sqls": [
                {"id": hexid(i + 1), "question": [q], "sql": [s]} for i, (q, s) in enumerate(spec["examples"])
            ],
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        for name, spec in SPACES.items():
            for q, s in spec["examples"]:
                print(json.dumps({"space": name, "q": q, "sql": s}))
        return
    for name, spec in SPACES.items():
        (ROOT / "resources" / f"{name}.geniespace.json").write_text(json.dumps(body(spec), indent=1) + "\n")
    print("wrote", ", ".join(f"resources/{n}.geniespace.json" for n in SPACES))


if __name__ == "__main__":
    main()
