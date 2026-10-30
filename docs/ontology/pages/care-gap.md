---
name: Care Gap (Numerator, Denominator, MET / NOT_MET)
synonyms: [care gap, gap in care, numerator, denominator, compliance, adherence, MET, NOT_MET, compliance rate]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.care_protocol.gold_adherence_gsd
  - eli_test_classic_catalog.care_protocol.gold_adherence_ked
---

HEDIS measures are expressed as a **denominator** and a **numerator**, and compliance is the ratio.

- **Denominator (eligible):** the patients a measure applies to (e.g. the diabetes cohort in an age band).
- **Numerator (compliant):** the eligible patients who received the required care (e.g. an A1c test for GSD;
  both eGFR and uACR for KED).
- **Status:** a patient is **MET** when in the numerator, otherwise **NOT_MET** — a **care gap** (eligible but
  missing the required care). Closing care gaps raises the measure's compliance rate.
- **Compliance rate** = compliant ÷ eligible, exposed as a governed measure in the metric views
  (`GSD Compliance Rate`, `KED Compliance Rate`). Each gold row keeps **record-level evidence** (the test
  date/code/value) so a gap, or a met status, is fully traceable.

> HEDIS-aligned demo, not NCQA-certified.
