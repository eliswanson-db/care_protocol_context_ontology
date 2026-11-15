---
page: pages/3a8d56e4-2f06-456e-8c90-0bbfe65ddba4
title: "uACR \u2014 Urine Albumin-Creatinine Ratio"
state: DRAFT
updated: 2026-11-01T22:42:45.675Z
synonyms: ["ACR", "albumin creatinine ratio", "microalbumin", "microalbuminuria", "uACR", "urine albumin creatinine ratio"]
description: "uACR (urine albumin-creatinine ratio) measures albumin in the urine relative to creatinine \u2014 an early marker of kidney damage (albuminuria)."
---
**uACR (urine albumin-creatinine ratio)** measures albumin in the urine relative to creatinine — an early
marker of kidney damage (albuminuria). It is the second component of the **KED** numerator.

- **Terminology:** LOINC. The demo value set `KED_UACR` includes **`14959-1`** (Microalbumin/Creatinine
  [Mass Ratio] in Urine) and `9318-7`.
- uACR tests are conformed into `silver_observation` and feed `gold_adherence_ked` (`uacr_flag`).
- In this demo **uACR is the limiting component** of KED: far fewer patients have a uACR than an eGFR, so the
  combined KED rate tracks the uACR rate. Closing the KED gap means ordering more uACR tests.

> HEDIS-aligned demo, not NCQA-certified.
