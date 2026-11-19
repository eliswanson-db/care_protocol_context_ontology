# Unmanaged Genie spaces on ECT: flagged, NOT modified (2026-11-19)

These two spaces are outside the bundle, but they were the main source of HEDIS inferred snippets (36 of 50 in the
recorded Genie One runs; see `docs/benchmark/CONTEXT_CONSISTENCY_AUDIT.md`). As of today the repo-managed `(ect)`
spaces carry their own knowledge stores (ADR-0027), so these spaces are no longer needed as a snippet source.
**Neither space was edited.** Read-only snapshots are in `docs/ontology/genie_unmanaged_snapshot/`.

| Space | Id | Knowledge store | Issue | Recommendation |
|---|---|---|---|---|
| (Clone) [dev eli_swanson] Care Protocol — HEDIS Diabetes Quality (dev) | `01f1d573b2fd1d4a8d48b82d9a9040f3` | 13 measures, 9 filters, 7 expressions, 4 joins, 4 column settings, 10 examples | Still uses the removed column `numerator_flag`; overlaps the managed space, so Genie One mines duplicate snippets | Trash it once the managed spaces' snippets show up in Genie One (about a day after deploy) |
| [dev eli_swanson] Care Protocol — HEDIS Diabetes Quality (dev) | `01f1d4983b7e1d71b07aec80b1bb5c5f` | 8 filters, 3 expressions, 23 column settings, 12 examples | Current names; overlaps the managed space | Keep as your dev sandbox, or trash after the same check |

The managed `Care Protocol — HEDIS Diabetes Quality (ect)` space now carries the union of their still-valid items,
each one re-checked against the metric views (`scripts/genie_knowledge.py --validate`).
