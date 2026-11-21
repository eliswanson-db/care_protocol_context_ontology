---
name: Care-protocol rules (drug classes, contraindications, thresholds)
synonyms: [care protocol, protocol rules, contraindication, recommended for, first-line, SGLT2, ACE, ARB, statin, metformin, albuminuria, threshold, monitored by]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.care_protocol_terminology.protocol_edges
  - eli_test_classic_catalog.care_protocol_terminology.value_set_segment
---

These are the care-protocol knowledge edges, one sentence per edge. They are the same facts the knowledge graph
and `protocol_edges` hold: this Page is generated from `src/terminology/protocol_edges.csv` (`scripts/gen_protocol_pages.py`), so it can't drift from them. Synthetic demo protocol; not clinical guidance.

## Drug-class recommendations

- Statins are recommended for the SPD measure (statin therapy, ages 40-75). *(protocol section CP-DM-2025.1 sec2/sec6)*
- ACE inhibitors are recommended for albuminuria. *(protocol section CP sec4)*
- ARBs are recommended for albuminuria. *(protocol section CP sec4)*
- SGLT2 inhibitors are recommended for chronic kidney disease (value set `COMORBID_CKD`). *(protocol section CP sec3)*
- SGLT2 inhibitors are recommended for heart failure (value set `COMORBID_HF`). *(protocol section CP sec3)*
- Metformin (biguanide) is first-line for glucose lowering. *(protocol section CP-GLY-2)*

## Contraindications

- Statins are contraindicated with pregnancy (value set `CONTRA_PREGNANCY`). *(protocol section CP sec4)*
- Statins are contraindicated with active hepatic disease (value set `CONTRA_HEPATIC`). *(protocol section CP sec4)*
- ACE inhibitors are contraindicated with pregnancy (value set `CONTRA_PREGNANCY`). *(protocol section CP sec4)*
- ARBs are contraindicated with pregnancy (value set `CONTRA_PREGNANCY`). *(protocol section CP sec4)*
- Metformin (biguanide) is contraindicated when eGFR below 30 mL/min/1.73m². *(protocol section CP-GLY-2)*
- SGLT2 inhibitors are contraindicated when eGFR below 20 mL/min/1.73m². *(protocol section CP sec4)*

## What each measure is monitored by

- GSD is monitored by HbA1c (LOINC part LP-HBA1C). *(protocol section CP sec5)*
- KED is monitored by eGFR (LP-EGFR). *(protocol section CP sec5)*
- KED is monitored by uACR (LP-UACR). *(protocol section CP sec5)*
- BPD is monitored by systolic blood pressure (LP-SBP). *(protocol section CP sec5)*
- BPD is monitored by diastolic blood pressure (LP-DBP). *(protocol section CP sec5)*

## Thresholds and definitions

- Albuminuria is defined by uACR of 30 mg/g or more. *(protocol section CP sec4)*
- BPD has the threshold systolic below 140 mmHg. *(protocol section CP sec2)*
- BPD has the threshold diastolic below 90 mmHg. *(protocol section CP sec2)*
- GSD has the threshold good control: A1c below 8%. *(protocol section CP sec2)*
- GSD has the threshold poor control: A1c above 9%. *(protocol section CP sec3)*

## Which lab each threshold is measured on

- Good control: A1c below 8% is measured on HbA1c (LOINC part LP-HBA1C). *(protocol section CP sec2)*
- Poor control: A1c above 9% is measured on HbA1c (LOINC part LP-HBA1C). *(protocol section CP sec3)*
- eGFR below 30 mL/min/1.73m² is measured on eGFR (LP-EGFR). *(protocol section CP-GLY-2)*
- eGFR below 20 mL/min/1.73m² is measured on eGFR (LP-EGFR). *(protocol section CP sec4)*
- uACR of 30 mg/g or more is measured on uACR (LP-UACR). *(protocol section CP sec4)*
- Systolic below 140 mmHg is measured on systolic blood pressure (LP-SBP). *(protocol section CP sec2)*
- Diastolic below 90 mmHg is measured on diastolic blood pressure (LP-DBP). *(protocol section CP sec2)*

For the A1c recheck rule (Protocol Step 3) see the Page *Protocol Step 3 — A1c recheck within 90 days*.
