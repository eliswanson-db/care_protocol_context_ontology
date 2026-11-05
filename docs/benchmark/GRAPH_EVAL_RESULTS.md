# Ontobricks graph arm — LIVE measured results (2026-11-03)

The Benchmark `graph` column was hypothesis-derived. This records the **live-measured** replacement: the
`ontobricks` provider (`src/benchmark/retrieval_eval/providers.py`) runs **entity-linked subgraph retrieval**
against the published `eswanson_demo.ontobricks.triplestore_clinicaldomain_v2_graph` (~55M triples) and feeds
the retrieved triples into the same fixed controlled supervisor (`agent.py`) + `is_correct` judge as every
other arm. Two passes: the 9-question 5-arm run (`retrieval_eval.json`) + the graph-only remainder
(`retrieval_eval_graph_remaining.json`).

## Measured graph verdicts (all 20 matrix questions)

| question | class | measured | note |
|---|---|---|---|
| kpi_gsd_rate | 1 KPI | n/a | no rate from a triple neighbourhood |
| kpi_ked_eligible | 1 KPI | n/a | — |
| sub_kidney | 2 ICD subsumption | **not_reached** | has the subClassOf edges, but a triple dump can't aggregate — agent mis-counted to 1 |
| sub_retinopathy | 2 ICD subsumption | **not_reached** | mis-counted to 2 (gold 393) |
| lab_a1c_any_method | 3 LOINC | **not_reached** | INSUFFICIENT CONTEXT (count) |
| lab_egfr_codes | 3 LOINC | **not_reached** | INSUFFICIENT CONTEXT (code enumeration not in the linked neighbourhood) |
| med_on_statin | 4 RxNorm | **not_reached** | INSUFFICIENT CONTEXT (count) |
| med_is_statin | 4 RxNorm | **reached** | correct "yes" — BUT sufficiency=no: the Simvastatin→RxNorm-code link came from the model, not the graph |
| vintage_egfr_2026 | 5 vintage | **not_reached** | graph carries no value-set vintage/temporal state |
| proto_statin_gap_safe | 6 multi-hop | **not_reached** | INSUFFICIENT CONTEXT (count + exclusions) |
| proto_albuminuria_aceiarb | 6 multi-hop | **not_reached** | surfaced the definitions but not the cohort count |
| proto_cardiorenal | 6 multi-hop | **not_reached** | INSUFFICIENT CONTEXT (multi-hop aggregate) |
| def_metformin_egfr | 7 definition | **reached** ✅ | `BIGUANIDE -[contraindicatedWhen]-> eGFR_LT_30` (grounded + sufficient) |
| def_controlled_bp | 7 definition | **reached** ✅ | `BPD -[hasThreshold]-> systolic_lt_140 / diastolic_lt_90` |
| infer_rationale_path | 8 graph-native | **reached** ✅ **graph-NECESSARY** | only arm to answer: E11 → eligible → SPD; `STATIN recommendedFor SPD` |
| infer_defined_class | 8 graph-native | **correct_refusal** | agent refused (correct — class undefined); automated `is_correct` scored the bare refusal a miss on phrasing |
| op_worst_clinic_annual | 9 operational | n/a | graph carries no operational/temporal rollups |
| op_clinic_drift | 9 operational | n/a | — |
| op_drift_rootcause | 9 operational | **not_reached** | no ops/temporal data linked |
| op_mad_rate | 9 operational | n/a | — |

**Rollup (measured):** reached 5 / applicable 15 (reached = 4 correctness + 1 correct_refusal), not_reached 10,
not_applicable 5. (Hypothesis column had claimed 15/15.)

## The finding (honest, demo-ready)

The graph's genuine lift **as an LLM-context source** is **typed, cross-vocabulary edges**: definitions
(`contraindicatedWhen`, `hasThreshold`), the multi-hop **rationale path** that no other arm could assemble, and
the **correct refusal** of a class the ontology doesn't define. It does **not** aggregate — counts, vintage,
and operational rollups are not something a retrieved triple neighbourhood can compute.

## ⚠ Methodology caveat (fairness — read before presenting)

This scores the graph **as a retrieval/context source** (retrieve triples → one fixed LLM reasons over them),
apples-to-apples with the **RAG** arm. It is **not** apples-to-apples with **`closure_sql`** on the COUNT
questions: `closure_sql` runs a hand-written aggregate SQL and injects the *scalar result* ("1881"), whereas
the graph arm injects *raw triples* and asks the LLM to count. The triplestore **contains** the membership
edges, so a graph **query** (a COUNT traversal / SPARQL aggregate) could produce the same scalar. So the honest
claim is **"graph-as-context can't aggregate,"** NOT "the graph can't count." A "graph-as-query" arm (give the
graph the same precomputed-aggregate privilege closure gets) would also reach the counts.

## Update 2026-11-04 (MY2026 re-record) — the class-8 claim is revised

The "graph-NECESSARY / only arm that reaches the rationale path" finding no longer holds. In the MY2026 Genie One
re-record (fresh sessions, `A1_off_ect_20261104.json` / `A1_on_dmvm_20261104.json`) both workspaces explained the
path correctly (diabetes → cohort → SPD eligibility → STATIN `recommendedFor` SPD), grounded in the SPD Page and, on
DMVM, the `protocol_edges` rule; the earlier run had timed out. The honest distinction now: the graph returns a
specific patient's path by **generic traversal** (Rx → ingredient → class → measure) with no path-specific SQL;
Genie explains the **general rule** from Pages + edge tables; closure SQL needs a hand-written join per path shape.
