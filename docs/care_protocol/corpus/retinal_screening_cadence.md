---
doc_id: CP-EYE-CADENCE-2025.1
title: "Diabetic Retinal Screening: Urgency and Risk-Stratified Cadence"
source: "Derived from the VA/DoD Diabetes CPG and an adult diabetes clinical practice model (public-domain clinical guidance)."
license: public-domain-derived-synthetic
effective_date: 2025-01-01
measurement_year: 2025
access: [quality_analytics, care_team]
patient_id: null
labels: "Synthetic · HEDIS-aligned (eCQM-proxied) · Not NCQA-certified · Not for clinical use"
---

# Diabetic Retinal Screening — Urgency and Cadence

> Synthetic care-protocol guidance for the Care Protocol Context & Ontology demo. HEDIS-aligned, not
> NCQA-certified, not for clinical use.

## New diagnosis: a 6-month deadline

A patient with **newly diagnosed type 2 diabetes** should have a dilated or retinal-imaging eye exam **within
6 months of diagnosis** to detect background retinopathy that may already be present at diagnosis.

## Risk-stratified surveillance interval

- **Biennial (every 2 years)** screening is acceptable for patients with **no retinopathy** on a prior exam
  and otherwise low risk.
- **Annual or more frequent** screening is required for patients with **existing or progressing retinopathy**,
  poor glycemic control, or other risk factors.

## Why this is richer than the EED measure

The EED quality measure records whether a retinal exam was **performed in the measurement year** (with a
biennial-lookback allowance). It cannot express:

1. The **6-month urgency** window for a newly diagnosed patient.
2. The **risk stratification** that shortens the interval to annual for patients with retinopathy.

A document-retrieval arm that reads this protocol can answer *"how soon does a newly diagnosed patient need an
eye exam?"*; a metric view over structured encounters cannot.
