---
document_id: CSL-EIN-v1.0
title: "Endpoint interpretation note: Week 24 weight change in CSL-A and CSL-B"
study_id: null
doc_type: NOTE
version: "1.0"
status: APPROVED
effective_date: "2025-03-01"
approval: "demo-fixture (seeded; no real human approval)"
access: "all"
---
# Endpoint interpretation note: Week 24 weight change in CSL-A and CSL-B

SYNTHETIC DOCUMENT. Illustrative only.

## 1 Are the two Week 24 endpoints equivalent?

No. Both measure the same biomedical concept (Body Weight, C81328) with the same formula, but the derivations
differ:

| Rule | CSL-A (SAP 9.4.1) | CSL-B (SAP 8.3) |
|---|---|---|
| Baseline | last valid weight | mean of all valid weights |
| Baseline window | study day -28 to -1, plus day 1 if timed before dose | study day -14 to -1 only |
| Target date | reference date + 168 days (day 169) | reference date + 167 days (day 168) |
| Analysis window | ±7 days (v1.0) / ±14 days (v2.0) | ±10 days |
| Tie-breaker | later date, then lower sequence | earlier date, then lower sequence |

The same participant data can give a different value under each definition. Results from the two studies must not
be pooled, and a Week 24 value from one study must not be compared with the other without stating both
definitions.

## 2 Background

Analysis windows vary between sponsors; windows of ±28 days are sometimes seen in long obesity programs. That is
background only and is not a rule for either study.

## 3 What these synthetic results can and cannot show

The results are synthetic and descriptive. They cannot establish efficacy, superiority of one treatment over
another, or any causal effect.
