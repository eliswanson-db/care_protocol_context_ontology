# Terminology sources & licenses (vendored subsets)

We vendor **small curated subsets** of the codes the demo references — not full releases. Code values are
facts; subsets are kept minimal and attributed. No Google Drive / runtime dependency (ADR-0007).

| System | File | License / attribution |
|---|---|---|
| **ICD-10-CM** | `icd10cm_subset.csv` | Public domain (U.S. CMS / CDC NCHS). Freely redistributable. |
| **LOINC®** | `loinc_subset.csv` | LOINC is © Regenstrief Institute, Inc. Used under the LOINC License (free). "This content contains content from LOINC® (http://loinc.org). LOINC is copyright © 1995-2024, Regenstrief Institute, Inc. and the LOINC Committee and is available at no cost under the LOINC License." Curated subset only; not modified. |
| **RxNorm** | `rxnorm_statins.csv` | Produced by the U.S. National Library of Medicine (NLM); free to use/redistribute. |
| **Demo value sets** | `value_sets_demo.csv` | Hand-curated for this demo. **Not NCQA/HEDIS and not VSAC** — labeled demo only. |

**Not vendored / not used:** full LOINC release, SNOMED CT, UMLS, VSAC (no license; ADR-0002). If the
LOINC subset is ever expanded, follow the LOINC License terms and keep the attribution above. The full raw
releases, if ever staged locally, go under `context/terminology/data/` which is gitignored.
