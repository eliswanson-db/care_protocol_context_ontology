# Terminology (vendored, demo subset)

**Self-contained — no Google Drive / runtime download dependency** (ADR-0007). These are small, curated
subsets of the codes the demo actually references, committed so the build is reproducible from the repo
alone. **Demo scope — validate every code against the official source before any non-demo use.**

| File | Loads into | Source / license |
|---|---|---|
| `icd10cm_subset.csv` | `icd10_hier` (adjacency → `icd10_closure`) | ICD-10-CM, public domain (CMS/CDC) |
| `loinc_subset.csv` | `loinc` | LOINC® — curated subset, see `LICENSES.md` (attribution required) |
| `rxnorm_statins.csv` | `rxnorm_statin` | RxNorm (NLM), free |
| `value_sets_demo.csv` | `value_set_segment` | Hand-curated **demo** value sets (not NCQA/VSAC) |

- `icd10cm_subset.csv` is the **adjacency list** that `../semantic/closure_tables.sql` builds the closure
  from (includes `E11.21` ⊏ `E11.2` ⊏ `E11` — the T3 subsumption tracer).
- `value_sets_demo.csv` seeds the **segment table**; note `CARDIORENAL_COHORT` is a deliberate
  **cross-branch** set (diabetes + CKD + HF) that no subtree equals — the segment-table demo.

## Load

```bash
databricks bundle run load_terminology -t ect --profile ECT      # once wired into resources/jobs.yml
# or run src/terminology/load_terminology.py as a notebook/job (reads these CSVs → Delta tables)
```

Then build the closure: run `../semantic/closure_tables.sql` on a SQL warehouse.
