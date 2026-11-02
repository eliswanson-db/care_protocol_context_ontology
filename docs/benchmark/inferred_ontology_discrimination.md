# Inferred-ontology discrimination — probe finding + candidate questions (PROPOSAL)

## Intent (the demo framing, decided 2026-11-02)

We **intend** `a1_on` (DMVM) to be the ontology-ON arm, and we are deliberately building the per-workspace
surfaces that mint native inferred snippets (analytics notebooks, dashboards, Genie agents, metric views,
column comments, query-history seeding), **assuming** that inferred layer will eventually surface and lift
answers the modeled layer can't reach. **But we do not assert it works.** The probe below shows that, so far,
Genie One on DMVM grounds only in the curated Pages + metric views both arms share. **Whether the native
inferred ontology ever gets retrieved — or whether Genie One always falls back to the shared modeled layer —
is one of the questions this demo is built to answer.** We say that out loud in the app and lead the benchmark
with the hand-verified *layer* capability map, which stands on its own. This doc records the probe, the intent,
and how we'd finally confirm (or falsify) the inferred-layer effect.

---

Status: **proposal / unverified. No benchmark runs yet.** Kept out of `ground_truth.yaml` on purpose —
that file is the hand-verified answer key *and* the `closure_sql` arm, and `run_capability_map.py` executes
every class in it; these candidates have no modeled gold by design, so running them from there would pollute
real runs. Merge a candidate in only after it's validated (see "Promotion" below).

## Why this exists — the DMVM probe (2026-11-02)

We had been **assuming** DMVM exercises a dense *inferred* Genie ontology (the "learned" layer) that ECT
lacks. Probed it directly instead of assuming (`databricks genie ask --raw --profile DMVM`, broad
knowledge-discovery question; raw stream saved to /tmp, **not committed** — it embeds JWTs):

- `search_knowledge_snippets` **fired** and returned the bare string **"Found 4 results"** — the stream does
  **not** expose the snippet contents or type.
- Genie then opened exactly **4 curated knowledge Pages** (`get_asset_info` on `knowledge_page.<uuid>`:
  HbA1c, GSD, Poorly-controlled-diabetes, +1) and resolved table locations via `search_assets` +
  `system.information_schema` SQL.
- The final answer grounded **entirely in the 16 curated Pages + catalog assets** — the *modeled* layer.

**Finding:** from this interface there is **no observable evidence of auto-inferred snippets doing work on
DMVM.** Every ontology artifact we can see is a curated Page or a directly-searched catalog asset — and
**ECT has those too**. This is consistent with the identical-accuracy result in `a1_runs/FINDINGS.md`, and it
means the a1_off-vs-a1_on contrast is **unverified**, not demonstrated.

Caveat on the caveat: absence of evidence isn't proof the inferred layer is empty — the CLI stream simply
hides snippet payloads. But we cannot *claim* an inferred-ontology effect we can't observe.

## Why discrimination is hard

Genie One can reach workspace assets via `search_assets` + `information_schema` SQL **without any inferred
snippet.** So "ask about an asset outside `care_protocol`" does **not** isolate the inferred layer — asset
search answers it. A *true* inferred-only question must need knowledge that exists **only in usage /
query-history** (how the data is actually used), which neither asset-search nor schema metadata can supply.

**Design criterion for a discriminating question:** the answer must be
(a) absent from every curated Page, (b) absent from table/column comments and the information schema, and
(c) present only as a usage/query-history-derived inferred snippet. Then:
`DMVM answers AND ECT does not` ⇒ the inferred layer is real and load-bearing;
`neither answers` ⇒ the inferred layer isn't delivering (the honest null);
`both answer` ⇒ the question wasn't actually inferred-only (redesign).

The most rigorous setup: pick a real workspace table that is (a) **not** covered by a Page, (b) has **no**
comment, but (c) **has** been queried/dashboarded enough to generate an inferred snippet, then ask for its
business meaning. Identifying/seeding such an asset is a setup task (see Next steps).

## Candidate inferred-only questions (draft — each with its risk)

| # | Candidate question | Intended to need | Risk it's answerable without inferred snippets |
|---|--------------------|------------------|-----------------------------------------------|
| I1 | "Based on how this data is actually used, what's the common way analysts filter the diabetes cohort before computing GSD?" | query-history filter patterns | Genie may just describe the cohort table from schema |
| I2 | "Which tables and metric views are usually queried *together* for diabetes quality reporting here?" | usage co-occurrence (query history) | search_assets may list related assets by name |
| I3 | "What does the `<uncommented, un-Paged, but dashboarded>` table/column represent, in business terms?" | inferred snippet from dashboard/query usage | **lowest risk IF the asset truly has no Page/comment** — the rigorous one; needs asset selection |
| I4 | "What's the typical measurement-year window and refresh cadence people assume when they query the GSD metrics?" | operational convention from usage | may be stated in a Page/comment — verify it isn't |
| I5 | "Which diabetes questions do people most often ask Genie in this workspace?" | query-history of NL questions | may not be exposed to Genie at all |

I3 is the only strong discriminator and depends on choosing/seeding a Page-less, comment-less, but
usage-rich asset. I1/I2/I4 are worth trying but must be validated against the design criterion first (confirm
the answer isn't in any Page/comment on ECT).

## Smoke subset (for the slow dev loop)

Genie One calls are ~30–90s each; 20 questions × 2 arms is painful to iterate. `run_capability_map.py
--smoke` runs 5 representative ids (one per key capability):
`kpi_gsd_rate` (metric view) · `sub_kidney` (ICD closure) · `med_on_statin` (RxNorm closure) ·
`def_controlled_bp` (doc/Page) · `op_clinic_drift` (operational/temporal). `--ids a,b,c` runs an arbitrary set.

## Next steps (gated on auth + your call)

1. Re-auth ECT (`databricks auth login --profile ECT`) so both arms are runnable.
2. Decide whether the inferred-layer contrast is worth chasing at all, given the probe — or whether we
   **drop the a1_off/a1_on framing** and present the capability map as the layer story (M0 < closure <
   Genie-One-over-modeled; graph-only class 8), which is already solid and honest.
3. If chasing it: pick/seed the I3 asset, validate I1/I4 against the design criterion on ECT, then run the
   candidates on both arms with `--ids`.

## Promotion (proposal → answer key)

A candidate graduates into `ground_truth.yaml` only after: the answer is confirmed absent from Pages/comments
(design criterion met), a hand-verified expected answer exists, and it's run on both arms. Until then it lives
here.
