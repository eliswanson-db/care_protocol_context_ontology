# Context Lab plan (2026-11-20) — plan of record for both demos

**HEDIS is close to right: this plan adjusts it, it doesn't rebuild it.** Everything below reuses what exists:
the pipeline, measures, terminology and closures, metric views, Pages, Genie spaces and knowledge stores, Lakebase
RAG, the Ontobricks graph, the retrieval-eval harness and the app. The life-sciences lab is brought into the same
shape.

## The story

Here are five context/retrieval approaches a customer can build on Databricks. We put the **same information** into
each one, as far as that's feasible, using a well-architected context layer. Then we do two things:

1. **Trace** a few pieces of information from source through the medallion architecture into each retrieval mode.
2. **Benchmark** the value of each approach with a **simple custom agent**, so we measure the retrieval, not the
   agent. Then show **Genie One**, a multi-step agent, answering every question when it's the reasoning engine.

Data is synthetic but realistic. There are no planted traps or trick questions. Every question is one a quality
analyst (HEDIS) or clinical scientist (life sciences) would actually ask. Nothing is faked: every result shown is
a recorded run.

## What each approach should showcase

| Approach | Strength we show | Limit we show |
|---|---|---|
| Metric views | Fast, governed, exact answers for measures built ahead of time | No answer for a measure nobody built |
| Closure tables | Exact hierarchy rollups and traversal along pre-chosen closures | Only the relationships someone materialized |
| RAG | Easy; answers anything stated in the documents | Only what's in the documents; shallow retrieval, no counts or joins |
| Genie Ontology | RAG-like retrieval with much richer semantic context: Pages, metric views, comments, table knowledge, beyond the docs | Retrieves context, doesn't compute multi-hop answers itself |
| Ontobricks graph | Deterministic reasoning engine for multi-hop typed queries and explanations | Needs the ontology and mapping built and published first |

None has to win. Each one's value and limits should be visible.

## 1. Context layer layout (same shape for both demos)

| Layer | Where | Built by |
|---|---|---|
| Source documents (protocol, guideline, payer/SAP memos), realistic synthetic PDFs | UC volume | repo → bundle sync |
| Raw → bronze → silver → gold | `<demo>` schema, Lakeflow pipeline | job |
| Reference terminology + closure tables | `<demo>_terminology` / `_standards` | job |
| Metric views + column comments | `<demo>_semantic` | job |
| RAG: documents → chunks → Lakebase hybrid index (as today) | Lakebase | script |
| Genie Ontology: Pages (API) + Genie spaces with knowledge stores | workspace | job (`sync_pages`, `genie_knowledge`) |
| Graph: Ontobricks ontology mapped onto the real silver/gold/terminology tables | `eswanson_demo.ontobricks` | **manual** (import + publish) |

## 2. Same information, as far as feasible

- One short **fact list** per demo (~25 facts, `docs/<demo>/facts.yaml`). These are the facts the questions
  depend on. For each fact, record where it lives in each mode, or why it can't live there (e.g. RAG can't hold
  25k patient rows). One test checks presence.
- HEDIS: this is mostly a write-up of what the consistency audit already checks. Close the gaps it found that
  the questions need. In life sciences it replaces the heavy parity machinery:
  - the graph-spec generator and the ~100 `clinical_study_graph` views;
  - the per-concept RAG reference entries.

## 3. Traces (3 per demo)

**HEDIS:**
- (a) **A1c result.** One patient's A1c result → bronze lab → silver observation (LOINC 4548-4) → gold GSD
  "poor control" → metric view → graph (`hasObservation`) → Genie answer.
- (b) **Guideline rule.** "Metformin is contraindicated at eGFR < 30" → protocol PDF → RAG chunk / Page /
  `protocol_edges` / graph edge.
- (c) **Diagnosis code.** E11.22 → bronze diagnosis → ICD hierarchy → closure (two parents: E11.2 and N18) → graph
  `subClassOf` → KED/SPD cohort.

**Life sciences:**
- (a) **Weight measurement.** A raw EDC weight in lb → SDTM VS in kg → the Week-24 endpoint → metric view → graph.
- (b) **Amendment.** The window change (±7 → ±14 days) → protocol PDF → rule registry → RAG / Page / graph.
- (c) **Medical-history term.** An MH term → MONDO code → closure → eligibility exclusion.

## 4. Benchmark

- **Simple agent.** The existing retrieval-eval agent and providers (`src/benchmark/retrieval_eval/`), extended
  where a mode needs a tool. One model, one system prompt. Each mode gets only its own retrieval tools:
  - **Metric views:** describe + one `MEASURE()` query.
  - **Closure:** resolve a code, ancestors/descendants, patients under a node.
  - **RAG:** top-k chunks.
  - **Genie Ontology:** the snippets and Pages that Genie Ontology retrieves for the question (retrieval only,
    not Genie One's answer).
  - **Graph:** typed path/pattern queries executed against the published triplestore. The graph computes; the
    agent only phrases the query.
- **Scoring.**
  - Gold answers come from an independent reference query per question (the answer key, not an arm).
  - Each cell is checked exactly (number, set or stated fact), run 3 times, then hand-verified.
  - Results are labelled answered / partial / not answered.
- **Questions: about 2 per approach's strength, ~10 per demo, real analyst questions.** HEDIS reuses
  `ground_truth.yaml` questions and gold queries where they fit. Each answer is confirmed
  to exist in the data before the question is locked. Draft HEDIS set:

  | # | Question | Should shine | Why the others fall short |
  |---|---|---|---|
  | 1 | GSD poor-control rate (A1c > 9%) for MY2025, by clinic | Metric views | Prebuilt measure; RAG has no data |
  | 2 | Share of diabetics 65–75 with A1c > 9% and no statin | Graph | Not a prebuilt measure, so metric views can't |
  | 3 | Patients with diabetes and any kidney complication | Closure | Subtree rollup; no metric view for it |
  | 4 | Which top-level conditions E11.22 rolls up to | Closure / graph | Multi-parent hierarchy |
  | 5 | Recommended A1c target for older adults with comorbidities | RAG | Stated only in the protocol document |
  | 6 | When to recheck A1c after intensifying therapy | RAG | Document rule (Step 3) |
  | 7 | What "KED compliant" means and which data reports it | Genie Ontology | Needs Page + metric view + comments together |
  | 8 | Which measures use eGFR, and where the eGFR value set is defined | Genie Ontology | Semantic context across assets |
  | 9 | Patients on a drug whose class is contraindicated by their own labs/conditions | Graph | Typed multi-hop |
  | 10 | Why patient X is in the SPD statin gap (the path) | Graph | Deterministic explanation |

  The life-sciences set follows the same pattern:
  - **Metric views:** Week-24 % change by arm.
  - **Graph:** the same measure restricted to BMI ≥ 35, which isn't prebuilt.
  - **Closure:** MONDO subtree rollups.
  - **RAG:** what Amendment 1 changed; the SAP baseline definition.
  - **Genie Ontology:** what the endpoint means and where it lives.
  - **Graph:** con-meds whose mechanism is prohibited; why participant X was excluded.
- **Genie One** gets the same questions through the scripted trace path, hand-verified. If it misses one, we show
  that.

## 5. What changes (HEDIS: small; nothing deleted)

- **App:** lead with **Trace** and **Benchmark**. The other tabs (drift lab, ontology explorer) stay, behind them.
- **Evaluation:** one harness, the retrieval eval, now with a Genie One column. The capability-map runs stay as
  history.
- **Arms:** A6 supervisor and `closed_book` stay in the code, but aren't shown as benchmark arms. DMVM stays
  retired.
- **Questions:** drop the trick ones (undefined-class refusal, vintage trick) from the benchmark.
- **Life sciences:**
  - Replace the named edge-case fixtures (FX-01..29) with a realistic generated population.
  - Map Ontobricks onto the real tables; flag the `clinical_study_graph` views and drop them only if you agree.

## 6. Manual steps (target)

- **Ontobricks:** import the ontology + mapping and publish, per demo and per mapping change.
- **Genie One:** inferred snippets build on the product's schedule (~daily). The recording itself is scripted.
- **Everything else is a bundle job or a committed script:** data, closures, metric views, comments, Pages,
  knowledge stores, the RAG index, grants, the benchmark.

## 7. Order

HEDIS first (most of it exists), then life sciences, with the same steps:
1. ✅ (2026-11-21) Fix the two HEDIS correctness bugs: value sets by measurement year (+ the lab's CKD-EPI 2021
   switch on 2022-07-01, so MY2026 KED keeps its eGFR results); Step 3 triggers on A1c > 9% (870 triggers, was 904).
   verify_gold 20/20.
2. Fact list + presence test.
3. The three traces.
4. Question set; verify each answer in the data.
5. One harness + the simple agent; run it.
6. Genie One run.
7. App: Trace + Benchmark tabs.

## Decisions (2026-11-21)

1. **HEDIS correctness:** apply value sets by measurement year: yes. Step 3 "> 9%": yes. Both done.
2. **The draft HEDIS questions:** keep as drafted.
