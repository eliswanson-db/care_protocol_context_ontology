# Capability map — which context approach earns its place, and why

The deliverable of the serious benchmark (ADR-0010, `BENCHMARK_CHARTER.md`): for each class of hard clinical
question, **which context/retrieval approach reaches the hand-verified answer, and how**. Not a leaderboard.

- **Data:** 25k synthetic patients, measurement year 2025, on the `ect` target after the generative
  care-behavior regen (ADR-0012). Gold values pinned in `ground_truth.yaml` and `gold_queries.sql`, verified
  by `verify_gold.py` (13/13).
- **Arms run (2026-10-30):**
  - **M0 — metric views only:** the governed semantic layer alone. Structural baseline for "is a definition
    enough?" (derived from whether a metric view yields the answer directly).
  - **closure_sql:** fixed-shape SQL over the materialized closure/edge tables (`icd10_closure`,
    `loinc_parts`, `rxnorm_closure`, `value_set_segment`, `protocol_edges`). This arm *is* `gold_queries.sql`,
    so for classes 1–6 it reaches gold by construction (it's the answer key).
  - **A1 — Genie One:** the front door, driven headless via `databricks genie ask`. Reasons over the
    workspace; nothing wired to an answer. Run captured in `/tmp/capmap/A1_detail.json` (answers + cited assets).
- **Arms pending:** A4 Lakebase hybrid RAG; A5 Ontobricks graph as a *scored* arm (notably, Genie One already
  reaches the Ontobricks `patientcare2` ontology + graph — see class 8).
- Verdicts below are **hand-verified** (the charter requires it); the auto-scorer in `run_capability_map.py`
  is a first-pass aid. ✓ = reached gold · ✗ = did not · ◐ = reasoned but diverged on definition · n/a = not
  applicable · *refusal* = correct "cannot answer".

## The matrix

| # | Question (id) | gold (25k) | M0 | closure_sql | A1 Genie One |
|---|---|---|---|---|---|
| 1 | GSD rate (`kpi_gsd_rate`) | 0.8071 | ✓ | ✓ | ✓ 80.7%, cited GSD metric view + Page |
| 1 | KED eligible (`kpi_ked_eligible`) | 2808 | ✓ | ✓ | ✓ |
| 2 | Diabetic kidney cx (`sub_kidney`) | 1881 | ✗ | ✓ | ✓ via `icd10_closure` |
| 2 | Any retinopathy (`sub_retinopathy`) | 393 | ✗ | ✓ | ✓ |
| 3 | A1c any method (`lab_a1c_any_method`) | 9709 | ✗ | ✓ | ✓ via `loinc_parts` Component |
| 3 | eGFR codes (`lab_egfr_codes`) | 33914-3, 98979-8 | ◐ | ✓ | ✓ |
| 4 | Diabetics on any statin (`med_on_statin`) | 1651 | ◐ | ✓ | ✓ 1,651 via RxNorm closure |
| 4 | Is 312961 a statin (`med_is_statin`) | yes | ✗ | ✓ | ✓ "Yes… under the statin class" |
| 5 | eGFR under 2026 set (`vintage_egfr_2026`) | 0 | ✓ | ✓ | ✓ (0; MDRD dropped in 2026) |
| 6 | Statin gap, safe (`proto_statin_gap_safe`) | 1609 | ✗ | ✓ | ◐ 1,769 — under-excluded contraindications |
| 6 | Albuminuria off ACE/ARB (`proto_albuminuria_aceiarb`) | 131 | ✗ | ✓ | ◐ 69 — latest-vs-any uACR, 2025-only |
| 6 | Cardiorenal cohort (`proto_cardiorenal`) | 10 | ✗ | ✓ | ✓ 10 (cross-branch) |
| 7 | Metformin eGFR floor (`def_metformin_egfr`) | eGFR < 30 | ✗ | n/a | ✓ cited the protocol doc |
| 7 | Controlled BP (`def_controlled_bp`) | <140/<90 | ✓* | n/a | ✓ |
| 8 | Rationale path (`infer_rationale_path`) | a path | ✗ | ✗ | ✗ timed out (>240s) |
| 8 | Defined class (`infer_defined_class`) | undefined | ✗ | ◐ | *refusal* — correctly found it undefined (checked `patientcare2`) |
| 9 | Worst clinic annually (`op_worst_clinic_annual`) | CLINIC-01 (0.475) | ✓ | ✓ | ✓ |
| 9 | Which clinic DRIFTED (`op_clinic_drift`) | CLINIC-08 (0.467 vs 0.778) | ✗ | ✓ | ✓ found CLINIC-08 + delta |
| 9 | Why did it drift (`op_drift_rootcause`) | PCP handoff + confound | ✗ | ✓ | ✓ named the PCP transition + case-mix |
| 9 | MAD rate (`op_mad_rate`) | 0.4784 | ✓ | n/a | ✓ 47.84%, 834 eligible |

\* `def_controlled_bp` and the BPD metric-view comment both carry the threshold, so M0 reaches it.

## Findings (the "when does each layer earn its place" write-up)

1. **Metric views (M0) answer definitions, not discovery.** Sufficient for KPIs (class 1), baked measures,
   versioned value sets (class 5), and the BP threshold — but structurally unable to express subsumption
   (2), multiaxial identity (3), or multi-hop (6). Exactly the "is a definition enough?" baseline.

2. **closure_sql is the robust spine for classes 2–6.** Fixed-shape SQL over the materialized closure/edge
   tables reaches every one exactly, because the semantic work (is-a rollups, LOINC Component, RxNorm class,
   versioned value sets, contraindication sets) is pre-materialized and governed. It is the answer key.

3. **Genie One (A1) is remarkably strong and reached gold on 16/19 scorable questions** — including the two
   signals this demo was built for: it **found CLINIC-08's drift** (masked in the annual ranking, where it is
   only 3rd-lowest) and **named the mid-year PCP handoff as the root cause**, with the case-mix confound. It
   resolved ICD subsumption, LOINC multiaxial identity, the value-set vintage drift, and the protocol
   definitions, each citing governed assets (metric views, Pages, the protocol doc).

4. **Where A1 diverged is the precise argument for the governed layer (◐, class 6).** On the two hardest
   multi-hop gaps it *reasoned soundly but to a different number* — it under-excluded contraindications
   (1,769 vs 1,609) and chose latest-vs-any / single-year uACR (69 vs 131). Neither is "wrong" in isolation;
   they differ because the **exact value sets and temporal windows live in the governed tables**
   (`value_set_segment`, `protocol_edges`). This is the capability-map point: for auditable, spec-faithful
   multi-hop answers, closure_sql (or a metric view baking the same sets) is *necessary* for exactness; A1
   approximates without them. It also argues for surfacing those value sets as governed context A1 can bind to.

5. **Class 8 is the genuine graph-native / Ontobricks case.** A1 **timed out** on the variable-shape rationale
   path and **correctly refused** the undefined OWL class (after consulting the `patientcare2` ontology). This
   is the charter's prediction: path/explanation + inference is where a formal graph is necessary — and Genie
   One already *reaches* the Ontobricks graph, so A5 plugs in as the arm that closes class 8.

## Reproduce

```bash
python src/benchmark/verify_gold.py --warehouse_id <WH> --profile ECT          # answer key / closure_sql (13/13)
python src/benchmark/run_capability_map.py --arm M0 --profile ECT              # structural baseline
python src/benchmark/run_capability_map.py --arm A1 --profile ECT --out /tmp/capmap  # Genie One, ~15 min
```

## Caveats

- A1 answers are an as-of snapshot (2026-10-30); Genie One reasoning is non-deterministic, so re-runs vary.
  The pinned gold and `verify_gold.py` are deterministic.
- The auto-scorer is a first-pass substring match (numeric/percent/comma + yes/no; pure-prose golds deferred
  to manual). Verdicts here are hand-verified against the captured answers.
- The ontology Pages bulk-import is still Eli-owned (RUNBOOK); A1 already cites some Pages and the Ontobricks
  graph, so this run is at least the "structured + comments + partial ontology" rung, not bare tables.
