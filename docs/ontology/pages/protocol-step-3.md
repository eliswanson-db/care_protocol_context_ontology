---
name: Protocol Step 3 — A1c recheck within 90 days
synonyms: [protocol step 3, step 3, A1c recheck, recheck within 90 days, intensify therapy, protocol adherence, follow-up A1c, PROTO_STEP3, protocol drift]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.care_protocol.gold_protocol_adherence
  - eli_test_classic_catalog.care_protocol_semantic.protocol_adherence_metrics
  - eli_test_classic_catalog.care_protocol.protocol_watch_findings
---

**Protocol Step 3** is a care-process rule, not a HEDIS outcome measure: after a high A1c result, the care team should
intensify therapy and **recheck A1c within 90 days**.

- **Trigger:** every A1c result **above 9.0%** in the measurement year, the same line as GSD *poor control*. Each one is a separate obligation
  (`gold_protocol_adherence`, one row per trigger).
- **Met:** any later A1c within **90 days** of the trigger (a recheck that lands in January of the next year counts).
- **Not met:** the 90-day window closed with no recheck. **Open:** the window hasn't closed yet; open triggers are
  excluded from the adherence rate, not counted as misses.
- **Rate:** `Step-3 Adherence Rate` in `protocol_adherence_metrics` = met / closed triggers.
- **Drift:** the Weekly Protocol Watch compares each clinic's trailing 3-month rate with its own earlier rate
  (`protocol_watch_findings`); an annual ranking can hide a clinic that is drifting.

**Wording:** the care-protocol document states the rule as "A1c **> 9.0%** … escalation within **3 months**". The
computed rule uses the same threshold and counts 3 months as 90 days.
