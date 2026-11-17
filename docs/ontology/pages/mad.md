---
name: MAD — Medication Adherence for Diabetes Medications
synonyms: [MAD, medication adherence, diabetes medication adherence, PDC, proportion of days covered, refill gap, adherence gap, star measure]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.care_protocol.gold_adherence_mad
  - eli_test_classic_catalog.care_protocol_semantic.mad_compliance_metrics
  - eli_test_classic_catalog.care_protocol_terminology.rxnorm_closure
---

**MAD** measures whether patients keep taking their diabetes medication, using the **proportion of days covered (PDC)**
by pharmacy fills.

- **Eligible population (denominator):** diabetes patients aged **18+** with **at least 2 fills** of a diabetes
  medication in the measurement year. In this demo the medication class is **biguanides (metformin)**: every RxNorm
  code under `DRUGCLASS-BIGUANIDE` in `rxnorm_closure`.
- **PDC:** covered days / treatment period, with overlapping fills capped so a day is never counted twice, and fills
  clipped to the measurement year.
- **Numerator (adherent):** **PDC ≥ 80%**. Otherwise **NOT_MET** (a refill / adherence gap).
- **Metrics:** `MAD Adherence Rate` and `Avg PDC` in `mad_compliance_metrics`.

HEDIS-aligned demo, not NCQA-certified. The real measure covers more diabetes medication classes than this demo does.
