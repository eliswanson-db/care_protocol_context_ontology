# Terminology sources & licenses

**Rule:** terminology content is **never committed** to this repo. It is staged into a UC Volume at
runtime and read from there. `context/terminology/data/` is gitignored. We do not write back to any Drive.

| System | Use | Source | License / note |
|---|---|---|---|
| **LOINC 2.83** | labs/observations + Part hierarchy | Eli's Google Drive (standard release) | LOINC License v5.8 (`LoincLicense_5.8.txt`) — honor terms; load from Volume |
| **ICD-10-CM** | diagnoses, cohort, exclusions, subsumption demo | CMS / CDC | Public domain |
| **RxNorm** | medications (statins/SPD) | NLM | Free (RxNorm is open; no UMLS needed for core files) |
| **Demo value sets** | measure numerators/denominators | hand-curated from the above | Labeled *demo — not NCQA/VSAC* |
| LOINC SNOMED Extension (optional) | LOINC-side ontology for Ontobricks only | Eli's Drive (`SnomedCT_LOINCExtension_…20261021`) | **Only if SNOMED is licensed** — not used by default (ADR-0002) |

**Not used:** SNOMED CT base, UMLS, VSAC (no license; ADR-0002). The subsumption story uses the
ICD-10-CM hierarchy instead of SNOMED is-a.
