---
page: pages/4ae0fb88-3dc7-4b45-93e0-4491de7b9f08
title: "Care Gap"
state: PUBLISHED
updated: 2026-10-30T15:36:11.909Z
synonyms: ["MET", "NOT_MET", "care gap", "denominator", "gap in care", "numerator", "open gap"]
description: "Patient-level status: an eligible patient (in the denominator) missing a measure's required care is NOT_MET and has an open gap."
---
## Definition
A **care gap** is an eligible patient who has not received the care a measure requires.

* **Denominator (eligible):** the patients a measure applies to.
* **Numerator (compliant):** the eligible patients who received the required care.
* **Status:** **MET** if the patient is in the numerator; otherwise **NOT_MET**, which means an open care gap.

## Data
Each `gold_adherence_<measure>` row holds one patient's status plus **record-level evidence** (test date, code, and value), so every MET or NOT_MET is traceable.

## Business use
Gap lists drive outreach. Closing a gap moves the patient into the numerator, which raises the measure's **Compliance Rate**.
