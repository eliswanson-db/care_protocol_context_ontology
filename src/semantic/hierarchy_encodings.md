# Hierarchy encodings — closure table + segment table

A **third, purely relational** way to encode hierarchy/semantics in the demo, alongside **Genie Ontology**
(inferred/modeled context an LLM uses to write SQL) and **Ontobricks** (OWL graph traversed via MCP). Three
encodings of the *same* clinical hierarchy, benchmarked head-to-head. SQL lives in `closure_tables.sql`.

## The point

"Select an entire subtree at any depth" should be **one equality**, not a recursive walk. A closure table
pays the recursion **once, at write time**; every read is a filter. A segment table captures the sets that
**cut across** the tree and that no subtree equals.

| Encoding | Shape | Subtree select | Verdict |
|---|---|---|---|
| Flattened (level columns) | one row, `lvl1..lvlN` | fixed-depth only | ✗ breaks at unbounded depth |
| Adjacency list (`parent_id`) | one row per node | **recursive CTE** | ✗ query shape changes every question; easy to get wrong |
| Materialized path | path string | `LIKE 'x/%'` | ~ workable, string-fragile |
| Nested set (`lft/rgt`) | interval per node | range predicate | ~ workable, costly to rebalance |
| **Closure table** | ancestor→descendant→depth | `WHERE ancestor = X` | ✅ one equality, any depth |
| **Closure + segments** | + named cross-branch sets | equality **or** segment id | ✅ also answers cross-branch |

The two in **bold** are where we land; the other four are shown in the app exhibit for contrast.

## In our domain (ICD-10-CM / HEDIS — ADR-0002)

- **`icd10_closure(ancestor_code, descendant_code, depth, …names)`** over the ICD-10-CM tree.
  "All diabetes" = `WHERE ancestor_code IN ('E10','E11','E13')` — **automatically includes `E11.21`**
  (T2DM with diabetic nephropathy), which is the **T3 subsumption tracer**. A flat code list misses it; a
  recursive CTE over the adjacency list is what a model writes wrong.
- **`value_set_segment(segment_id, segment_name, code, code_system, measurement_year, owner, …)`** — the
  HEDIS **value set / cohort**: a curated set spanning ICD-10 branches (+ LOINC/RxNorm), i.e. exactly the
  "rules that ignore the tree." Every segment carries a **named owner** (value-set governance).
- Optional **`loinc_part_closure`** over the LOINC Part hierarchy for the lab-concept side.

## Two questions, written both ways (demo exhibits)

1. **"Diabetes denominator count"** — *adjacency* needs a recursive CTE whose shape changes per question;
   *closure* is one equality that catches every depth (incl. `E11.21`). Same answer, stable shape.
2. **Cross-branch cohort** (the "Strategic Assortment" analog) — a curated diabetes value set that spans
   branches and includes/excludes specific codes. **Only the segment table** answers it; no subtree equals it.

See `closure_tables.sql` for the exact adjacency-vs-closure-vs-segment queries.

## How it differs from the other two differentiators

| | Where the relationship lives | How a question is answered | Strength |
|---|---|---|---|
| Genie Ontology | inferred + modeled UC context | LLM writes SQL (may write a wrong recursive CTE) | zero-code for the user; quality = context quality |
| **Closure + segments** | **a Delta table, written once** | **one equality join** | deterministic, cheap at read, governable |
| Ontobricks | OWL graph | MCP graph traversal | formal semantics, multi-hop |

The field result to reproduce (from the Genie-One source material): on a 7-question hierarchy benchmark the
**closure** encoding answered 5/7 at the lowest SQL complexity; **adjacency** answered 2/7 and produced *no*
correct recursive CTE; adding the **segment** table resolved the cross-branch question every encoding missed.
Crucially, Genie reached parity with the graph **after a closure view + metadata were added** — so the
closure table is also the **"Genie + closure view"** benchmark arm, not just a standalone encoding. Read it
as *query shape*, not throughput (small dataset).

## Costs (price these explicitly)

- Closure grows with **depth × node count** (one row per ancestor–descendant pair) and must be **rebuilt or
  incrementally maintained** whenever the hierarchy is restructured — ties into the measure-drift demo
  (rebuild on code-set / measurement-year change).
- Each **segment** needs a **named owner** and effective dates.

## Where this plugs into the build (see ADR-0006)

- **P2** build `icd10_closure`, `loinc_part_closure`, `value_set_segment` (recursive CTE at build time).
- **P4** register as governed UC tables/views with comments + synonyms (feeds Genie → the "Genie + closure view" arm).
- **P12** add **closure** as a benchmark encoding and the **adjacency-vs-closure** head-to-head; wire the
  "Genie + closure view" ablation point.
- **P13** a **"Hierarchy Encodings"** app exhibit: the six patterns + the paired queries + which answered correctly.
- **T3 tracer** resolved by one closure equality.
