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

## How to publish (manual, ~once)
Prerequisite: a domain exists. On ECT that is **`Clinical Domain`** (tag_key `Clinical Domain`, id
`b624f99f-8903-40db-a1d6-61c11e3336e7`) — created by `scripts/create_domains.py --root-tag "Clinical Domain"`.

1. Databricks → **Discover → Pages → Bulk import pages**.
2. Open the **Genie Code** pane; attach these files (or point it at this repo folder / an MCP source).
3. Genie Code proposes one Page per term. Review, assign each to the **Clinical Domain** domain.
4. **Publish** (drafts are owner-only; published Pages are visible to Genie One for everyone).
5. Verify: ask Genie One a question (e.g. "what is the GSD compliance rate?") and confirm the answer **cites**
   the Page / metric view under "Ontology References" (may take time to extract — see RUNBOOK async waits).

## File = one Page
Each file's front block gives the fields Pages expects (name, synonyms, domain, owner); the body is the
Page body. Keep terms consistent with the UC comments and metric-view synonyms so the whole ontology agrees.
