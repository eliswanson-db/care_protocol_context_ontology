# HEDIS benchmark v2: final results (2026-11-25)

**Final run: 3 runs per cell, majority shown, every cell hand-checked.** The graph is clinicaldomain v7, and the
answer key was corrected on 2026-11-25. The agent and judge are `databricks-claude-sonnet-5`. Questions, gold,
predictions and the hand check: `docs/benchmark/questions_v2.yaml` (`hand_notes` holds one note per cell;
`hand_overrides` holds where the check overrides the judge). Raw cells, with context, the one query, and every fact's
verdict and quote: `docs/benchmark/benchmark_v2.json`.

## How a cell is scored

**Retrieval approaches** use one simple agent. It reads what the approach retrieved, then may make **one query** in
the approach's own interface: SQL for metric views, RAG and Genie Ontology; one closure-tool call; one graph-runner
call.
- Each expected fact is judged **stated / missing / contradicted**, with a verbatim quote that is checked in code.
- A fact counts if the context states it **or** the one query does. The query is read with its rows: the query says
  what the rows are, and the rows carry the values.
- A SELECT of constants reads no table, so it isn't a query.

Outcomes:
- **in context** (tier 1): every fact is stated in what the approach retrieved.
- **one query** (tier 2): the context and the one query together state every fact.
- **incomplete**: some facts are stated, one is missing.
- **found none**: the query ran but stated no fact.
- **wrong**: it contradicts a fact.
- **query failed**.
- **no query**: the agent declined, and says why.
- **nothing**: retrieved nothing.

**Genie One**, a multi-step agent, is judged on its own answer.

| Q | Question (short) | Metric views | Closure | RAG | Genie Ontology | Graph | **Genie One** |
|---|---|---|---|---|---|---|---|
| 1 | GSD poor control by clinic | no query (1 of 3 ✓) | nothing | no query | **wrong** | no query | ✓ |
| 2 | 65–75, A1c > 9%, no statin | no query | no query | no query | no query | no query | ✓ |
| 3 | Diabetes with a kidney complication | no query | **✓ in context** | no query | **✓ one query** | no query | ✓ |
| 4 | A1c target, moderate comorbidity | no query | nothing | **✓ in context** | no query | no query | **wrong** |
| 5 | eGFR: measures, MY2026 codes, where defined | no query | nothing | no query | **✓ one query** | incomplete | ✓ |
| 6 | Contraindicated on 2026-10-30 | no query | nothing | no query | query failed | no query | ✓ |
| 7 | Why patient 00040be9 is an SPD gap | no query | no query | nothing | query failed | incomplete (hand) | ✓ |
| 8 | Outside eye exam for patient 0b4f4745 | no query | no query | **✓ in context** | no query | found none | **wrong** |
| | **Answered** | 0 of 8 | 1 | 2 | 2 | 0 | **6** |

## What the run shows

- **One query from a single layer's context answers little.** Six of the eight questions are data questions: a count,
  a rate, or one patient's record. They need the right joins on the first try, from names the context supplies. Genie
  One explores, runs several queries and retries, and answers 6 of 8. The comparison measures what each kind of
  context is *enough for*, not which tool is best.
- **Each answered retrieval cell is that approach's natural question.**
  - Closure tables answer the hierarchy rollup (q3).
  - Genie Ontology's context names the right tables and rules, so its one query works (q3, q5).
  - RAG answers the two questions whose answer exists only in documents: the protocol's individualized targets (q4)
    and a patient's outside eye-exam letter (q8).
- **Metric views decline the prebuilt measure (q1)**, even though the view's *Poor Control Rate by Clinic* is the
  answer. The question says "through 2026-10-30" and the view has no date to filter on; the data ends there anyway.
  One of the three runs answered.
- **Genie Ontology's misses are mostly about the context.**
  - q2: nothing it retrieved names the age column.
  - q4: it ranked the Page that holds the target but didn't read it.
  - q7: snippets from the deprecated dev dashboard still name a removed `status` column.
  - Its one outright wrong answer (q1) is a date boundary: an A1c taken during 2026-10-30 is counted as after the
    cutoff.
- **The graph (v7) holds the structure but not what these questions turn on.**
  - It has no dates on diagnoses, orders or results (fact F28), so it declines q2, q3 and q6.
  - It has no clinic (F07) and no MY2026 value-set membership (F15).
  - Letters aren't in it, by design.
  - In v7, a patient now reaches their own lab values (v3 couldn't). What it still lacks is listed in
    `hedis_facts.yaml` as gaps.
- **Genie One misses only the document questions, for a structural reason.** It can't reach the protocol text or the
  Lakebase letters. On q4 it searched the rules table and said targets are uniform; on q8 it found, correctly, no
  outside record in the tables.

## What changed on 2026-11-25 (all on ECT)

- **Answer key.** Every expected fact now asks only what its question asks and says what the data says:
  - q2: no denominator; q3: no definition clause; q5: no "MDRD was dropped"; q8: no abstraction advice.
  - q6 asks *how many*, which is what its key checks.
  - q7: the 2009 statin is an open-ended **order**, not a dispense. Genie One said so and had been marked wrong; its
    gold query now reads `care_order_med`, as q6's does.
  - `verify_gold` 28/28.
- **Judging.**
  - Each fact gets a stated / missing / contradicted verdict, and a contradiction must be a different value.
  - The one query is read with its rows, and the context and the query count together.
  - A SELECT of constants doesn't count as a query.
  - The agent gives its reason when it declines.
  - Each change was made because a cell was misjudged. Each time, the fix was in the answer key or the judge's rules,
    never in a single cell's score.
- **Graph.** The column is scored on v7 (gate 12/12 required, 9/9 optional), not v3.
- **Genie recording.** Genie One and Genie Ontology were re-recorded for the corrected questions on 2026-11-25. The
  dev Genie spaces and dashboards were deprecated the same day, but Genie's snippet index hadn't refreshed: 49 of the
  175 snippets still came from them.

## To re-check after Genie's snippet refresh

The deprecated dev assets still feed snippets until Genie re-indexes, roughly daily. After that, re-record and
re-score the two Genie columns (the other columns don't change):

```
.venv/bin/python -I scripts/record_genie_ontology.py --profiles ECT
PYTHONPATH=src:src/app DATABRICKS_CONFIG_PROFILE=ECT .venv/bin/python -m benchmark.retrieval_eval.run_retrieval_eval \
    --arms genie_ontology,genie_one --final --merge --out benchmark_v2.json
cp docs/benchmark/{benchmark_v2.json,genie_ontology_retrieval_v2.json} src/app/server/benchmark_data/
```

Then hand-check any cell that changed against its note in `questions_v2.yaml`.
