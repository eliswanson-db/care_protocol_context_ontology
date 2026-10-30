# Benchmark Charter — context layers & retrieval approaches

> Supersedes the trivial first-cut benchmark (single-KPI questions, latency headline). This is the plan of
> record for a *serious* evaluation. See ADR-0004 (evaluation scope) and ADR-0010 (this charter).

## The question we're actually answering

**Not** "which arm wins." The deliverable is a **capability map**: *for each kind of clinical question, which
context/retrieval approach is sufficient, which adds unique value, and which is genuinely necessary* — and
**why the context had to be shaped that way**. Concretely:

- When does a **metric view** alone suffice?
- When does **semantic RAG** (Lakebase) suffice, and when does it fail?
- When does **Genie Ontology** (curated Pages + comments + metric views) add something RAG can't?
- When does a **closure table** equal a **graph traversal**, and when do you truly need a **graph** (Ontobricks)?
- Where does **Genie One** orchestrating these as components beat any single component?

Accuracy on realistic hard questions is the **primary** metric. Latency/cost is **secondary** (a fair Pareto
axis once accuracy is comparable). The spine of the whole thing is **lineage**: follow information from a
bronze patient → the care-protocol PDF + encounters + prescriptions → the retrieved context → the agent's
answer, and be able to say exactly which artifact supplied which fact.

## Ground truth (no oracle)

There is **no single oracle**. A closure table is *not* always right — it precomputes **one** relation (is-a),
so it answers is-a rollups but cannot do typed multi-edge traversal, variable-length mixed paths, inference,
or qualifier-constrained traversal. It is a **competing arm**, not the answer key. Each benchmark question
ships with a **hand-verified expected answer**, constructed by whatever method is correct *for that question*
and cross-checked — independent of any arm. No pre-wired per-question answers in any arm; **every arm must
reason** (choose/compose tools, retrieve, generate), including the governed-tool arm.

## The data & lineage spine

- **Scale:** 25,000 synthetic patients (Synthea) — removes scale as an objection; thousands of diabetics and
  real signal in rare complication subtrees. Measurement year 2025.
- **Unstructured anchor:** a synthetic **care-protocol PDF** (diabetes care guidance: eligibility, measure
  thresholds, recommended drug classes, monitoring cadence, contraindications). Parsed with
  `ai_parse_document`, linked to patients. It feeds RAG, Pages, and graph edges at once, and is the lineage
  anchor.
- **Lineage thread (the demo):** `bronze_patient` → diagnoses/labs/meds (encounters) → crosswalked codes →
  cohort (ICD closure) → measure result + evidence → care-protocol guidance (PDF) → retrieved context →
  agent answer. Every hop is inspectable.

## The knowledge graph (license-clean): LOINC + ICD-10 + RxNorm + protocol, linked

Each vocabulary is a graph of its own shape; the value is **linking them**.

| Vocab | Shape | Closure vs graph |
|---|---|---|
| **ICD-10-CM** | near-pure **is-a tree** | closure **== graph** (diagnosis rollups); no graph needed |
| **LOINC** | **multiaxial** (6 typed Part axes: Component/Property/Time/System/Scale/Method) | **graph > closure even within the vocab** (e.g. "any A1c regardless of method" via the Component Part). License-clean (LOINC license; NOT the SNOMED-dependent LOINC-SNOMED Ontology) |
| **RxNorm** | typed relations (ingredient/dose-form/brand) | ingredient→product is one relation (closure ok); other edges are graph |
| **Protocol/measure** | typed clinical edges (requires / monitored-by / recommends / has-threshold) | inherently multi-edge → graph |

**Unified graph** nodes = {ICD codes, LOINC terms+Parts, RxNorm ingredients+drugs, value sets, measures,
protocol concepts, patients}; edges = intra-vocab (is-a, has-component, has-ingredient) + inter-vocab/clinical
(measure requires LOINC; condition monitored-by lab; protocol recommends drug-class; cohort defined-by
ICD-subtree; value-set contains code). ICD stays available as a closure table *specifically to demonstrate*
closure==graph there.

## Arms = reasoning front door + pluggable context components

A common reasoning front door (**Genie One first**; also Genie Agent / a custom supervisor agent) with
components plugged in via MCP / Genie Ontology / retrieval. We measure the **marginal value of each
component**. As many components as possible are reachable by Genie One; the app visualizes the flow.

| Arm / component | What it contributes |
|---|---|
| **M0 Metric views only** | governed KPIs; baseline for "is a definition enough?" |
| **A2 Genie Agent** | curated space over structured measures + metric views |
| **A3 ablation** | same engine, add context in layers (raw tables → +comments/metric views → +Pages/ontology) |
| **A4 Lakebase hybrid RAG** | lexical + pgvector over the corpus incl. the care-protocol PDF |
| **A5 Ontobricks graph** | formal ontology + graph traversal / inference (Eli sets up; graph as above) |
| **A6 governed-MCP agent** | LLM reasons with governed tools (subsumption, value-set, measure, graph-query) — not pre-wired |
| **Genie One** | front door orchestrating the above components |

## Capability classes (realistic questions, no trivial traps)

Each class has hand-verified ground truth. "Sufficient / adds value / necessary" per approach is the output.

1. **Simple KPI** — "What's the GSD rate?" → metric view **sufficient**; everything else overkill. (control)
2. **Single-relation subsumption (ICD)** — "patients with any diabetic kidney disease" → closure **==** graph;
   RAG alone weak; metric view only if predefined. (shows closure suffices, graph unnecessary)
3. **Multiaxial lab identity (LOINC)** — "every A1c test regardless of method/specimen" → LOINC Part graph
   adds value over an enumerated value set (robust to new codes); RAG can't enumerate.
4. **Med subsumption (RxNorm)** — "patients on any statin" → ingredient→drug closure; naive enumeration misses.
5. **Value-set vintage** — "KED eGFR coverage under the 2026 spec" → versioned value sets; RAG on current docs
   gives a stale/ambiguous answer.
6. **Cross-domain protocol multi-hop** — "statin gap with no contraindication", "cardiorenal on 3 drug
   classes" → **fixed-shape multi-joins** over the closure/edge tables + `protocol_edges`; **closure_sql
   suffices**, graph is more natural/maintainable but NOT strictly necessary. (correction to an earlier
   overclaim — see below)
7. **Definition / provenance** — "what does 'controlled' mean for BPD and where is it defined?" → RAG over the
   PDF; Genie Ontology **Page adds the citation/provenance**; structured-only can't explain.
8. **Graph-native** — path/explanation queries ("the rationale connecting this patient's diabetes to their
   statin") and **OWL-defined classes** (reasoner-classified). Variable-shape / inference → **the genuine
   Ontobricks-necessary case**, and it ties to the lineage/explainability thread.

### Where semantic resolution happens (the real variable) + honest correction
The same answer can be produced by doing the terminology work at a different stage, and that — not "rival
engines" — is what the arms vary:
- **build-time** (baked into a metric view / Gold) → **Genie Ontology** answers from the semantic layer;
- **query-time** (join a materialized closure/edge table) → the **closure_sql** approach (Genie SQL or MCP);
- **live traversal / inference** (Ontobricks) → classes that are variable-shape or inference-based (class 8);
- **text** → RAG.
Correction: classes 2–6 are all expressible as fixed-shape SQL over materialized closure/edge tables, so
**none strictly require Ontobricks** over a good closure layer. Ontobricks earns its place on **class 8**.
Full per-question mapping (how each is asked, min approach, graph-strictly-needed) is in
`docs/benchmark/ground_truth.yaml`.

## Metrics

- **Primary — answer accuracy** vs. hand-verified ground truth (result-set / value correctness), per class.
- **Lineage completeness** — can we trace every answer to its source artifacts (codes, Page, PDF span, SQL,
  graph path)? First-class, captured per answer.
- **Secondary — latency & cost** — recorded per arm; shown as a Pareto view, not a headline.

## Deliverables

- The **capability-map matrix** (class × approach → sufficient/adds-value/necessary) backed by MLflow runs.
- The **lineage visualization** in the app + Databricks UI (one patient/question traced end-to-end).
- An honest write-up of *when each Databricks capability earns its place* (metric views, Genie Ontology,
  Lakebase RAG, Ontobricks graph, closure tables).

## Open / in-progress
- A5 Ontobricks graph construction is Eli-owned (ADR-0005); this charter defines the graph it should expose.
- Ground-truth set authoring (classes 1–7) is the next build after the 25k data + PDF + graph land.
