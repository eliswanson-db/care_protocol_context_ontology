---
name: Cross-study comparability (Week 24)
synonyms: [are the endpoints equivalent, pooling, compare CSL-A and CSL-B, definition mismatch, same biomedical concept different derivation]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.clinical_study_standards.rule_version
---

**CSL-A and CSL-B Week 24 weight change are not equivalent.** Both measure Body Weight (C81328) with the same
formula, but baseline method (last vs mean), baseline window (−28…−1 + day 1 vs −14…−1), target (day 169 vs day
168), window (±7/±14 vs ±10) and tie-breaker (later vs earlier) differ. The same participant data can give a
different value: named participant CSL-B-FX-18 is −5.94% under CSL-B's rule and would be −5.53% under CSL-A's.

**Never pool** the two studies, and never compare a number from one with the other without stating both
definitions. Summaries are always grouped by study **and** rule version.
