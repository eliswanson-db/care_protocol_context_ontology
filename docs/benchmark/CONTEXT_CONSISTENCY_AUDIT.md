# Context consistency audit: do the five approaches hold the same facts? (2026-11-17)

The benchmark tests retrieval **mechanism**, so every approach must hold the same facts (ADR-0025). This audit checks
the facts each approach actually holds. For deployed state it queries ECT live: the published graph
`triplestore_clinicaldomain_v3`, the Lakebase RAG chunks, the closure/edge tables, gold and the metric views. It
checks repo content (Pages, comments, Genie instructions, documents) as text. Scripts: `/tmp/audit/*.py`; the
lasting checks are in `tests/test_hedis_context_parity.py` and `tests/test_ls_knowledge_parity.py`.

Legend: ✓ holds the fact, consistent · ✗ holds a **different** value · — doesn't hold it · (fixed) corrected in this audit

## HEDIS

### Measure definitions (canonical = `src/pipelines/measures.py`)

| Fact | Metric views | Closure / edge tables | Graph v3 (published) | RAG (Lakebase) | Genie Ontology (Pages, comments, agents) |
|---|---|---|---|---|---|
| GSD 18–75, A1c in MY, bands <8 / >9 | ✓ | ✓ thresholds | ✓ thresholds | ✓ | ✓ |
| KED 18–85, eGFR **and** uACR | ✓ | ✓ value sets | ✓ | ✓ | ✓ (stale coverage % removed: (fixed)) |
| BPD <140/90, latest reading | ✓ | ✓ | ✓ thresholds; monitoredBy **✗ old "BP"** | ✓ | ✓ |
| SPD 40–75, statin | ✓ | ✓ | ✓ | ✓ | ✓ |
| EED 18–75 | ✓ | ✓ | ✓ | ✓ | ✓ |
| SSD 18–64, SMI + antipsychotic | ✓ | ✓ value sets | **— no SSD node** | ✓ | ✓ |
| MAD PDC ≥ 80%, ≥2 biguanide fills | ✓ | ✓ (rxnorm class) | **— no MAD node** | **—** | — → ✓ new Page (fixed) |
| **Step 3:** A1c ≥ 9.0 → recheck ≤ 90 d | ✓ (≥ 9%, 90 d) | — | **—** | **✗ "> 9.0% … within 3 months"** | — → ✓ new Page (fixed); app said "at/above-target" (fixed) |

### Protocol knowledge edges (22 rows of `protocol_edges.csv`)

| | Closure / edge tables | Graph v3 | RAG | Pages before | Pages now |
|---|---|---|---|---|---|
| Edges held | 22 / 22 | **20 / 22** (BPD monitoredBy SBP/DBP missing) | 22 / 22 | **10 / 22** | 22 / 22 (generated Page) |

Genie agents could already query `protocol_edges` (Terminology agent), so Pages were the gap, not access.

### Hierarchies and value sets

| Fact | Closure | Graph v3 | RAG | Pages |
|---|---|---|---|---|
| E11.22 under E11.2 **and N18** (multi-parent) | ✓ | **✗ E11.2 only** | — | ✓ |
| Drug → class membership (16 class_member edges) | ✓ 16 | **✗ 3 (statins only)** | prose only | — |
| Measure value-set codes (e.g. KED_EGFR) | ✓ | **— (no `contains` for measure value sets)** | **— (no LOINC codes)** | ✓ |
| MY2026 KED drops MDRD 33914-3 | ✓ (year-stamped) | — | ✓ (payer memo) | ✓ (drift Page; stale count fixed) |
| MY2026 GSD adds GMI 97506-0 | ✓ | — | ✓ | — (and **no GMI results exist** in the data) |

### Findings that need a decision (not changed by this audit)

1. **Measures ignore value-set versions.** Each measure uses the union of codes across all `measurement_year`s. The
   reported MY2026 KED counts 33914-3 (2,453 of 2,453 eGFR results). The MY2026 value set, the payer memo (RAG) and
   the drift Page all say that code is dropped, so "KED in MY2026" is 47% from the metric view and ~0% under the
   stated rule.
2. **Step-3 trigger ≥ 9.0 vs > 9.0.** The code and metric view say ≥ 9.0%. The protocol document (RAG), the GSD poor
   band and the graph threshold `a1c_poor_gt_9` say > 9%. 35 of 904 triggers are exactly 9.0, so changing it moves
   the drift numbers.
3. **Graph v3 is behind the closure tables.** E11.22→N18, BPD→SBP/DBP and 13 drug-class edges are missing (republish
   paths in `docs/ontology/ONTOBRICKS_REPUBLISH.md`). MAD, SSD and Step 3 aren't in the project mapping at all.
4. **RAG has no reference entries.** It holds prose documents only: no codes and no MAD. The life-sciences lab adds
   one generated entry per fact; doing the same for HEDIS needs a Lakebase write.
5. **Old published Pages** (`docs/ontology/PAGES_FLAGGED.md`) still sit next to the managed ones. Values agree on
   the audited facts; titles and coverage differ.

Patient-level facts in the graph match gold exactly: GSD eligible 2,399 / gaps 618, SPD gaps 1,870. The deployed RAG
chunks equal the repo corpus (36/36).

## Life sciences

Canonical = approved rule registry + `kb_edge`.

| Fact group | Graph (views) | RAG (`rag_corpus`) | Documents (approved) | Pages | Genie agents | Metric views |
|---|---|---|---|---|---|---|
| Endpoint rules R1/R2/B (window, target, baseline, tie-break) | ✓ 12/12 | ✓ | ✓ | ✓ | refers to tables | computed (gold) |
| WRC-V1 roots (10), carve-outs (3), V2 adds OSA only | ✓ | ✓ | ✓ | ✓ | refers to tables | — |
| Exclusions (7 roots), CSL-B retinopathy exception | ✓ | ✓ | ✓ | ✓ | refers to tables | — |
| Prohibited meds (GLP-1 class + appetite suppression, 90 d) | ✓ | ✓ | ✓ | ✓ | refers to tables | — |
| CI ignores product-specific hypersensitivity | ✓ | ✓ | ✓ | ✓ | refers to tables | — |
| Amendment dates, ±21 draft = candidate | n/a | ✓ | ✓ (draft not approved) | ✓ | ✓ | — |
| Every KB fact (5,479 edges) | ✓ (test) | ✓ (test) | n/a | by design: classes and rules only; per-concept facts via tables | via tables | — |

No inconsistencies found. Pages quote no data-derived numbers (only fixture values). **Not yet comparable:** the
published Ontobricks graph (import pending) and Lakebase RAG (loading pending), so only their sources are verified.
