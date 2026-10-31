---
doc_id: CP-PHARM-CARDIORENAL-2025.1
title: "Cardiorenal Pharmacotherapy: Metformin, SGLT2 Inhibitors, GLP-1 RAs, ACE/ARB, Statins"
source: "Derived from the VA/DoD Diabetes CPG and an adult diabetes clinical practice model (public-domain / de-identified clinical guidance)."
license: public-domain-derived-synthetic
effective_date: 2025-01-01
measurement_year: 2025
access: [quality_analytics, care_team]
patient_id: null
labels: "Synthetic · HEDIS-aligned (eCQM-proxied) · Not NCQA-certified · Not for clinical use"
---

# Cardiorenal Pharmacotherapy for Adults with Diabetes

> Synthetic care-protocol guidance for the Care Protocol Context & Ontology demo. Paraphrased from
> public-domain clinical guidance. HEDIS-aligned, not NCQA-certified, not for clinical use.

## Metformin and kidney function

Metformin is first-line glucose-lowering therapy. Kidney-function gates:

- **Do not initiate** metformin when eGFR is below **45 mL/min/1.73m²**.
- Metformin is **contraindicated** below eGFR **30 mL/min/1.73m²**; stop it at that level.
- Between 30 and 45, continue with caution and dose review but do not start it new.

## SGLT2 inhibitors and GLP-1 receptor agonists — organ protection beyond glucose

These agents are indicated for **cardiorenal protection even when A1c is already at goal**:

- Type 2 diabetes **plus atherosclerotic cardiovascular disease (ASCVD)**: add a GLP-1 RA or an SGLT2
  inhibitor to reduce major adverse cardiovascular events.
- Type 2 diabetes **plus heart failure**: add an **SGLT2 inhibitor** to reduce heart-failure hospitalization.
- Type 2 diabetes **plus chronic kidney disease** (eGFR ≥ 20): add an **SGLT2 inhibitor** for renal protection.

The decision is **outcome-driven, not glucose-driven**: a patient at an A1c goal on metformin alone who has
CKD with albuminuria should still have an SGLT2 inhibitor added for renal protection — a recommendation no
HEDIS quality measure captures.

## ACE inhibitors / ARBs and albuminuria

Start an **ACE inhibitor or ARB** when a patient has hypertension with albuminuria, or chronic kidney disease.
The albuminuria gate is a **urine albumin-to-creatinine ratio (uACR) ≥ 30 mg/g**. Monitor uACR **at least
annually**. The KED measure checks that an eGFR test *and* a uACR test were done; it does not encode the
ACE/ARB decision that an abnormal uACR should trigger.

## Statins

Most adults aged 40–75 with diabetes should receive a **moderate-to-high intensity statin** (this is the SPD
measure numerator). Before starting, confirm no contraindication.

## Pregnancy contraindications

**Statins and ACE inhibitors / ARBs are contraindicated in pregnancy.** A gap-closure recommendation that
would otherwise fire (e.g. "start a statin for this 40-year-old with diabetes") must be suppressed if the
patient is pregnant. This is an exclusion the structured measure does not reason about on its own.
