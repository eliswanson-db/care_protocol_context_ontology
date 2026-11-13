---
name: Unit normalization (body weight)
synonyms: [lb to kg, pounds, kilograms, VSRESU, LB, unsupported unit, stone, unit mapping, VSSTRESN]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.clinical_study.silver_vs
  - eli_test_classic_catalog.clinical_study_standards.kb_edge
---

The COSMoS WEIGHT dataset specialization allows `VSORRESU` = **LB, g, kg** (CDISC CT VSRESU). Raw site units map
to those values: kg/KG/Kg/kgs → kg; lb/lbs/Lb → LB; g → g. `VSSTRESN` is kg (LB × 0.45359237; g × 0.001).

Any other raw unit (for example `st`, stone) is kept as recorded, flagged `CPL_UNIT_MAPPING_STATUS =
UNMAPPED_RAW_UNIT`, and is **not valid** for the endpoint (UNSUPPORTED_UNIT). A blank unit is MISSING_UNIT. Nothing
is converted by guessing. The raw unit is always kept in `CPL_RAW_UNIT` for lineage.
