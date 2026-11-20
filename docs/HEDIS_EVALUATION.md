# HEDIS lab: critical evaluation (2026-11-20)

What the HEDIS demo set out to do, what it does, what it actually proved, and what it costs. Written before
continuing the life-sciences lab, which was meant to repeat this pattern. Sources: `docs/STORY_ALIGNMENT.md`,
`docs/BENCHMARK_CHARTER.md`, `docs/benchmark/{capability_map,GRAPH_EVAL_RESULTS,CONTEXT_CONSISTENCY_AUDIT}.md`,
`docs/benchmark/a1_runs/FINDINGS.md`, `docs/benchmark/retrieval_eval_arena*.json`, the ADR log.

## 1. What we were trying to accomplish

1. **The business story.** "A Monday with Genie": diabetes protocols drift quietly. Genie, over one governed
   context layer (Genie Ontology = learned + modeled, plus certified metric views), notices a protocol step
   slipping. It explains the root cause (a PCP handoff), sizes the Star impact, and proposes a fix.
2. **Explain the context options.** Show how Genie Ontology works, and how the other semantic/graph options a
   customer can build on Databricks compare: metric views, closure tables, RAG (Lakebase), Ontobricks.
3. **Trace journeys.** Follow a hero patient through raw → bronze → silver → gold → semantic layer →
   retrieval layer, clearly and simply.
4. **A capability map.** For each kind of question, which approach is sufficient, adds value, or is necessary.
   It's a map, not a leaderboard.

## 2. What it does (the build)

| Layer | What exists |
|---|---|
| Data | Synthea 25k patients → Clarity-shaped bronze → silver → gold for 7 measures (GSD, KED, BPD, SPD, EED, MAD, SSD) plus Step-3 protocol adherence. A seeded care-behavior model produces the drift (CLINIC-08 drops from 78% to 47% mid-Q3) without wiring an answer. |
| Terminology | Vendored ICD-10, LOINC (+Parts), RxNorm subsets; closure tables; `protocol_edges` (22 guideline edges). |
| Semantic layer | 8 metric views, column comments, 17 managed Pages (Pages API), 4 Genie spaces with repo-managed knowledge stores. |
| Retrieval approaches | Genie One / Genie Ontology, metric views, closure SQL, Lakebase hybrid RAG with document-level RLS, Ontobricks OWL graph (Eli-built, ~55M triples), an MCP tool supervisor (A6). |
| Evaluation | Two harnesses: the capability map (Genie One headless, hand-verified, 20 questions) and the retrieval eval (one fixed agent × 7 context providers, LLM-judged tiers). |
| App | Tabs: quality, tracer journey, retrieval arena, benchmark scorecard, drift lab, ontology explorer. Plus the protocol-watch job. |
| Size | About 26k lines of code and 10k lines of docs, 27 ADRs and 124 commits in about 3 weeks. |

## 3. What we actually accomplished

### The story: mostly yes, for the core beat

- **Done and real:** Step-3 drift is emergent and detectable. The watch job fires HIGH on CLINIC-08. Genie One
  found the drift, which is masked in the annual ranking, and named the PCP handoff as root cause (capability
  map, class 9). MAD has a continuous PDC distribution.
- **Not built:** plan-side claims and enrollment, row-filtered Pages, guideline-diff decision support,
  close-the-loop, and a live notification. The watch schedule is paused. Those are the later beats that sell
  the story.
- **Correctness gaps a customer could catch** (open decisions, `CONTEXT_CONSISTENCY_AUDIT.md`):
  - Measures ignore value-set versions: MY2026 KED still counts MDRD 33914-3, though the value set, payer memo
    and drift Page all say it was dropped.
  - The Step-3 trigger is "≥ 9.0" in the code and metric view, but "> 9%" in the protocol document and the
    graph. 35 of 904 triggers sit exactly at 9.0.

### Explaining Genie Ontology: not achieved

- **The on/off comparison showed nothing.** ECT (~200 snippets) vs DMVM (~1,100) gave identical accuracy
  (16/20 each). The two arms differed on 2 questions, which flipped between runs. The comparison was retired
  (ADR-0021).
- **The questions can't separate the layers.** All 20 are answerable from the modeled layer (metric views +
  Pages), so they can't isolate what inferred snippets add. `FINDINGS.md` says so itself.
- **Where inferred snippets come from.** They are mined mostly from Genie-space knowledge stores (36/50 from
  two unmanaged dev spaces) and query history, not from Pages. In practice "Genie Ontology" here means curated
  assets. We now seed those stores ourselves (ADR-0027), so any lift we later observe is the curation, not
  something the product learned.

### The capability map: real findings, weak instrument

**What holds:**
1. Metric views answer definitions and KPIs, not discovery.
2. Genie One is strong on a well-modeled domain (16/19 scorable, hand-verified). It misses exact multi-hop
   counts, because the exact value sets and windows live only in governed tables.
3. A graph used as LLM context gives typed cross-vocabulary edges (definitions, a patient's rationale path). It
   can't aggregate.

**What doesn't hold up:**
- **Circularity.** `closure_sql` is both an arm and the answer key (`gold_queries.sql`). It "reaches gold by
  construction" on classes 1–6, so that column proves nothing.
- **The two harnesses disagree.** In the capability map, closure SQL is "the robust spine for classes 2–6." In
  the retrieval eval (15 questions, run 2026-11-05) it reaches tier 1 on 1 of 15. The app's 6-question arena
  is similar:

  | Arena (6 questions) | Tier 1 | Tier 2 | Tier 3 (miss) |
  |---|---|---|---|
  | closure_sql | 1 | 0 | 5 |
  | genie_ontology | 2 | 0 | 4 |
  | metric_view | 2 | 1 | 3 |
  | ontobricks | 0 | 2 | 4 |
  | rag | 1 | 0 | 5 |

  `graph_multiparent_routes` is missed by every arm, including the graph. The difference is how each arm is
  driven, not what it knows. So the app's headline depends on which harness you look at.
- **Noise.**
  - Both retrieval-eval runs used `repeats=1`. The harness docstring says the default is 3, but the argument actually defaults to 1. The judge is an LLM, and
    several cells are flagged unstable.
  - The 6-question app arena is too small to support a claim.
  - Conclusions have already reversed once. "Graph-necessary for class 8" was claimed on 11/03 and withdrawn on
    11/04, after a Genie One re-run answered it.
- **Arms of different kinds in one table.** RAG and the graph are retrieved context. Closure SQL and metric
  views are query engines. Genie One is an orchestrator, replayed from recordings. The fairness caveat
  ("graph-as-context can't aggregate, not the graph can't count") is real, but it is buried in a doc.

### Ontobricks: works, lags behind

- **What works:** the graph is mapped onto the real tables, with a few inline `rr:sqlQuery` filters for the
  generic edge table. That's the product doing what it's for.
- **The lag:** v3 is behind the closure tables. It lacks the drug-class edges and labels on edge nodes, and
  MAD, SSD and Step 3 aren't mapped. Today's republish was as-is: REQUIRED 12/12, OPTIONAL 0/9.

### Parity (same facts in every approach): partly

The audit found the approaches hold different facts:
- Graph: 20/22 protocol edges, 3/16 drug-class memberships.
- RAG: no reference entries, no MAD.
- Pages: covered 10/22 edges before the fix.

Some of these are fixed. The rest need a republish or Lakebase writes.

## 4. Pros of the HEDIS approach

- **A real data story.** The drift is emergent, the generators are deterministic, and a gold regression gate
  catches any change that moves a number. Nothing is wired to an answer.
- **Databricks-native surfaces, as a customer would build them:** metric views, the Pages API, Genie spaces
  with knowledge stores, UC governance, Lakebase RLS, Apps, bundles.
- **Ontobricks used the intended way:** mapped onto real tables, with filtering queries only where the source
  is a generic edge table.
- **An honest posture.** Hand-verified answers, published corrections (class 6 and 8 claims withdrawn), and
  caveats written down rather than hidden.
- **The context layer is content-as-code** (Pages, knowledge stores, comments). It is reproducible and can be
  reviewed.
- **License-clean terminology** that is vendored and pinned.

## 5. Cons of the HEDIS approach

1. **Scope sprawl buried the story.** `STORY_ALIGNMENT.md` warned "don't let [the benchmark] become the demo's
   spine," and it did. Seven arms, two harnesses, two workspaces (one retired), a tool supervisor and a
   per-fact parity regime all compete with the story beats that aren't built yet.
2. **The headline question is still open.** "What does Genie Ontology add?" was the reason for the on/off
   design. It produced no difference and was retired without a replacement test.
3. **The benchmark can't carry the claims made from it.** It is circular, its two harnesses conflict, it ran
   once per cell, it has 6–20 questions, and its arms differ in kind. It is fine as illustrations. It is not
   evidence.
4. **Consistency costs more than it pays.** Keeping five representations of the same facts in sync (graph,
   RAG, Pages, closures, metric views) is a standing tax. The audit still found gaps, and every fix needs
   manual steps (Ontobricks republish, Lakebase writes, Page duplicates).
5. **Fragile operations.** Ontobricks and grants are manual (grants were lost when a catalog was recreated).
   Pages collide on duplicate titles. Inferred-snippet extraction happens on the product's schedule, not
   ours. Every redeploy has ⚙/⏳ steps.
6. **Open data-correctness questions** (value-set versioning; ≥ vs >) undercut a demo whose argument is
   governed exactness.
7. **Complexity beyond what an audience sees.** About 10k lines of app code for six tabs. Much of the eval
   machinery isn't visible in the demo at all.

## 6. Implications for the life-sciences lab (for discussion)

The LS lab copied HEDIS's ambitions (five approaches, parity, an eval) and then added machinery HEDIS doesn't
have (a single-spec generator and ~100 graph views). The cons above apply to it with more force. Before
building further, decide:

1. **What is the one story beat for LS?** Candidate: an amendment changes the endpoint, the governed context
   shows which participants' results change and why, with citations.
2. **Which comparisons are worth showing?** Show a few crisp, hand-verified contrasts, not a scored matrix.
3. **Copy the HEDIS pattern exactly** where it works: Ontobricks over real tables, Pages and knowledge stores as
   code, metric views. Don't copy the parts that don't pay: two harnesses, per-fact parity across every
   approach.
4. **For HEDIS itself:**
   - Settle the two correctness decisions.
   - Pick one evaluation frame for the app and label it honestly.
   - Decide whether "what Genie Ontology adds" stays a headline claim, given that we can't currently show it.
