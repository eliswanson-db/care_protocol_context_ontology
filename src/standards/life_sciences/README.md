# Life-sciences standards (vendored subset) — ADR-0022 / ADR-0025

Small curated subsets of **open** standards, committed so the build is reproducible from the repo alone. The raw
releases are **not** committed. Their pinned versions, checksums and terms are in `standards_manifest.yaml`.

| File | What | Built by |
|---|---|---|
| `standards_manifest.yaml` | Source manifest: publisher, URL, release, checksum, terms | hand-edited (re-pin deliberately) |
| `kb_seeds.yaml` | Which MONDO subtrees, MED-RT drugs/classes, CDISC codelists and COSMoS BCs to vendor | hand-edited |
| `kb_curated_edges.csv` | Namespaced `cpl:` demo-extension edges, each with a reason (e.g. a missing MONDO→MeSH xref) | hand-edited |
| `kb_concept.csv` / `kb_edge.csv` | **The knowledge base.** Direct assertions only, with source artifact, authority and release per row | `scripts/ls_build_kb.py` |
| `kb_build_report.json` | Counts, unresolved seeds (must be empty), pruned branches | `scripts/ls_build_kb.py` |

Every retrieval approach is fed from `kb_*` (ADR-0025 parity): graph triples, closures, the RAG reference corpus,
and Genie's governed tables/Pages.

```bash
# 1. download each artifact in the manifest into one cache dir (file names as published), e.g. ~/.cache/care_lab/standards
# 2. build (verifies checksums first; a mismatch is fatal)
.venv/bin/python -I scripts/ls_build_kb.py --cache ~/.cache/care_lab/standards
# 3. the multi-hop paths the demo depends on must still hold
python3 -I tests/test_ls_kb_paths.py
```

Not used: CDISC Library (membership/API key), MedDRA, SNOMED CT, WHO ATC (licensed), and UMLS-distributed MED-RT
content. Only the public NCI EVS release of MED-RT is used. Synthetic demo: validate every code against the official
source before any non-demo use.
