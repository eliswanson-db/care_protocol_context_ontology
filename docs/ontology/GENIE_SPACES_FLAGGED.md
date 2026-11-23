# Unmanaged Genie context sources on ECT: flagged, NOT modified (updated 2026-11-22)

Genie One mines inferred snippets from workspace assets: Genie spaces, dashboards, metric views and query history.
On 2026-11-22 the benchmark recordings showed which assets it actually mined, and which of those taught it
**incorrect** rules (`docs/benchmark/BENCHMARK_V2_RESULTS.md`, †q7). Nothing below was edited by automation; the
owner decides. Read-only snapshots of the two dev spaces: `docs/ontology/genie_unmanaged_snapshot/`.

All of these live under `/Users/eli.swanson@databricks.com/` and carry the `[dev eli_swanson]` prefix of this bundle's
`-t dev` (development-mode) deployments from late October, before gold dropped its verdict columns
(`numerator_flag`, `status`) and before GSD moved to the HEDIS rule. They are this project's, just stale.

## What Genie mined (8 benchmark questions, 144 inferred snippets, 100 distinct)

| Source | Snippets | Certified? | Incorrect snippets (today's rules) |
|---|---|---|---|
| `[dev eli_swanson] Care Protocol — HEDIS Diabetes Quality (dev)` (Genie space `01f1d4983b7e1d71b07aec80b1bb5c5f`) | 27 | **yes** (`system.certification_status = certified`) | none found by the check, but it predates the HEDIS GSD rule |
| `(Clone) [dev eli_swanson] Care Protocol — HEDIS Diabetes Quality (dev)` (Genie space `01f1d573b2fd1d4a8d48b82d9a9040f3`) | 19 | no | its knowledge store uses the removed `numerator_flag` |
| `[dev eli_swanson] HEDIS Diabetes Quality — Care Protocol (dev)` (dashboard `01f1d4983b6f194b897d48fa3cd1eedf`) | 13 | no | **9**: removed `status` / `numerator_flag` columns, "GSD = an A1c test" |
| Managed `(ect)` dashboard (`resources/hedis_quality.lvdash.json`) | 10 | no | 2 (`status`). **Fixed 2026-11-22**: it queried removed columns; now on the metric views |
| Query history (seeded by `src/semantic/seed_query_history.py` + real use) | 39 | n/a | 2 (`status`, `numerator_flag`). **Seed fixed 2026-11-22**; old history ages out |
| Managed metric views | 36 | yes | 1 (GSD poor control "among tested", mined before today's HEDIS change; re-mined on refresh) |
| **Managed `(ect)` Genie spaces (7)** | **0** | **no** | n/a |

The one certified HEDIS Genie space is the dev one, and it is the single largest snippet source; none of the seven
managed spaces is certified, and none had been mined three days after deploy. Usage may matter too: on 2026-11-22,
21 conversations were run on the managed spaces (`scripts/exercise_genie_spaces.py`).

## Recommendations (owner: Eli)

| Asset | Recommendation |
|---|---|
| dev Genie space `01f1d4983b7e1d71b07aec80b1bb5c5f` (certified) | Remove its certification, or set it to deprecated, so Genie stops preferring a stale copy. Keep it as a sandbox if useful. |
| Clone dev Genie space `01f1d573b2fd1d4a8d48b82d9a9040f3` | Trash, or deprecate: it teaches `numerator_flag`. |
| dev dashboard `01f1d4983b6f194b897d48fa3cd1eedf` (+ its two `[dev eli_swanson]` siblings) | Deprecate or trash; or redeploy `-t dev` so it carries the fixed queries (that target also owns the shared schemas, so only on purpose). |
| the seven managed `(ect)` Genie spaces | Certify them (`system.certification_status = certified`), like the metric views. |

Content parity: the managed `Care Protocol — HEDIS Diabetes Quality (ect)` space carries the dev spaces' still-valid
items, rewritten to today's rules (GSD gap reason, care-gap counts, worklist and multi-gap examples), each one
re-checked live (`scripts/genie_knowledge.py --validate`: 258 items ok). Items that encode the old rules were not
copied.
