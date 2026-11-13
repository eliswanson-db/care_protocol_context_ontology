# Genie Code: Clinical Study Lab Pages bulk-import prompt

Pages have no API, CLI or bundle resource, so this import is manual (same as HEDIS, ADR-0008). The sources are
`docs/life_sciences/pages/*.md`. The `ls_context` job stages them to the volume below.

**Domain:** the existing `Clinical Domain` (id `b624f99f-8903-40db-a1d6-61c11e3336e7`). A dedicated
`Clinical Study Lab` domain could not be created: ECT's account is at its 1,000-domain cap. The four governed
tags for that tree exist; if a domain slot frees up, run
`python scripts/create_domains.py --profile ECT --tree life_sciences` and move these Pages to it.

## Prerequisite

`/Volumes/eli_test_classic_catalog/clinical_study/ontology_pages` holds **16 files**: 15 Page sources plus
`README.md`. To refresh it: `databricks bundle run ls_context -t ect --profile ECT`.

## Prompt (paste into Genie Code on the ECT workspace)

> Bulk-import the Clinical Study Lab Pages into the existing domain `Clinical Domain`
> (id `b624f99f-8903-40db-a1d6-61c11e3336e7`). Do not create a new domain or any subdomains, and do not modify
> or delete any existing Page.
>
> **Source:** `/Volumes/eli_test_classic_catalog/clinical_study/ontology_pages`
>
> **One Page per `.md` file, skipping `README.md`: exactly 15 Pages.**
>
> For each file: the Page title is the frontmatter `name`; synonyms are the frontmatter `synonyms`; link every
> table listed under `related_assets`; the Page body is everything after the frontmatter, verbatim (keep tables,
> lists, bold text and code formatting). Do not summarize, rewrite or add content. Owner:
> `eli.swanson@databricks.com`.
>
> When done, list the 15 Page titles you created and any file you could not import, with the reason.

## Check after import

The 15 titles, as in the frontmatter `name` fields: Clinical Study Context & Evidence Lab (overview) · Study
glossary · Standards and versions (Clinical Study Lab) · Dataset and domain guide (Clinical Study Lab) · Endpoint
definitions (Week 24 weight change) · Baseline and visit-window rules · Unit normalization (body weight) ·
Protocol amendments (CSL-A) · Record-level traceability · Cross-study comparability (Week 24) · Known limitations
(Clinical Study Lab) · Tool and retrieval routing (Clinical Study Lab) · Weight-related comorbidity class
(WRC-V1 / WRC-V2) · Exclusionary history and class contraindications · Prohibited medications (PROHIB-CM-V1).
