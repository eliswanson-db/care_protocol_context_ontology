---
name: Known limitations (Clinical Study Lab)
synonyms: [limitations, not submission ready, synthetic, MedDRA, study day convention, ontology gap, hypertensive heart disease]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.clinical_study_standards.standards_manifest
---

- **Synthetic** data, documents and compound. Simulated effects do not represent any real product or trial.
- SDTM-/ADaM-**shaped**, not conformant or submission-ready. No define.xml; SDTMIG text is not vendored.
- Study-day arithmetic is simplified (no day 0, dates only); it does not implement every CDISC convention.
- MH is coded to MONDO and CM to RxNorm ingredients, not MedDRA/WHODrug (licensed).
- **Ontology gaps are shown, not patched:** MONDO does not place hypertensive heart disease under hypertensive
  disorder, so it is not a weight-related comorbidity member. MONDO lacks a MeSH cross-reference for medullary
  thyroid carcinoma; one curated, namespaced equivalence (with its reason) closes it.
- MED-RT is not uniform within a class (for example the medullary thyroid carcinoma contraindication sits on
  different MeSH records for different GLP-1 receptor agonists). The study rule treats a contraindication for
  **any** class member as a class contraindication.
- All approvals and reviews are **seeded demo fixtures**, not real human review.
