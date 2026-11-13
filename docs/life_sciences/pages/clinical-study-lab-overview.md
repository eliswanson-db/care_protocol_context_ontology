---
name: Clinical Study Context & Evidence Lab (overview)
synonyms: [clinical study lab, CSL-A, CSL-B, CSL-101, study evidence lab, life sciences demo]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.clinical_study.gold_endpoint_result
  - eli_test_classic_catalog.clinical_study.gold_study_summary
  - eli_test_classic_catalog.clinical_study_standards.rule_version
---

**SYNTHETIC educational demo.** Two fictional studies of a fictional compound (CSL-101, a GLP-1 receptor agonist).
The data are SDTM-shaped and ADaM-shaped for a narrow scope; they are **not submission-ready**, not validated, and
**not for clinical use**. Results are descriptive and cannot show efficacy, superiority or any causal effect.

**The story:** from a raw study observation to a reproducible endpoint result, with CDISC-grounded meaning,
protocol-aware context and record-level traceability.

| Study | Design | Week 24 endpoint |
|---|---|---|
| CSL-A | 72 weeks, 2:1 CSL-101 10 mg once weekly vs placebo; obesity, or overweight with a weight-related comorbidity | EP-A-WT24, rule versions R1 (±7 days) and R2 (±14 days, Amendment 1) |
| CSL-B | 52 weeks, 1:1; type 2 diabetes with BMI ≥ 27 | EP-B-WT24, R1 (mean baseline, ±10 days) |

**Three questions the lab answers:** What was the percent change in body weight at Week 24, which observations
qualified, and why? The visit window changed: whose selected observations and results changed, and why? Are the
CSL-A and CSL-B Week 24 endpoints equivalent? (No; see Cross-study comparability.)

Every result row carries its study, endpoint rule version, protocol and SAP versions, and execution run id.
