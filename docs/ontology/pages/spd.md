---
name: SPD — Statin Therapy for Patients With Diabetes
synonyms: [SPD, statin therapy, statin use, statin adherence, cholesterol medication for diabetics, lipid therapy]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.care_protocol.gold_adherence_spd
  - eli_test_classic_catalog.care_protocol.spd_compliance_metrics
  - eli_test_classic_catalog.care_protocol_terminology.rxnorm_closure
---

**SPD (Statin Therapy for Patients With Diabetes)** is a HEDIS measure for statin use in diabetic patients.

- **Eligible population (denominator):** patients aged **40–75** as of the end of the measurement year in the
  **diabetes cohort**.
- **Numerator (compliant):** dispensed **at least one statin** during the measurement year.

**Why this exercises the ontology:** the `SPD_STATIN` value set lists RxNorm **ingredients** (e.g. `36567`
simvastatin, `83367` atorvastatin), but prescriptions carry RxNorm **clinical-drug** codes (e.g. `312961`
*Simvastatin 20 MG Oral Tablet*). A flat match of ingredients against prescriptions finds **zero** statins.
SPD instead resolves statins by **subsumption over `rxnorm_closure`** (ingredient → its clinical drugs) — the
same closure-join pattern used for the diabetes cohort over ICD-10. This is the medication-side companion to
ICD-10 subsumption: meaning comes from the hierarchy, not a flat code list.

> HEDIS-aligned demo, not NCQA-certified.
