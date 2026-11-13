---
name: Prohibited medications (PROHIB-CM-V1)
synonyms: [prohibited medication, concomitant medication, GLP-1 receptor agonist, appetite suppression, phentermine, semaglutide, tirzepatide, lookback, intercurrent event]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.clinical_study_standards.class_root
  - eli_test_classic_catalog.clinical_study.silver_cm
---

Prohibited: any drug that is a **member of** the MED-RT class GLP-1 Receptor Agonist [EPC] (N0000178480), or any drug
whose MED-RT **physiologic effect** is Appetite Suppression [PE]. The protocol names classes, not products.

- Active within **90 days before screening** → exclusion (EXC-CM).
- Started or taken **during treatment** → major protocol deviation: the participant stays in the FAS but leaves the
  PPS (intercurrent event).
