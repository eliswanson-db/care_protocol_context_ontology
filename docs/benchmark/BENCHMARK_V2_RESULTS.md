# HEDIS benchmark v2: test-mode results (2026-11-22)

**Test mode: 1 run per cell, not hand-verified yet.** Final numbers come from `--final` (3 runs) after the known
issues below are settled. Questions, gold and predictions: `docs/benchmark/questions_v2.yaml`. Raw cells (context,
queries, judge rationales): `docs/benchmark/benchmark_v2.json`.

How a cell is scored: each approach retrieves with its own method. **1** = every expected fact is in what it
retrieved; **2** = not, but the agent made ONE query in the approach's native interface (SQL for metric views,
RAG and Genie Ontology; one closure-tool call; one graph-runner call) and the result has every fact; **3** = neither.

| Q | Question (short) | Metric views | Closure | RAG | Genie Ontology | Graph |
|---|---|---|---|---|---|---|
| 1 | GSD poor control by clinic | **2** | 3 | 3 | 3 † | 3 |
| 2 | 65–75, A1c > 9%, no statin | 3 | 3 | 3 | **2** | 3 |
| 3 | Diabetes with kidney complication | 3 | **1** | 3 | 3 | **2** ‡ |
| 4 | A1c target, moderate comorbidity | 3 | 3 | **1** | 3 § | 3 |
| 5 | eGFR measures, MY2026 codes, where defined | 3 (1 of 3) | 3 | 3 (2 of 3) | 3 (2 of 3) § | 3 |
| 6 | Contraindicated on 2026-10-30 | 3 | 3 | 3 | 3 | 3 ¶ |
| 7 | Why patient 00040be9 is an SPD gap | 3 | 3 | 3 | 3 † | 3 ¶ |
| 8 | Outside eye exam for patient 0b4f4745 | 3 | 3 | **1** | 3 | 3 |

## Predicted vs observed

Where the prediction held (as written before the run):

- **q1**: metric views answered with one `MEASURE()` query, exactly. RAG and closure can't.
- **q2**: no prebuilt view crosses GSD and SPD (metric views 3); Genie Ontology's context named both gold tables
  and their rules, and its one query returned 73.
- **q3**: closure tables answered in context (one equality join).
- **q4**: RAG answered from the glycemic-targets document.
- **q5**: RAG had the codes (payer memo) but not where the value set lives; metric views had only "KED uses eGFR".
- **q8**: only RAG answered, from the patient's outside letter, as the care-team role with the patient filter.
  Metric views and closure see only the EHR; nothing else holds per-patient correspondence.

Where it didn't, and why:

- **† Genie Ontology q1, q7: agent errors on top of good context.** q1: right table and rule, but it wrote
  `evidence_datetime > DATE'2026-10-30'` (drops results taken during 2026-10-30), so a few rates are off by about
  a point. q7: it used a `status` column gold no longer has. 5 of the 20 inferred snippets it retrieved for q7
  describe `status = 'NOT_MET'`, mined from an unmanaged dev dashboard ("[dev eli_swanson] HEDIS Diabetes Quality —
  Care Protocol (dev)"), the Clone dev Genie space (`docs/ontology/GENIE_SPACES_FLAGGED.md`) and query history from
  before gold dropped its verdict columns. A real finding about inferred context: it reflects everything in the
  workspace, including stale assets, which argues for deciding what to do with those assets.
- **§ Genie Ontology q4, q5: freshness.** The HbA1c and eGFR Pages gained these facts on 2026-11-21/22. Genie's
  Page index and snippet extraction run about daily, so the recording (today) predates them. Re-record after the
  daily extraction (`scripts/record_genie_ontology.py`) before reading anything into these two cells.
- **Closure q6, q7: the prediction was wrong.** It assumed hand-written joins. In this harness, closure tables are
  the reviewed tools (resolve a code, ancestors / descendants, patients under a node) with one call: deterministic,
  but no tool expresses "drug class × threshold × last lab on a date" or a per-patient explanation. Writing those
  joins is what a SQL-capable agent (Genie One, step 6) does with the closure tables.
- **¶ Graph q6, q7 (and q2): the published v3 graph stops short**, as the fact list says: no drug class for
  metformin (F22), no threshold-to-lab edge (F23), observation values on a different node (F26), no dates on
  diagnoses and orders (F28). Its traversals found the right structure (e.g. q7: patient → prescribed → statin
  class) but can't finish. These cells are expected to change after the republish (`ONTOBRICKS_REPUBLISH.md`
  2026-11-21 list); until then they stay 3, with the reason.
- **‡ Graph q3**: the number is right (1,881) but its pattern was narrower than the question (E11 under N18 only,
  undated), so the match may be a coincidence. Hand-verify before counting it.
- **Genie Ontology q6**: had the rules and tables but didn't write the query; as predicted, applying several rules
  needs multi-step querying.

## Before the final run

1. Re-record Genie Ontology after the daily extraction (fixes or confirms § cells).
2. Decide the unmanaged dev dashboard and dev/Clone Genie spaces (they feed stale schema into inferred snippets,
   † q7). Query history ages out on its own.
3. Ontobricks republish (items 1, 2, 3, 3b, 4, 5b).
4. Hand-verify every tier 1/2 cell (‡ q3 first), then `--final`.
