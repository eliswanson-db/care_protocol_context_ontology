---
name: Exclusionary history and class contraindications
synonyms: [exclusion criteria, contraindication, MTC, MEN2, pancreatitis, diabetic ketoacidosis, GLP-1 contraindication, EXC-MH, EXC-CI, drug allergy]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.clinical_study_standards.class_root
  - eli_test_classic_catalog.clinical_study_standards.kb_edge
---

**EXCL-MH-V1 roots:** medullary thyroid gland carcinoma (MONDO:0015277), multiple endocrine neoplasia type 2
(MONDO:0019003), pancreatitis (MONDO:0004982), type 1 diabetes mellitus (MONDO:0005147), diabetic retinopathy
(MONDO:0005266; not exclusionary in CSL-B), bipolar disorder (MONDO:0004985), schizophrenia (MONDO:0005090).

**CI-STUDY-DRUG-CLASS:** a condition is also exclusionary if MED-RT records it as a contraindication (CI_with) for
**any** member of the GLP-1 receptor agonist class (MED-RT EPC N0000178480). The walk only broadens: MONDO
condition → its is_a ancestors → equivalent MeSH record → broader MeSH records → MeSH concept → CI_with ← drug. It
never steps down to a narrower record.

**Ignored target:** MED-RT "Drug Hypersensitivity" (MeSH D004342) means allergy to that product, so a history of an
unrelated drug allergy does **not** exclude.
