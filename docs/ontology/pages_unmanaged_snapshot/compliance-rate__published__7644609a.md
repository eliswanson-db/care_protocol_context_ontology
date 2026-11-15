---
page: pages/7644609a-924b-416d-80f0-461e4ab5ea20
title: "Compliance Rate"
state: PUBLISHED
updated: 2026-10-30T15:36:36.883Z
synonyms: ["GSD Compliance Rate", "KED Compliance Rate", "adherence rate", "compliance rate", "measure rate"]
description: "Aggregate measure metric: compliant \u00f7 eligible patients, exposed as a governed measure in each *_compliance_metrics metric view."
---
## Definition
**Compliance rate = compliant (numerator) ÷ eligible (denominator)** for a measure in a measurement year.

## Data
| Measure | Metric view | Governed metrics |
| --- | --- | --- |
| GSD | `gsd_compliance_metrics` | GSD Compliance Rate |
| KED | `ked_compliance_metrics` | KED Compliance Rate, eGFR Test Rate, uACR Test Rate |
| EED | `eed_compliance_metrics` | EED compliance |
| BPD | `bpd_compliance_metrics` | BPD compliance |
| SPD | `spd_compliance_metrics` | SPD compliance |

## Business use
Use the governed metric instead of recomputing the ratio. A rate change can come from a change in care or from a change in the definition; check **Measure Drift** before reading a change as a change in care.
