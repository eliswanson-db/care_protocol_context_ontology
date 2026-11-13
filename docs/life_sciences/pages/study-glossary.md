---
name: Study glossary
synonyms: [glossary, FAS, PPS, study day, reference date, baseline, target date, analysis window, intercurrent event, rule version]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.clinical_study_standards.rule_version
  - eli_test_classic_catalog.clinical_study_standards.analysis_population
---

- **Reference date**: the date of the first dose of study treatment (CSL-101 or placebo; placebo is recorded with
  dose 0 and still counts as dosed).
- **Study day**: date minus reference date, plus one on or after the reference date. There is no day 0.
- **Baseline**: the pre-treatment body weight the change is measured from (CSL-A: last valid; CSL-B: mean of valid).
- **Target date**: the date the Week 24 follow-up should fall on (CSL-A reference + 168 days; CSL-B + 167 days).
- **Analysis window**: how far from the target date a follow-up weight may be and still qualify. Different from the
  protocol's operational *scheduling* window used to book visits.
- **Rule version**: one approved, executable version of an endpoint's derivation (for example EP-A-WT24.R2).
- **FAS** (full analysis set): randomized and dosed. **PPS** (per-protocol set): FAS minus major deviations.
- **Major deviation**: an eligibility violation at the applicable protocol version, or a prohibited medication on
  treatment.
- **Intercurrent event**: starting a GLP-1 receptor agonist during treatment. FAS keeps observed weights
  (treatment-policy); PPS excludes the participant.
- **Candidate assertion**: a rule-like statement extracted from a document that has not been approved. It never
  changes a calculation.
