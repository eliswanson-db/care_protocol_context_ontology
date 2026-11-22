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

- One short **fact list** per demo (~25 facts; HEDIS: `docs/benchmark/hedis_facts.yaml`, checked by
  `tests/test_hedis_facts.py`). These are the facts the questions
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

### 4a. Step 4 plan: lock the HEDIS questions (drafted 2026-11-22)

Each question gets: final wording, answer type, a gold query in `src/benchmark/gold_queries.sql` (the answer key,
`verify_gold.py` gate), an entry in `docs/benchmark/ground_truth.yaml`, its facts (`hedis_facts.yaml`), and a
one-line honest expectation per approach. Nothing is locked until the gold query runs on ECT and the answer is
checked by hand.

Every question names a fixed date or period; no "current", "recent", "this year" or unanchored "latest" (the gold
answer must not depend on when it is asked). Anchor: MY2026 data runs through **2026-10-30** (the extract horizon).
The gold SQL filters on the same dates explicitly (e.g. `result_ts <= '2026-10-30'`), so a longer extract can't move it.

| # | Question (proposed wording) | Answer type | Gold | Live check (2026-11-22) |
|---|---|---|---|---|
| 1 | What was the GSD poor-control rate (last A1c of MY2026 above 9%) by clinic, for MY2026 through 2026-10-30? | 8 (clinic, rate) pairs | new (metric view) | values exist (e.g. CLINIC-03 11.3%) |
| 2 | Of GSD-eligible diabetics aged 65–75 in MY2026, how many had a last MY2026 A1c (through 2026-10-30) above 9% and no statin dispensed in MY2026? | count + share | new | 73 of 821 (93 above 9%) |
| 3 | How many patients have diabetes with a kidney complication (any diagnosis on or before 2026-10-30)? | count | `sub_kidney` | 1,881 |
| 4 | Which top-level conditions does E11.22 roll up to, and through which parents? | set of routes | `graph_multiparent_routes` | E11.22 > E11.2 > E11, E11.22 > N18 |
| 5 | What A1c target does the care protocol (v2025.1) recommend for an older adult with moderate comorbidity? | stated fact | doc (corpus) | 7.0–8.0% (5–10 yr life expectancy) |
| 6 | Under the care protocol (v2025.1), after an A1c above 9%, when must A1c be rechecked? | stated fact | doc + metric view | within 90 days (3 months) |
| 7 | What does "KED compliant" mean for MY2026, and which governed view reports it? | stated facts | Page + metric view | eGFR AND uACR in MY2026, 18–85; `ked_compliance_metrics` |
| 8 | Which measures use eGFR, which LOINC codes count in MY2026, and where is that defined? | stated facts | value_set_segment | KED; 98979-8 only; `value_set_segment` KED_EGFR |
| 9 | On 2026-10-30, which patients had an active order for a drug the protocol contraindicates for a condition active on that date, or for their last lab result on or before it? | patient set + reasons | new (replaces `graph_statin_contra_cohort`) | see decision 1 |
| 10 | Why was patient X in the SPD statin gap for MY2026 (through 2026-10-30)? (the path) | path | new (per patient) | hero picked by rule |

**Decided (2026-11-22)**

1. **Showcase questions are fair; trick questions are not.** A question built to show one approach's specific value
   (Genie Ontology's inferred snippets or the semantic value of its Pages; a graph multi-hop that needs a reasoning
   engine a single-shot context doesn't have) belongs in the set. A trick is a question that fails an approach on a
   wording or data artifact, e.g. "MY2026 eGFR = 0 patients" from a code the data never used, or a refusal test.
2. **Few questions, the most useful.** Proposed set of 8 below.
3. **Dates.** Conditions carry `stop_date` (Synthea `STOP`, in `bronze_pat_enc_dx` / `silver_condition` since
   2026-11-22); orders already carry start/stop. "Active on 2026-10-30" = started on or before it and not stopped
   before it. `graph_statin_contra_cohort` (198) and `proto_statin_gap_safe` are rewritten this way and re-verified.
4. **Statin = the governed SPD definition:** dispensed in MY2026, resolved through `rxnorm_closure`.
5. **Runs.** Test mode (default) = 1 run per cell; `--final` = 3, only for final demo testing.
6. **Fixed dates** in every question and gold query (above).
7. **Reword** `op_worst_clinic_annual`, `op_clinic_drift`, `op_drift_rootcause` to fixed dates.

**Proposed set (8): two per approach where it matters, graph only where it really stands out**

| # | Showcases | Question | Why this one |
|---|---|---|---|
| 1 | Metric views | q1 GSD poor-control rate by clinic, MY2026 through 2026-10-30 | the prebuilt, governed measure: exact and fast |
| 2 | Metric views' limit | q2 diabetics 65–75 with A1c > 9% and no statin (SPD rule) | crosses two measures; no prebuilt view answers it |
| 3 | Closure tables | q3 diabetes with a kidney complication | subtree rollup in one equality join |
| 4 | RAG | q5 A1c target for an older adult with moderate comorbidity | stated only in a protocol document |
| 5 | Genie Ontology | q8 which measures use eGFR, which codes count in MY2026, where defined | Page + value-set table + metric view together |
| 6 | Genie Ontology | is the GSD poor-control rate over all eligible patients or only those tested? | semantic-layer knowledge (metric view comment, knowledge store) that no document states |
| 7 | Graph | q9 patients on a drug contraindicated by a condition active on 2026-10-30 or their last lab | drug class × rule × lab or condition, with dates: needs a reasoning engine |
| 8 | Graph | q10 why patient X was in the SPD statin gap (the path) | a per-patient explanation found by traversal |

Dropped from the draft: q4 (E11.22 routes; trace 2 shows it), q6 (Step 3 recheck; trace 1 shows it, and it overlaps
q5), q7 (KED definition; overlaps q8).

**Dependencies (known, not blockers for locking)**
- The graph can't answer q2, q9 or q10 fully until the republish (items 1, 3, 3b, 4). Until then its cell shows not
  answered, with the reason, rather than being dropped.
- The Genie Ontology provider replays recorded Genie One retrievals, so the new questions need one scripted
  recording run (`scripts/record_genie_ontology.py`).

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
2. ✅ (2026-11-21, HEDIS) Fact list + presence test: 25 facts, every pointer resolves (live too). Open: 6 graph
   gaps that need the Ontobricks project (listed by the test).
3. ✅ (2026-11-22, HEDIS) The three traces, in the Tracer Journey tab (`server/traces.py`; heroes picked from the data
   by rule): an A1c result (11.0% → GSD poor control → missed Step 3), E11.22 (two parents → diabetes + CKD value
   sets → SGLT2), metformin at eGFR < 30 (CP-GLY-2 → a patient on metformin at eGFR 19.4). Every stage is live. The
   graph stops short where the republish list says (F22, F23, F26).
4. Question set; verify each answer in the data.
5. One harness + the simple agent; run it.
6. Genie One run.
7. App: Trace + Benchmark tabs.

## Decisions (2026-11-21)

1. **HEDIS correctness:** apply value sets by measurement year: yes. Step 3 "> 9%": yes. Both done.
2. **The draft HEDIS questions:** keep as drafted.
