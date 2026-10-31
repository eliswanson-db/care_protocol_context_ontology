---
doc_id: PAYER-MEMO-MY2026
title: "Payer Quality Policy Memo — Measurement Year 2026 Changes"
source: "Synthetic payer policy memo authored for the demo, grounded in publicly described HEDIS MY2026 measure evolution and KED value-set modernization."
license: synthetic
effective_date: 2026-01-01
measurement_year: 2026
supersedes: CP-DM-2025.1
access: [quality_analytics, care_team]
patient_id: null
labels: "Synthetic · HEDIS-aligned (eCQM-proxied) · Not NCQA-certified · Not for clinical use"
---

# Payer Quality Policy Memo — MY2026 Changes

> Synthetic payer memo for the Care Protocol Context & Ontology demo. HEDIS-aligned, not NCQA-certified, not
> for clinical use. This memo **supersedes** the MY2025 glycemic-status guidance for measurement year 2026.

## 1. GSD now accepts a Glucose Management Indicator (GMI)

Effective **measurement year 2026**, the Glycemic Status Assessment (GSD) numerator accepts a **Glucose
Management Indicator (GMI)** derived from continuous glucose monitoring (CGM) as an equivalent glycemic-status
result, alongside a laboratory **HbA1c**. The GMI result is identified by **LOINC 97506-0**; HbA1c remains
**LOINC 4548-4** (and method variants). A patient with a qualifying GMI but no lab HbA1c is now **compliant**.

Operational impact: the GSD value set gains a code for MY2026. A patient who looked like a care gap under the
MY2025 value set (CGM data only, no lab draw) flips to compliant under MY2026 — a pure **measure-drift** event
driven by a value-set version change, not by any change in the patient's data.

## 2. KED kidney value-set modernization

For **MY2026**, the eGFR value set is modernized to the race-free CKD-EPI 2021 estimating equation and
**drops the legacy race-based (MDRD) eGFR code** that older lab feeds still emit. Health systems whose result
feed still carries the legacy code will see eGFR coverage — and therefore KED compliance — fall on otherwise
unchanged data until mapping is updated. This is the second controlled drift scenario in the demo.

## 3. No change to protocol guidance

These are **measurement** changes. The underlying clinical care protocol (A1c targets, cardiorenal
pharmacotherapy, screening cadence) is unchanged. Updating a measure value set is not the same as updating the
standard of care — the demo deliberately distinguishes the two.
