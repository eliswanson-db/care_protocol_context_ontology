# HEDIS benchmark v2: test-mode results (2026-11-22)

**Test mode: 1 run per cell.** Hand-verified: all of Genie One's column and every retrieval cell the judge scored as
answered (where the hand check disagrees, it wins; `hand_overrides` in questions_v2.yaml). The judge's misses are
not all hand-checked yet. Final numbers come from `--final` (3 runs) after the open items at the end. Questions, gold
and predictions: `docs/benchmark/questions_v2.yaml`. Raw cells (context, queries, judge rationales):
`docs/benchmark/benchmark_v2.json`.

How a cell is scored. **Retrieval approaches** (simple agent, plan step 5): each retrieves with its own method;
**1** = every expected fact is in what it retrieved; **2** = not, but the agent made ONE query in the approach's
native interface (SQL for metric views, RAG and Genie Ontology; one closure-tool call; one graph-runner call) and the
result has every fact; **3** = neither. **Genie One** (plan step 6): its own end-to-end answer, after as many queries
as it chose; ✓ = every fact, ✗ = not.

| Q | Question (short) | Metric views | Closure | RAG | Genie Ontology | Graph | **Genie One** |
|---|---|---|---|---|---|---|---|
| 1 | GSD poor control by clinic | **2** | 3 | 3 | 3 † | 3 | ✓ |
| 2 | 65–75, A1c > 9%, no statin | 3 | 3 | 3 | **2** | 3 | ✓ |
| 3 | Diabetes with kidney complication | 3 | **1** | 3 | 3 | 3 ‡ | ✓ |
| 4 | A1c target, moderate comorbidity | 3 | 3 | **1** | 3 § | 3 | ✗ § |
| 5 | eGFR measures, MY2026 codes, where defined | 3 (1 of 3) | 3 | 3 (2 of 3) | 3 (1 of 3) § | 3 | ✓ |
| 6 | Contraindicated on 2026-10-30 | 3 | 3 | 3 | 3 | 3 ¶ | ✓ |
| 7 | Why patient 00040be9 is an SPD gap | 3 | 3 | 3 | 3 † | 3 ¶ | ✗ (3 of 4) |
| 8 | Outside eye exam for patient 0b4f4745 | 3 | 3 | **1** | 3 | 3 | ✗ |

## The story the run tells (so far)

- **The simplest approach is often enough, but only for what it was built for.** Metric views answer the prebuilt
  measure exactly (q1) and nothing that crosses measures (q2). Closure tables answer the hierarchy rollup in context
  (q3) and none of the questions that need a join across rules and dates (q6, q7).
- **RAG wins where the information only exists in documents**: the protocol's individualized targets (q4) and a
  patient's outside eye-exam letter (q8, care-team role, patient filter). No other approach holds per-patient
  correspondence, and none should.
- **Genie Ontology gives the agent the right tables and rules** (q2: its one query returned 73), but a single query
  isn't enough for multi-rule questions (q6), and its inferred context carries stale schema (q7, †).
- **Genie One, as a reasoning engine, answers 5 of 8** (q1, q2, q3, q5, q6), including the multi-hop, dated
  contraindication question no single-shot approach answered. It misses where the answer lives in documents or
  per-patient letters it doesn't read (q4, q8), and on q7 it explains the gap but not the protocol rule behind it.
- **The graph** is held back by the published v3 (¶); its cells are expected to change after the republish.

## Notes per cell

- **† Genie Ontology q1, q7: agent errors on top of good context.** q1: right table and rule, but its SQL's date
  boundary drops results taken during 2026-10-30, so a few rates are off by a fraction of a point. q7: it used a
  `status` column gold no longer has. 5 of the 20 inferred snippets it retrieved describe `status = 'NOT_MET'`, mined
  from an unmanaged dev dashboard ("[dev eli_swanson] HEDIS Diabetes Quality — Care Protocol (dev)"), the Clone dev
  Genie space (`docs/ontology/GENIE_SPACES_FLAGGED.md`) and old query history. A real finding about inferred
  context: it reflects everything in the workspace, stale assets included.
- **§ q4, q5: freshness.** The HbA1c and eGFR Pages gained these facts on 2026-11-21/22; Genie's Page index and
  snippet extraction run about daily. Genie One said the protocol sets no age/comorbidity target (it searched the
  protocol-rules table; it doesn't read the documents, and the updated Page wasn't retrieved yet). Re-record after
  the daily extraction before reading anything into these.
- **Closure q6, q7: my prediction was wrong.** It assumed hand-written joins. Here, closure tables are reviewed
  tools with one call each; none expresses "drug class × threshold × last lab on a date" or a per-patient path.
  Writing those joins is what Genie One did on q6.
- **¶ Graph q6, q7 (and q2):** the published v3 stops at the documented gaps (no drug class for metformin F22,
  no threshold-to-lab edge F23, observation values on a different node F26, no dates F28).
- **‡ Graph q3: overridden to not answered by the hand check.** Its pattern asked for diagnoses under both N18
  and E11 (only E11.22), not under E11.2 / E10.2 / E13.2; it matched 1,881 only because every kidney-complication
  patient in this data carries E11.22.
- **Genie One q7 (3 of 4):** it explains eligibility, age and the missing 2026 fill, but calls the 2009 simvastatin
  order "dispensed" and never cites the protocol rule that makes a statin expected for SPD.
- **Genie One q8:** "no record". Expected: Genie doesn't read the RAG corpus, and the letters are care-team only.

## What step 6 surfaced, and what changed (all on ECT, gold 28/28)

Hand-verifying Genie One's misses found three problems on our side, all fixed:

1. **The recorder kept only the first 4,000 characters of Genie One's answer** (cut q1, q5, q6, q7 mid-table), and
   its subset mode silently reused old recordings. Fixed; those questions re-recorded.
2. **The judge isn't reliable on its own.** On the truncated q1 answer it claimed "matches all gold clinic rates"
   with only 4 of 8 in the text. Hand verification is binding; the judge is a first pass.
3. **The data, not Genie One, was wrong on q6**, three ways:
   - the gold read `bronze_order_med` (Synthea's open-ended orders); the measures read `care_order_med`, the
     effective layer of 30-day fills. Genie One used the effective layer. The gold does now.
   - `care_behavior` floored the number of 30-day fill cycles, so every patient's last metformin fill ended before
     2026-10-30 and almost no one held supply that day. Now the last fill runs its full 30 days (74% of 2026
     metformin patients hold supply on 2026-10-30). MAD clips coverage at the horizon, so it only loses the
     artificial end gap. Genie One then noticed every fill started on the same day ("a batch load"): all cycles
     began on 2026-01-01. Ongoing patients now start on their own day 0-29 of January (97 distinct last-fill dates).
     MAD rate 58.4% (860 eligible); MAD has no gold query, and its ground-truth note was stale.
   - Synthea sends two different results for the same patient, code and moment (2,989 eGFR moments in MY2026), so
     "last eGFR" depended on which row a query picked. Silver now keeps the lower value (decision 2026-11-22) and
     records `source_rows`; 36,758 conflicts collapsed. The gold also took the last result per LOINC code, so a stale
     MDRD value could count; it now takes the last result per lab component.
   q6 gold: 67 patients (48 metformin with last eGFR < 30; 11 ACE inhibitor and 9 statin with an active pregnancy).
   Genie One's answer matches it exactly (hand-verified).

Realism caveat found on q7: SPD counts a statin **dispensed** in the year, and our data approximates dispensing by
an order's start date. The hero's only statin is an open-ended 2009 order; an EHR order isn't a fill, so "SPD gap"
is right by the rule, but the patient could equally be "on a statin with no recorded 2026 fill".

## Before the final run

1. Re-record Genie Ontology / Genie One after the daily extraction (§ cells).
2. Decide the unmanaged dev dashboard and dev/Clone Genie spaces (stale schema in inferred snippets, † q7).
3. Ontobricks republish (`ONTOBRICKS_REPUBLISH.md` 2026-11-21 items 1, 2, 3, 3b, 4, 5b).
4. Hand-check the judge's misses, then `--final`.
