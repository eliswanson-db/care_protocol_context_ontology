# A1 (Genie One) run evidence — A1-off (ECT) vs A1-on (DMVM)

Observational layer of the capability map (ADR-0018). Machine-observed by driving Genie One headless over the
20 ground-truth questions on each workspace arm, same shared catalog, differing native-ontology density.
Snapshots: `A1_off_ect_<date>.json`, `A1_on_dmvm_<date>.json`. Genie is non-deterministic — each file is an
as-of snapshot. (A `--raw` event-stream sample was inspected locally to see the retrieval detail the summary
hides, but it is **not committed** — the raw stream embeds short-lived JWTs; regenerate with
`databricks genie ask ... --raw` if needed. `.gitignore` guards `raw_sample_*.jsonl`.)

## Headline (2026-11-01)

| signal | A1-off (ECT, ~200 snippets) | A1-on (DMVM, ~1,100 snippets) |
|---|---|---|
| first-pass reached gold (auto) | 16/20 | 16/20 |
| `search_knowledge_snippets` fired | 1/20 | 2/20 |
| cited/fetched a Page (modeled) | 11/20 | 10/20 |

**Accuracy is identical (16/16).** Per-question the two arms differ on only two, and both flip between runs
(`proto_albuminuria_aceiarb` ON-gained; `sub_kidney` OFF-better) — run-to-run Genie noise, not a stable signal.

## What's really going on (from `--raw`, which exposes retrieval the `--output json` summary hides)

On DMVM, `search_knowledge_snippets` surfaces a **broad candidate set spanning the whole workspace** — other
Genie spaces (Cedar Population Health, DBXMetagen, Supply Chain Orders…), `system.*` tables, and multiple
Discover Pages — then narrows to `eli_test_classic_catalog.care_protocol_semantic.gsd_compliance_metrics` + the
"Compliance Rate" Page. That breadth **is** the high-density inferred ontology at work. But it does **not change
the final answer**, because every one of these 20 questions is already covered by the shared governed metric
views + the 16 curated Pages — and **both** workspaces have those (Pages were imported on ECT originally and on
DMVM this session; the metric views live in the shared catalog).

## Honest conclusion + the key caveat

For a **well-modeled** domain (governed metric views + curated Pages), Genie One reaches the answers **with or
without** the high-density inferred ontology; the inferred layer adds breadth of candidate grounding, not answer
correctness, on covered questions. This is consistent with the capability-map thesis: classes 1–7 and 9 are
reachable by the modeled/closure layers; only graph-native class 8 is unreached by everything.

**Caveat — this is partly a property of the question set.** The 20 questions are deliberately
metric-view/closure/Page-answerable (the care_protocol domain is fully modeled), so they do not isolate what
inferred snippets *uniquely* add. A fair test of inferred-ontology value needs questions the modeled layer
**cannot** answer — e.g. cross-space discovery, or questions about assets outside care_protocol — where only the
inferred snippets carry the answer. That is a benchmark **scope** decision (see next step).

## Reproduce

```
python src/benchmark/run_capability_map.py --arm A1 --profile ECT  --out /tmp/capmap_ect
python src/benchmark/run_capability_map.py --arm A1 --profile DMVM --out /tmp/capmap_dmvm
# commit the two A1_detail.json as dated snapshots here, then:
python src/benchmark/persist_a1_runs.py      # -> eli_test_classic_catalog.care_protocol.benchmark_a1_runs
```
