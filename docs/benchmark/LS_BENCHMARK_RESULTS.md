# Life-sciences benchmark: final results, protocol v3 (2026-11-25)

The HEDIS counterpart is `BENCHMARK_V2_RESULTS.md`, and the method (ADR-0028) is the same: one harness, one simple
agent, the same five approaches, and Genie One as the reasoning engine.

**Final run: 3 runs per cell; majority shown, ties go to the worse outcome. Every cell's three runs were audited.**
- The graph is clinicalstudylab v6. It adds population membership, protocol deviations and failed criteria,
  mirroring HEDIS's verdicts.
- RAG searches the Lakebase `clinical_study` corpus: 8 study documents and 848 monitoring visit reports.
- Questions, gold and the hand check: `docs/benchmark/ls_questions.yaml`. Holdout gold:
  `src/benchmark/ls_gold_queries.sql` (5/5). Raw cells: `docs/benchmark/ls_benchmark.json`.
- Run it with `CARE_DEMO=life_sciences_clinical PYTHONPATH=src:src/app DATABRICKS_CONFIG_PROFILE=ECT .venv/bin/python
  -m benchmark.retrieval_eval.run_retrieval_eval --final`.

| Q | Question (short) | Metric views | Closure tables | RAG | Genie Ontology | Ontobricks graph | Genie One |
|---|---|---|---|---|---|---|---|
| 1 | Week 24 % change by arm (R2) | ✓ one query (2/3) | found none | no query | ✓ one query | ✓ one query (hand) | ✓ |
| 2 | Same, baseline BMI ≥ 35 | no query | found none (2/3) | no query | no query | found none (1/3) | ✓ |
| 3 | Randomized with a weight-related comorbidity | no query | ✓ one query | no query | no query | **wrong** | ✓ |
| 4 | What Amendment 1 changed | no query | ✓ in context | no query | ✓ in context | ✓ one query (2/3) | ✓ |
| 5 | Where body weight is stored, unit, rule version | no query | incomplete (2/3), 1/3 facts | no query | ✓ in context | incomplete (hand) | ✓ |
| 6 | Prohibited drug started on treatment | no query | found none (2/3) | no query | no query | ✓ one query | ✓ |
| 7 | Why CSL-A-103-0137 left the PPS | found none (1/3) | ✓ one query | no query | no query | incomplete (2/3), 1/2 facts | ✓ |
| 8 | Qualified only because of sleep apnea | no query | **wrong** | no query | no query | no query (2/3) | ✓ |
| 9 | Why SITE-118's Week 24 visits were late | no query | no query | no query | no query | no query | ✗ |
| | **Answered** | 1 | 3 | 0 | 3 | 3 | 8 |

## What the run shows

- **Metric views answer their prebuilt measure (lq1) once told the as-of date.** Each approach also answers its
  natural question:
  - closure: the class-membership count (lq3) and the "why" path, through the participant's coded history (lq7);
  - Genie Ontology: the amendment and data-layout questions (lq4, lq5);
  - graph: the endpoint means (lq1) and the dated prohibited-medication count (lq6), straight from its triples.
- **Closure and graph hold the same data but answer different questions, for reasons each run shows.**
  - Closure misses lq1 / lq2 / lq6 on a *value* it didn't know: it filtered `rule_version = 'EP-A-WT24.R2'`, but that
    column holds `R2`. Table cards give column names, not example values; the graph's triples carry the values.
  - The graph misses lq3 (it didn't subtract the class's carve-outs, which SQL over triples makes awkward) and lq7
    (it didn't walk subClassOf to the exclusion root).
  - So each holds the answer; the difference is which store the agent can drive correctly in one query. The detail
    of each cell says how it went.
- **RAG answers none, and that's a finding.** The 848 monitoring reports crowd the 8 study documents out of the top
  five passages. Asked what Amendment 1 changed, it returned reports. A deployment would filter by document type or
  rerank; the benchmark measures it as built.
- **Genie One answers 8 of 9.** It misses lq9 because the monitoring reports are only in Lakebase.

## What changed on 2026-11-25

- **Protocol v3 (ADR-0028).**
- **The graph maps the verdicts gold holds,** as HEDIS does: FAS / PPS membership, ProtocolDeviation with
  violatesCriterion / evidencedBy, failsCriterion and ruleEligible. This supersedes ADR-0025's exclusion.
- **Answer key:** facts state values only. lq1 / lq2 / lq6 no longer restate the rule, subgroup or date, and lq5
  names the rule, not a date clause. Gold values are unchanged (5/5).
- **Closure retrieval** starts from the graph's entry points: linked participant, study, rule and class ids, the
  participant's coded record rolled up through the closures, and the rule and study versions.

## To re-check

After any change to the LS Pages, comments or Genie spaces:

```
.venv/bin/python -I scripts/record_genie_ontology.py --profiles ECT --questions docs/benchmark/ls_questions.yaml \
    --out docs/benchmark/genie_ontology_retrieval_ls.json
CARE_DEMO=life_sciences_clinical PYTHONPATH=src:src/app DATABRICKS_CONFIG_PROFILE=ECT .venv/bin/python -m \
    benchmark.retrieval_eval.run_retrieval_eval --arms genie_ontology,genie_one --final --merge
.venv/bin/python -I scripts/benchmark_audit.py --demo life_sciences_clinical
cp docs/benchmark/{ls_benchmark.json,genie_ontology_retrieval_ls.json,ls_questions.yaml} src/app/server/benchmark_data/
```
