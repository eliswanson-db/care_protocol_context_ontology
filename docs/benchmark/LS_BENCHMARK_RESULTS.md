# Life-sciences benchmark: final results (2026-11-25)

The HEDIS counterpart is `BENCHMARK_V2_RESULTS.md`, and the method is the same: one harness, one simple agent, the
same five approaches, and Genie One as the reasoning engine.

**Final run: 3 runs per cell, majority shown, every cell hand-checked.**
- The graph is clinicalstudylab v4. RAG searches the Lakebase `clinical_study` corpus: 8 study documents and 848
  monitoring visit reports.
- The agent and judge are `databricks-claude-sonnet-5`.
- Questions, gold, predictions and the hand check (one note per cell): `docs/benchmark/ls_questions.yaml`.
- Holdout gold: `src/benchmark/ls_gold_queries.sql` (5/5). Raw cells: `docs/benchmark/ls_benchmark.json`.

Run it with `CARE_DEMO=life_sciences_clinical PYTHONPATH=src:src/app DATABRICKS_CONFIG_PROFILE=ECT
.venv/bin/python -m benchmark.retrieval_eval.run_retrieval_eval --final`. The scoring is the same as HEDIS: each
fact is judged stated / missing / contradicted, and the context and the one query count together.

| Q | Question (short) | Metric views | Closure | RAG | Genie Ontology | Graph | **Genie One** |
|---|---|---|---|---|---|---|---|
| 1 | Week 24 % change by arm (R2) | no query | nothing | no query | **✓ one query** (2 of 3) | no query | ✓ |
| 2 | Same, baseline BMI ≥ 35 | no query | nothing | no query | no query | no query | ✓ |
| 3 | Randomized with a weight-related comorbidity | no query | **✓ one query** (2 of 3) | no query | no query | no query | ✓ |
| 4 | What Amendment 1 changed | no query | nothing | no query | **✓ in context** | **✓ in context** | ✓ |
| 5 | Where body weight is stored, unit, rule version | no query | nothing | no query | **✓ one query** (2 of 3) | found none | ✓ |
| 6 | Prohibited drug started on treatment | no query | no query | no query | no query | no query | ✓ |
| 7 | Why CSL-A-103-0137 left the PPS | no query | nothing | no query | no query | found none | ✓ |
| 8 | Qualified only because of sleep apnea | no query | no query | no query | no query | no query | ✓ |
| 9 | Why SITE-118's Week 24 visits were late | no query | nothing | no query | no query | no query | **wrong** |
| | **Answered** | 0 of 9 | 1 | 0 | 3 | 1 | **8** |

## What the run shows

- **The same shape as HEDIS.** One query from one layer's context answers little. Genie One explores and retries, and
  answers 8 of 9. It misses only the question whose answer is in documents it can't reach: lq9's monitoring report,
  which lives only in Lakebase. It answered that no reports exist, the counterpart of HEDIS q8's outside letter.
- **Genie Ontology does best of the retrieval approaches (3).** Its Pages name the governed view and the rule version
  (lq1), state Amendment 1 outright (lq4), and say where body weight lives (lq5).
- **The graph answers the amendment question from its own triples (lq4).** The changes and the date are on
  StudyVersion/CSL-A.P2.0. It holds the participant-level path for lq7 (the trace walks it: record → codedAs → MONDO
  → subClassOf → the EXCL-MH-V1 root), but its one call asked for endpoint exclusion reasons instead. The runner
  can't average, compute BMI, subtract a class's carve-outs or compare dates, so lq1, lq2, lq3, lq6 and lq8 are out
  of reach in one call.
- **The closure tools answer the class-membership count (lq3)**: WRC-V1's roots minus its carve-outs, joined to
  randomized CSL-A participants.
- **RAG answers none, and that's a finding, not noise.**
  - The corpus is 8 study documents and 848 monitoring visit reports, and the reports crowd the documents out of the
    top five passages. Asked what Amendment 1 changed (lq4), it returned five reports.
  - On lq9 it ranks later SITE-118 reports, which only point back to the 2025-09-18 report that records the cause.
  - That is how plain hybrid retrieval behaves over a realistic document mix. A deployment would filter by document
    type or rerank; the benchmark measures it as built.
- **Metric views decline the prebuilt measure (lq1)**, as in HEDIS q1. The question names the 2026-10-31 cutoff, and
  the view has no date to filter on; the data ends there anyway.

## Answer key (2026-11-25)

Each expected fact asks only what its question asks:
- the participant counts and denominators the questions didn't ask for are gone;
- lq5 and lq7 are split into one fact per thing asked;
- lq9's follow-up action is dropped.

The holdout gold values are unchanged (`verify_gold --gold src/benchmark/ls_gold_queries.sql`: 5/5).

## To re-check

Genie Ontology and Genie One were recorded on 2026-11-25 (`docs/benchmark/genie_ontology_retrieval_ls.json`).
Re-record and re-score those two columns after any change to the LS Pages, comments or Genie spaces:

```
.venv/bin/python -I scripts/record_genie_ontology.py --profiles ECT --questions docs/benchmark/ls_questions.yaml \
    --out docs/benchmark/genie_ontology_retrieval_ls.json
CARE_DEMO=life_sciences_clinical PYTHONPATH=src:src/app DATABRICKS_CONFIG_PROFILE=ECT .venv/bin/python -m \
    benchmark.retrieval_eval.run_retrieval_eval --arms genie_ontology,genie_one --final --merge
cp docs/benchmark/{ls_benchmark.json,genie_ontology_retrieval_ls.json,ls_questions.yaml} src/app/server/benchmark_data/
```
