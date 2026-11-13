---
name: Standards and versions (Clinical Study Lab)
synonyms: [CDISC, controlled terminology, COSMoS, biomedical concept, dataset specialization, MONDO, MED-RT, MeSH, NCIt, RxNorm, standards manifest, release]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.clinical_study_standards.standards_manifest
  - eli_test_classic_catalog.clinical_study_standards.kb_concept
  - eli_test_classic_catalog.clinical_study_standards.kb_edge
---

All standards are **open** releases, pinned with checksums in `standards_manifest`. The CDISC Library (SDTMIG
text, RDF), MedDRA, SNOMED CT and WHO ATC are **not used**. Only the public NCI EVS release of MED-RT is used.

| Source | Release | Role |
|---|---|---|
| CDISC SDTM Controlled Terminology (NCI EVS) | 2026-09-25 file | Test codes, units, codelists |
| CDISC COSMoS biomedical concepts and SDTM dataset specializations | package 2026-11-02 | Body Weight concept C81328 → WEIGHT specialization → VS variables and allowed units |
| MONDO | 2026-11-03 | Disease hierarchy (eligibility and exclusion classes) |
| MED-RT (public EVS release) | 2026.11.02 | Drug classes, mechanisms, physiologic effects, contraindications |
| MeSH descriptors + supplementary concept records | 2026 | Bridge between MED-RT conditions and MONDO diseases |
| NCIt | 26.10d | Labels for CDISC C-codes |
| RxNorm | as referenced by MED-RT | Drug ingredients |

**Official vs demo extension.** `kb_edge` holds only direct facts from these sources. Predicates prefixed
`cpl:` are demo extensions (for example one curated MONDO→MeSH equivalence for medullary thyroid carcinoma,
whose reason is recorded), and are never official CDISC content. Medical history is coded to MONDO instead of
MedDRA; this is a documented deviation.
