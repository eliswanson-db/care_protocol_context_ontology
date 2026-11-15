---
page: pages/fd610d42-21c5-48c3-8a29-dfc348e7c7b9
title: "uACR (Urine Albumin-Creatinine Ratio)"
state: PUBLISHED
updated: 2026-10-30T15:37:15.151Z
synonyms: ["ACR", "albumin creatinine ratio", "microalbumin", "microalbuminuria", "uACR", "urine albumin creatinine ratio"]
description: "Urine test for albuminuria, an early sign of kidney damage (LOINC 14959-1, 9318-7); the test that limits KED."
---
## Definition
A urine test measuring albumin relative to creatinine. It is an early marker of kidney damage (albuminuria).

* **Value set:** `KED_UACR`, containing **`14959-1`** (Microalbumin/Creatinine [Mass Ratio] in Urine) and `9318-7`.

## Data
Conformed into `silver_observation`. Feeds `gold_adherence_ked` as `uacr_flag` and the `uACR Test Rate` metric.

## Business use
Far fewer patients have a uACR than an eGFR, so the combined KED rate tracks the uACR rate. Ordering more uACR tests is the lever for closing KED gaps.
