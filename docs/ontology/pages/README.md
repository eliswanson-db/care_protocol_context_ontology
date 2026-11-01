# Genie Ontology Pages — source content

These Markdown files are the **source of truth** for the human-modeled layer of the Genie Ontology (UC
Semantics **Pages**). Each file defines one business concept: a HEDIS measure, a clinical term, or a
semantic construct this demo relies on. Pages are the authoritative definitions Genie One prioritizes and
cites ("Ontology References") when answering questions.

## Why these live in the repo (ADR-0008)
Pages have **no public API, CLI, or asset-bundle resource** — they can only be authored in the UI, via
Genie Code, or bulk-imported. So we keep the *content* version-controlled here (regenerable, reviewable) and
treat the import as the one irreducible manual step. This honors the project's reproducibility rule:
everything is code or a documented step.

## How to publish (manual, ~once per workspace)
Prerequisite: the **`Clinical Domain`** domain (tag_key `Clinical Domain`, id
`b624f99f-8903-40db-a1d6-61c11e3336e7`). This domain is **metastore-level and shared** — it already exists on
both ECT and DMVM with the *same* id (created once via `scripts/create_domains.py --root-tag "Clinical Domain"`).
The catalog is shared too, so the staging **volume is one object** both workspaces read.

Use the ready-made, de-duplicated import prompt in **[`../PAGES_IMPORT_PROMPT.md`](../PAGES_IMPORT_PROMPT.md)**
(includes the mandatory "refresh the volume first" pre-req and the review-table gate). In outline:

1. Refresh the volume: `bundle run stage_pages` (→ 16 Page sources + README = **17 files**).
2. Databricks → **Discover → Pages → Bulk import pages** → open the **Genie Code** pane.
3. Paste the import prompt; Genie Code proposes **one Page per `.md`, skipping README → 16 Pages**. Review the
   table, assign each to **Clinical Domain**.
4. **Publish** (drafts are owner-only; published Pages are visible to Genie One for everyone).
5. Verify: ask Genie One a question (e.g. "what is the GSD compliance rate?") and confirm the answer **cites**
   the Page / metric view under "Ontology References" (may take time to extract — see RUNBOOK async waits).

**Pages re-import per workspace:** even though domain + catalog + volume are shared, the published-Page set is
authored per workspace — re-run this import (same prompt, same volume) in each workspace where Genie Ontology
is ON (currently DMVM).

## File = one Page
Each file's front block gives the fields Pages expects (name, synonyms, domain, owner); the body is the
Page body. Keep terms consistent with the UC comments and metric-view synonyms so the whole ontology agrees.
