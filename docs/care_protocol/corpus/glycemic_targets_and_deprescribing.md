---
doc_id: CP-GLY-TARGETS-2025.1
title: "Glycemic Targets, Monitoring Cadence, and De-intensification (Adult Diabetes)"
source: "Derived from the VA/DoD Clinical Practice Guideline for the Management of Type 2 Diabetes Mellitus in Primary Care (public domain, U.S. Government)."
license: public-domain-derived-synthetic
effective_date: 2025-01-01
measurement_year: 2025
access: [quality_analytics, care_team]
patient_id: null
labels: "Synthetic · HEDIS-aligned (eCQM-proxied) · Not NCQA-certified · Not for clinical use"
---

# Glycemic Targets, Monitoring Cadence, and De-intensification

> Synthetic care-protocol guidance for the Care Protocol Context & Ontology demo. Facts are paraphrased from
> the public-domain VA/DoD diabetes CPG. HEDIS-aligned, not NCQA-certified, not for clinical use.

## Individualized A1c targets

A single population A1c threshold is **not** appropriate for every adult with diabetes. The target range is
individualized by comorbidity burden and life expectancy:

| Patient profile | Target A1c range |
|---|---|
| No or minimal microvascular complications, >10 years life expectancy | 6.0–7.0% |
| Moderate comorbidity, 5–10 years life expectancy | 7.0–8.0% |
| Marked comorbidity or end-stage disease, <5 years life expectancy | 8.0–9.0% |

This is the key difference from the GSD quality **measure**, which only records whether an A1c test happened
and buckets the latest value as good control (<8.0%) or poor control (>9.0%). The measure answers *"was a test
done and what was the value?"*; the protocol answers *"what should this specific patient's target be?"*.

## Monitoring cadence

- Check HbA1c **every 3 months** for patients who are above individualized goal or whose therapy has changed.
- Check HbA1c **every 6 months** for patients who are stable at goal.
- Do not react to a single out-of-range HbA1c; confirm with a repeat before escalating therapy.

The GSD measure requires only **one** A1c in the measurement year, so it cannot distinguish a patient checked
quarterly from one checked once.

## De-intensification (deprescribing)

Over-treatment carries real harm. Consider **de-intensifying** glucose-lowering therapy and re-targeting a
higher A1c when a patient is over-controlled relative to their individualized goal — for example an older
adult with chronic kidney disease and a history of hypoglycemia whose A1c is 6.5%.

For adults **aged 65 and older**, prefer drug classes **other than insulin, sulfonylureas, and meglitinides**
to minimize hypoglycemia risk. Age-stratified hypoglycemia-avoidance is absent from the HEDIS measures.
