---
name: Dataset and domain guide (Clinical Study Lab)
synonyms: [SDTM, ADaM, DM, VS, EX, MH, CM, DS, SV, bronze, silver, gold, VSSTRESN, VSORRESU, CPL columns]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.clinical_study.silver_vs
  - eli_test_classic_catalog.clinical_study.silver_dm
  - eli_test_classic_catalog.clinical_study.gold_endpoint_result
  - eli_test_classic_catalog.clinical_study.gold_endpoint_candidate
---

| Layer | Tables | Shape |
|---|---|---|
| Bronze | `bronze_edc_subjects`, `_vs`, `_ex`, `_mh`, `_cm`, `_ds`, `_sv` | Raw EDC exports exactly as delivered (all strings) + source file |
| Silver | `silver_dm`, `silver_vs`, `silver_ex`, `silver_mh`, `silver_cm`, `silver_ds`, `silver_sv` | SDTM-shaped (CDISC variable names, CT values) |
| Gold | `gold_endpoint_result`, `gold_endpoint_candidate`, `gold_participant_population`, `gold_eligibility_criterion`, `gold_amendment_impact`, `gold_study_summary`, `gold_provenance_edge`, `gold_tracer_registry` | ADaM-shaped analysis records with traceability |

Body weight is `silver_vs` where `VSTESTCD = 'WEIGHT'`: `VSORRES`/`VSORRESU` as collected (unit mapped
to CT), `VSSTRESN` in kg, `VSDY` study day. Columns prefixed `CPL_` are demo extensions (raw unit, unit
mapping status, MONDO/RxNorm codes, source record id). `gold_endpoint_candidate` keeps **every** weight
observation per participant and rule version with its decision and reason, not just the winners.
