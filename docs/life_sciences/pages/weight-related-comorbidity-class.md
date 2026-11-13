---
name: Weight-related comorbidity class (WRC-V1 / WRC-V2)
synonyms: [weight-related comorbidity, comorbidity class, BMI 27, eligibility class, WRC-V1, WRC-V2, obstructive sleep apnea]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.clinical_study_standards.concept_class
  - eli_test_classic_catalog.clinical_study_standards.class_root
  - eli_test_classic_catalog.clinical_study_standards.mondo_closure
---

A participant with BMI ≥ 27 and < 30 qualifies for CSL-A only with at least one member of this class.

**Roots (WRC-V1):** hypertensive disorder (MONDO:0005044), hyperlipidemia (MONDO:0021187), hypertriglyceridemia
(MONDO:0005347), type 2 diabetes mellitus (MONDO:0005148), prediabetes syndrome (MONDO:0006920), coronary artery
disorder (MONDO:0005010), heart failure (MONDO:0005252), stroke disorder (MONDO:0005098), peripheral arterial
disease (MONDO:0005386), MASLD (MONDO:0013209).

**Carve-outs (exclusion wins):** pulmonary hypertension (MONDO:0005149), pregnancy-induced hypertension
(MONDO:0024664), congenital coronary artery malformation (MONDO:0015203).

**WRC-V2 (Amendment 2)** = WRC-V1 + obstructive sleep apnea syndrome (MONDO:0007147). Central sleep apnea is not
added.

**Membership** is the root and everything under it by is_a, at any depth, minus anything under a carve-out. MONDO
is a polyhierarchy, so a term can reach a root through one parent and a carve-out through another (then it is not a
member). The class is **not** a flat list of codes.
