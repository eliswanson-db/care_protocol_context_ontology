---
doc_id: CP-SSD-BH-2025.1
title: "Diabetes Screening for People on Antipsychotics (Behavioral-Health Cohort)"
source: "Facts paraphrased from the public HEDIS SSD measure description (Diabetes Screening for People With Schizophrenia or Bipolar Disorder Who Are Using Antipsychotic Medications). NCQA measure text is proprietary; only facts are summarized here."
license: facts-only-synthetic
effective_date: 2025-01-01
measurement_year: 2025
access: [quality_analytics, care_team]
patient_id: null
labels: "Synthetic · HEDIS-aligned (eCQM-proxied) · Not NCQA-certified · Not for clinical use"
---

# Diabetes Screening for People on Antipsychotics (SSD)

> Synthetic care-protocol guidance for the Care Protocol Context & Ontology demo. Facts only; HEDIS-aligned,
> not NCQA-certified, not for clinical use.

## Why this population needs screening

Second-generation antipsychotic medications carry a well-established risk of weight gain, dyslipidemia, and
new-onset diabetes. People with schizophrenia, schizoaffective disorder, or bipolar disorder who are
dispensed antipsychotics are therefore a **high-metabolic-risk population** that is frequently missed by
routine diabetes screening. This is a **cross-domain** measure linking behavioral health and metabolic care.

## Eligible population

- Adults **aged 18–64** during the measurement year.
- A diagnosis of **schizophrenia, schizoaffective disorder, or bipolar disorder**, evidenced by at least one
  acute inpatient encounter **or** at least two outpatient / ED / partial-hospitalization / telehealth visits.
- **At least one antipsychotic medication dispensed** during the measurement year.

## Numerator (compliant)

At least one **glucose test** or **HbA1c test** during the measurement year. Code systems: CPT for the lab
procedure (e.g. glucose panels; HbA1c 83036/83037), LOINC for the result, and RxNorm for the antipsychotic
dispensing event.

## Exclusions

Patients with **pre-existing diabetes** (already under diabetes management), hospice, or death during the
measurement year are excluded; a patient with no antipsychotic dispensing is not eligible.

## Relationship to the drug-induced diabetes code family

Antipsychotic-associated hyperglycemia can be coded under the ICD-10-CM **E09** family (drug- or
chemical-induced diabetes). This links the SSD behavioral-health cohort to the diabetes terminology graph.
