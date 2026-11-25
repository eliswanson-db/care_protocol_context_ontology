# HEDIS benchmark v2: final results, protocol v3 (2026-11-25)

**Final run: 3 runs per cell; majority shown, ties go to the worse outcome. Every cell's three runs were audited.**
- The graph is clinicaldomain v8 (gate: no predicate lost or shrunk; 3 new node types, 11 new predicates).
- The agent and judge are `databricks-claude-sonnet-5`.
- Method: ADR-0028. Questions, gold, predictions and the hand check (one note per cell, plus overrides):
  `docs/benchmark/questions_v2.yaml`. Raw cells, with every run's context, query, result and per-fact verdicts:
  `docs/benchmark/benchmark_v2.json`.

## How a cell is scored (protocol v3)

Each approach **retrieves in its own way**, and that retrieval may query its own store:
- **Metric views:** their metadata.
- **Closure:** the resolved concepts, their edges, and table cards for the same source tables the graph maps.
- **RAG:** passages.
- **Genie Ontology:** Genie's own snippets and Pages.
- **Graph:** the entity-linked subgraph and the graph schema.

The same simple agent, told the data runs through 2026-10-30, then writes **one read-only SQL query** over the same
lakehouse: metric views with `MEASURE()`, closure tables joined to the data, the graph over its triplestore.

Judging:
- Each expected fact is judged **stated / missing / contradicted**, with a verbatim quote that is checked in code.
- A fact counts if the context or the query and its rows state it.
- A contradiction is a different value. An empty result states no value, so it can't contradict one.
- Identical evidence always gets the same verdict, because judgments are cached on disk.

**Genie One**, a multi-step agent, is judged on its own answer.

| Q | Question (short) | Metric views | Closure tables | RAG | Genie Ontology | Ontobricks graph | Genie One |
|---|---|---|---|---|---|---|---|
| 1 | GSD poor control by clinic | ✓ one query | ✓ one query | no query | ✓ one query | found none (1/3) | ✓ |
| 2 | 65–75, A1c > 9%, no statin | no query | ✓ one query (2/3) | no query | no query | no query (2/3) | ✓ |
| 3 | Diabetes with a kidney complication | no query | ✓ in context | no query | ✓ one query | ✓ one query (2/3) | ✓ |
| 4 | A1c target, moderate comorbidity | no query | no query | ✓ in context | no query | no query | **wrong** |
| 5 | eGFR: measures, MY2026 codes, where defined | incomplete, 1/3 facts | incomplete, 1/3 facts | incomplete, 2/3 facts | ✓ one query | incomplete (2/3), 2/3 facts | ✓ |
| 6 | Contraindicated on 2026-10-30 | no query | no query | no query | **wrong** (2/3) | **wrong** (1/3) | ✓ |
| 7 | Why patient 00040be9 is an SPD gap | no query | incomplete, 1/4 facts | nothing | query failed | incomplete (hand), 2/4 facts | ✓ |
| 8 | Outside eye exam for patient 0b4f4745 | no query | no query | ✓ in context | no query | no query | **wrong**, 1/2 facts |
| | **Answered** | 1 | 3 | 2 | 3 | 1 | 6 |

"(k/3)" means the shown outcome won k of the three runs. Graph q1, for example, answered in 1 run, found none in 1 and
was wrong in 1; the tie goes to the worse outcome. "(hand)" means the hand check overrides the judge.

## What the run shows

- **Every approach now answers its natural questions, and no approach is boxed out by the setup.**
  - Metric views answer the prebuilt measure (q1) once told the data's as-of date.
  - Closure answers the hierarchy rollup (q3), and with the graph's source tables the clinic rates (q1) and the
    two-measure question (q2).
  - RAG answers the two document questions (q4, q8).
  - Genie Ontology's context names the right tables for q1, q3 and q5.
- **Closure and graph hold the same data and agree on what's answerable (q1–q3).** The graph does it less reliably:
  1–2 of 3 runs against closure's 2–3 of 3. Same facts, but a one-shot SQL query over a subject / predicate / object
  table needs several self-joins, where closure joins typed tables.
  - This is the interface cost, measured. SPARQL would remove it; ADR-0028 records why the graph isn't queried with
    SPARQL yet.
  - Neither approach gets the time-and-lab question (q6) right in one query.
- **q6 and q7 are the hard ones for a single query.** q6 needs each patient's *last* eGFR before a date and active
  orders and conditions; q7 needs one patient's diagnosis, age, dispense history and the SPD rule together. Genie
  One, exploring with several queries, answers both.
- **Genie One misses only what it can't reach:** the protocol text (q4) and the Lakebase letter (q8).
- **Genie Ontology's q7 failure is stale context.** Its query uses a `status` column that gold no longer has. The
  snippet comes from the deprecated dev dashboard, which Genie's index still serves (49 of 175 snippets on
  2026-11-25).

## What changed on 2026-11-25

- **Protocol v3 (ADR-0028):** the same action for every retrieval approach, and the as-of date told to each.
- **Graph content parity (R2RML rev 10, v8):**
  - dated ConditionRecord and MedicationOrder records;
  - Observation result dates;
  - Clinic attribution;
  - lab value-set membership.
  - `hedis_facts.yaml`: the graph now holds 23 facts; only Protocol Step 3 (F11) is unmapped.
- **Answer key:** every expected fact states the answer only, never the question's conditions or one store's table
  name:
  - q2 drops its denominator, q3 its definition clause, q5 its table name, q8 its advice;
  - q6 asks *how many*;
  - q7 says the 2009 statin is an *order* (Genie One was right).
  - `verify_gold` 28/28.
- **Judging:**
  - fact verdicts with quotes; context and query judged together;
  - empty results are *found none*;
  - judgments are cached on disk, so identical evidence always gets the same verdict;
  - `scripts/benchmark_audit.py` covers all runs.
- **Harness fixes:**
  - a fence-stripping bug that removed a closing backtick from correct SQL;
  - closure retrieval now uses the graph's entry points: the entity linker, a named patient's coded record and the
    protocol edges.
  - the shared lexicon links "contraindicated" to lab-threshold rules as well.

## To re-check after Genie's snippet refresh

Re-record and re-score the two Genie columns once the deprecated dev assets drop out of Genie's snippet index:

```
.venv/bin/python -I scripts/record_genie_ontology.py --profiles ECT
PYTHONPATH=src:src/app DATABRICKS_CONFIG_PROFILE=ECT .venv/bin/python -m benchmark.retrieval_eval.run_retrieval_eval \
    --arms genie_ontology,genie_one --final --merge --out benchmark_v2.json
.venv/bin/python -I scripts/benchmark_audit.py
cp docs/benchmark/{benchmark_v2.json,genie_ontology_retrieval_v2.json,questions_v2.yaml} src/app/server/benchmark_data/
```
