# Provider Coding & Care Protocol Source Extracts

## Sources & Licensing

**COPYRIGHTED SOURCES (Facts Paraphrased, NOT Verbatim):**
- Johns Hopkins Health Plans GSD measure (© Johns Hopkins Medicine; extracted for healthcare quality measure context only)

**PUBLIC/REFERENCE:**
- SSD measure (HEDIS specification, Johns Hopkins Health Plans public documentation)
- Diabetes CPM (Intermountain Healthcare, publicly available clinical practice model, 2021)
- ICD-10-CM Coding Guidance (CMS public coding guidelines; "Coding Spotlight: Focus on Diabetes")

---

## 1. GSD - Glycemic Status Assessment (Johns Hopkins)

**[COPYRIGHTED — Facts only, paraphrased]**

### Measure Overview
Assesses the percentage of patients (age 18–75) with type 1 or 2 diabetes whose most recent hemoglobin A1c (HbA1c) or glucose management indicator (GMI) result meets one of two thresholds during the measurement year (Jan 1 – Dec 31).

### Numerator Metrics
1. **Good glycemic control:** Most recent HbA1c/GMI result < 8.0%
2. **Poor glycemic control:** Most recent HbA1c/GMI result > 9.0% (or missing/not performed)

### Care-Gap Guidance (Provider Actions)
- Schedule labs prior to patient appointments to improve compliance capture
- If multiple tests recorded on same date, use lowest result
- Repeat elevated tests before year-end to enable compliance
- Educate members on A1c target and CGM goals
- Establish protocols for prescribing continuous glucose monitoring (CGM)
- CGM minimizes fingerstick glucose tests and provides comprehensive glucose variability data
- Adjust therapy as indicated to improve A1c levels
- Refer to case management for chronic condition support (especially for poorly controlled patients)

### Eligible Population & Denominator
- **Age:** 18–75 years (measured as of last day of measurement period)
- **Diabetes diagnosis:** Either:
  - At least 2 diagnoses of diabetes on different dates during measurement year or prior year, OR
  - At least 1 diabetes diagnosis + at least 1 dispensing of insulin or hypoglycemic/antihyperglycemic medication during measurement year or prior year

### Exclusions
- Palliative care patients (any time through end of measurement period)
- Hospice patients
- Deceased patients
- Patients ≥66 years old with both frailty AND advanced illness
- Medicare SNP/LTI patients ≥66 years old

### Test Codes & Terminology
**Acceptable test terminology:** A1c, HbA1c, HgbA1c, Glycohemoglobin, Glycohemoglobin A1c, Glycated hemoglobin, Glycosylated hemoglobin, Hemoglobin A1c

**Not acceptable:** Self-tested HbA1c (not lab-processed), ranges/thresholds (e.g., "< 9.0%"), "Unknown"

**Lab codes:**
- CPT: 83036, 83037 (HbA1c lab test)
- LOINC: 4548-4, 17855-8, 4549-2, 17856-6, 96595-4 (HbA1c), 97506-0 (GMI)
- SNOMED CT: 165679005, 451061000124104

**Result value codes (CPT-CAT-II):**
- 3044F: HbA1c < 7.0%
- 3051F: HbA1c ≥ 7.0% and < 8.0%
- 3052F: HbA1c ≥ 8.0% and ≤ 9.0%
- 3046F: HbA1c > 9.0%

---

## 2. SSD - Diabetes Screening for People With Schizophrenia or Bipolar Disorder on Antipsychotics (HEDIS)

### Measure Spec Summary

| Field | Value |
|-------|-------|
| **Measure Code** | SSD (HEDIS) |
| **Measurement Period** | Jan 1 – Dec 31 |
| **Product Line** | Priority Partners |
| **Age Range** | 18–64 years (as of last day of measurement period) |
| **Improvement Notation** | Increased score = improvement |
| **Data Collection Method** | Administrative (claim/encounter) + Supplemental |

### Eligible Population Criteria

**Behavioral Health Diagnosis:** Persons with:
- Schizophrenia, schizoaffective disorder, OR bipolar disorder, AND

**Service Pattern (at least one of):**
- At least 1 acute inpatient encounter with any diagnosis of schizophrenia, schizoaffective disorder, or bipolar disorder

**OR at least 2 encounters on different dates (same diagnosis type) of any of:**
- Outpatient visit
- Intensive outpatient encounter or partial hospitalization program (PHP)
- Community mental health center (CMHC) visit
- Electroconvulsive therapy (ECT)
- Emergency department (ED) visit
- Nonacute inpatient encounter
- Telehealth visit
- Telephone visit
- E-visit or virtual check-in

**Plus:** At least 1 antipsychotic medication dispensing event during measurement period

### Numerator
Persons who received **either**:
- A glucose lab test (CPT: 80047, 80048, 80050, 80053, 80069, 82947, 82950, 82951), OR
- An HbA1c lab test (CPT: 83036, 83037)

During the measurement period.

### Denominator Exclusions
- Hospice patients
- Deceased patients
- **Pre-existing diabetes:** Either:
  - At least 2 diagnoses of diabetes on different dates in measurement year or prior year, OR
  - At least 1 diabetes diagnosis + at least 1 diabetes medication dispensing (insulin or hypoglycemic/antihyperglycemic)
- Persons without any antipsychotic medication dispensing during measurement period

### Antipsychotic Medications (Measure-Covered List)

**Oral/Injectable:**
Aripiprazole, Aripiprazole lauroxil, Asenapine, Brexpiprazole, Cariprazine, Chlorpromazine, Clozapine, Fluphenazine, Haloperidol, Iloperidone, Loxapine, Lurasidone, Molindone, Olanzapine, Paliperidone, Perphenazine, Pimozide, Quetiapine, Risperidone, Thioridazine, Thiothixene, Trifluoperazine, Ziprasidone

**Long-Acting Injections (HCPCS):**
J0401, J1631, J1943, J1944, J2358, J2426, J2680, J2794, J2798, J2801

### Laboratory Test Codes

**Glucose tests:**
- CPT: 80047, 80048, 80050, 80053, 80069, 82947, 82950, 82951
- LOINC: 10450-5, 1492-8, 1494-4, 1496-9, 1499-3, 1501-6, 1504-0, 1507-3, 1514-9, 1518-0, 1530-5, 1533-9, 1554-5, 1557-8, 1558-6, 17865-7, 20436-2, 20437-0, 20438-8, 20440-4, 2345-7, 26554-6, 41024-1, 49134-0, 6749-6, 9375-7
- SNOMED CT: 166890005, 166891009, 166892002, 166921001, 166922008, 442545002, 444780001, 1179458001, 1259140002

**HbA1c tests:**
- CPT: 83036, 83037
- LOINC: 4548-4, 4549-2, 17855-8, 17856-6, 96595-4

### Best Practice & Care Guidance
- Establish annual screening protocols with care-gap alerts in EHR
- Request lab tests be completed prior to scheduled appointments
- Follow up with patients to discuss and educate on lab results
- Coordinate care with other providers managing the patient
- Reach out to patients who cancel to reschedule promptly
- Discuss importance of diabetes screening given elevated risk with antipsychotics
- Educate on early symptoms of new-onset diabetes
- Consider referrals to dietitian or other health professionals
- Inform patients/caregivers of increased diabetes risk with antipsychotic use

---

## 3. Diabetes CPM - Adult Diabetes Clinical Management (Intermountain Healthcare, 2021)

### Treatment Goals & Targets

| Clinical Measure | Goal | Frequency |
|------------------|------|-----------|
| **HbA1c** | < 7.0%* | Every 6 months |
| **Blood Pressure** | < 140/90 mmHg* | Each office visit |
| **Foot Exam** | Normal | Annually (every visit if abnormal) |
| **Statin Medication** | Appropriate intensity | As prescribed |
| **Urine Albumin/Creatinine Ratio** | < 30 mg/g creatinine | Annually |
| **Serum Creatinine (eGFR)** | Normal | Annually |
| **Retinal/Dilated Eye Exam** | Normal | Annually (or every 2 years if well controlled) |

*Goals should be individualized; not all patients require the same target.

### Screening & Diagnosis Strategy

**Type 2 Diabetes Screening:**
- Recommended routine screening in at-risk populations
- Consider screening adults > 30 years old every 3–5 years (cost-effective; reduces MI and microvascular complications)
- Many patients present with existing complications (neuropathy, nephropathy, retinopathy) at diagnosis (~25% of type 2 undiagnosed)

**Type 1 Diabetes Screening:**
- No routine screening (typically acute presentation with markedly elevated glucose)
- First-degree family members can be referred to research studies (e.g., TrialNet)

**Diagnostic Tools:**
- **HbA1c:** No fasting required; specimen stable at room temperature; preferred over point-of-care testing; can be done during illness. Caveats: slightly elevated normal range in some ethnic groups; increases with age; false-low values in hemolytic anemias.
- **Fasting Plasma Glucose (FPG):** More reproducible, less costly than OGTT
- **Oral Glucose Tolerance Test (OGTT, 75g, 2-hour):** Use when evaluating impaired fasting glucose or suspected diabetes with normal FPG/HbA1c

**Diagnosis confirmation:** Requires repeat testing in absence of unequivocal hyperglycemia.

### Diabetes Type Classification

**Type 2:** Slow onset; older adults (can occur in children); obesity/insulin resistance; often has neuropathy at diagnosis; positive family history; responds to oral/non-insulin agents for years.

**Type 1:** Rapid onset; primarily children/younger adults; DKA or weight loss at diagnosis; insulin required from onset; requires antibody testing if unclear.

**LADA (Latent Autoimmune Diabetes in Adults):** Slow onset; age ≥30; ~10% prevalence in adult-onset diabetes; ~90% GAD-antibody positive; often female, younger, smaller waist (overweight not obese), no DKA; may have family/personal autoimmune history; initially responds to oral meds but eventually requires insulin.

### Care Process Architecture

**Team-based model includes:**
- EDC/EHR integration for population health management
- Education materials and programs for providers and patients
- Data systems for population tracking
- Multidisciplinary care coordination

**Key Clinical Protocols:**
- CVD risk assessment/screening (see algorithms page 24)
- Cholesterol/ASCVD risk management (page 28)
- Hypertension management algorithm (page 29)
- Nephropathy screening & monitoring (page 31)
- Continuous glucose monitoring (CGM) for type 1 and type 2, with enhanced coverage

**Antihyperglycemic Treatment:**
- Updated algorithms for type 2 diabetes (pages 14–23)
- SGLT-2 inhibitors recommended as second-line for type 2 with CVD or diabetic kidney disease (per ADA/AACE guidance)
- GLP-1 agonists recommended as second-line for type 2 with CVD (FDA-expanded indication)
- Icosapent ethyl for CV risk reduction in those with elevated triglycerides on statin therapy

### Early Identification & Prevention

The model emphasizes that many patients develop complications before or at diagnosis. Timely screening and diagnosis enable earlier intervention to delay or prevent:
- Heart disease, congestive heart failure, stroke
- Blindness/diabetic retinopathy
- Kidney disease/diabetic nephropathy
- Nervous system disease/neuropathy
- Amputations
- Dental disease
- Pregnancy complications

---

## 4. ICD-10-CM Diabetes Coding (Coding Spotlight, "Focus on Diabetes")

### Diabetes Mellitus Code Categories

| Category | Type/Etiology |
|----------|----------------|
| **E08** | Diabetes mellitus due to underlying condition (e.g., Cushing's, acromegaly, pancreatitis) |
| **E09** | Drug or chemical induced diabetes mellitus |
| **E10** | Type 1 diabetes mellitus |
| **E11** | Type 2 diabetes mellitus |
| **E13** | Other specified diabetes mellitus |

### Coding Principle: Combination Codes
ICD-10-CM presumes a **causal relationship** between diabetes and related complications unless documentation explicitly states otherwise.

Term definition: "**With**" in a code title, alphabetic index, or instructional note means "associated with" or "due to."

Each diabetes code combines:
1. **Type of diabetes** (categories E08–E13)
2. **Body system affected**
3. **Complications** affecting that system

### Neurological Complications (Sub-Classification)

Formats: **E08–E13 with .4x** (for each diabetes type):
- **.40** – Unspecified diabetic neuropathy
- **.41** – Diabetic mononeuropathy
- **.42** – Diabetic polyneuropathy
- **.43** – Diabetic autonomic (poly)neuropathy
- **.44** – Diabetic amyotrophy
- **.49** – Other diabetic neurological complication

### Circulatory & Skin Complications

| Code Pattern | Complication |
|--------------|--------------|
| **E08–E13 with .51** | Diabetic peripheral vascular disease without gangrene |
| **E08–E13 with .52** | Gangrene (diabetic) |
| **E08–E13 with .621** | Diabetic foot ulcer (with additional code L97.4–L97.5 for site) |
| **E08–E13 with .622** | Other diabetic skin ulcers (with additional code L97.1–L97.9 or L98.41–L98.49 for site) |
| **E08–E13 with .59** | Diabetes with other circulatory complications |

### Status Codes (Frequently Overlooked)

Include status codes for manifestations or sequelae:
- **Ostomies/artificial openings:** Colostomy, gastrostomy, ileostomy
- **Amputation status:** Lower extremities (above-knee [AKA], below-knee [BKA], feet/toes)
- **Long-term insulin use status**

### Nephropathy & Retinopathy

The CPM document (Intermountain) references kidney and eye complications as core management targets; ICD-10-CM has specific subcategories for these within E08–E13 (e.g., E11.21 = type 2 with diabetic nephropathy; pattern varies by complication type).

### Special Populations

**Gestational Diabetes:**
- Assign from category **O24.4** (gestational diabetes in pregnancy, childbirth, puerperium)
- Subdivided by control method: diet, insulin, oral hypoglycemic
- If abnormal glucose tolerance **without** gestational diabetes diagnosis: code from **O99.81** (abnormal glucose complicating pregnancy)
- Do not assign other O24 codes with O24.4

**Diabetes in Pregnancy (Type 1 or 2):**
- Assign code from **O24** (diabetes mellitus in pregnancy, childbirth, puerperium) first
- Follow with appropriate code from E08–E13 to indicate type

**Insulin Pump Malfunction:**
- Mechanical complications: **T85.6** (mechanical complication of prosthetic devices/implants)
- **T85.614** – Breakdown (mechanical) of insulin pump
- **T85.624** – Displacement of insulin pump
- **T85.633** – Leakage of insulin pump

### Uncontrolled Diabetes

No single default code; classify by type and glucose status:
- Uncontrolled hyperglycemia (specific type E08–E13 + hyperglycemia indicator)
- Uncontrolled hypoglycemia (specific type E08–E13 + hypoglycemia indicator)

### Coding Guidance: Hierarchy & Subsumption

The CPM (Intermountain) and coding guidance emphasize proper hierarchy:
- Type 2 diabetes with nephropathy: E11.21 (subsumes E11 + complication)
- Do not use flat lists; rely on hierarchy to capture complication nuance
- Multiple complications: assign all applicable codes
- Verify causal relationship documented by provider

---

## ALLOCATION RECOMMENDATIONS

### Mapping Facts to Demo Components

| Fact Cluster | Primary Allocation | Secondary Use | Rationale |
|--------------|-------------------|---------------|-----------|
| **GSD measure spec** (HbA1c <8.0%, >9.0%, denominator, numerator, codes) | **Metric-View Measure** | RAG corpus | Exact specs for metric-view SQL and reporting; denominator logic maps cleanly to data model |
| **SSD measure spec** (schizophrenia/bipolar + antipsychotic + glucose test) | **Metric-View Measure (candidate/new)** | RAG corpus | Cross-domain measure (behavioral health + diabetes screening) adds diversity; nice story for demo; ready-to-code |
| **GSD control thresholds** (<8.0%, >9.0%) | **Value-Set & Terminology** | Genie Page | Drives buckets in metric dashboard; educate providers on targets |
| **Diabetes CPM: care process steps, algorithms, care gaps** (monitor HbA1c, BP, kidney/eye, statin, referral) | **RAG Corpus + Genie Page** | Metric-View measure detail | Narrative protocol provides context for "what to do next"; enables Genie chat to surface care paths and escalation |
| **ICD-10-CM diabetes code families** (E08–E13 categories) | **Value-Set & Terminology Graph** | Metric-View cohort definition | Subsumption hierarchy (E11 parent codes vs. E11.21 nephropathy) is load-bearing for cohort logic; enables "find all type 2 diabetes + complications" without flat lists |
| **Diabetes code subcategories** (.4x neuropathy, .51/.52 vascular, .621/.622 ulcers) | **Value-Set & Terminology Graph** | RAG corpus | Informs complication flags in metric numerators and denominator exclusions; enables ontology-driven rollup |
| **Best practice care guidance** (schedule labs, repeat elevated tests, refer to case mgmt, CGM) | **RAG Corpus + Genie Page** | Metric metadata (measure tips) | Genie can retrieve and surface gap-closure actions; providers use to close care gaps |
| **Test codes** (CPT 83036, LOINC 4548-4, SNOMED 165679005 for HbA1c) | **Value-Set & Terminology Graph** | Metric-View measure (SQL WHERE clauses) | Cross-code-system lookup; enables provider system integration; feeds ETL pipelines |

### Component Assignments (Summary)

1. **Metric-View Measures:**
   - GSD (existing — finalize numerator/denominator SQL from spec)
   - SSD (new candidate — HEDIS spec ready for implementation)

2. **Value-Set & Terminology Graph:**
   - ICD-10-CM diabetes family tree (E08–E13 + subcategories)
   - A1c test codes + value thresholds (CPT, LOINC, SNOMED)
   - Antipsychotic medication list (for SSD denominator)
   - Care-complication buckets (nephropathy, retinopathy, neuropathy, vascular)

3. **Genie Page / RAG Corpus:**
   - Diabetes CPM care process model (full narrative + algorithms)
   - GSD and SSD measure tips (care gap closure guidance)
   - Provider education on diabetes coding and hierarchy
   - Escalation logic (e.g., "if HbA1c >9.0% → refer case management")

4. **Data Model / Cohort Definition:**
   - Denominator: diabetes codes (E08–E13, at least 2 on different dates OR 1 + medication)
   - Numerator: A1c test codes with result values (<8.0% / >9.0% buckets)
   - Complication flags: ICD-10-CM nephropathy (E11.21 pattern), retinopathy, neuropathy
   - Medication prescriptions: glucose-lowering agents (for GSD), antipsychotics (for SSD)

---

## Next Steps for Implementation

1. **GSD & SSD Measures:**
   - Translate numerator/denominator specs to SQL (Epic/Clarity Clarity schema)
   - Wire up metric-view dashboards with control thresholds as KPI tiles
   - Integrate care-gap closure guidance into Genie prompts

2. **Terminology Graph:**
   - Build ICD-10-CM diabetes subsumption tree (E08–E13 parent + children)
   - Load test codes (CPT, LOINC, SNOMED) with canonical mappings
   - Create antipsychotic medication list (SSD denominator)

3. **Genie Integration:**
   - Seed RAG with Diabetes CPM (Intermountain) for protocol navigation
   - Add measure-specific guidance (GSD/SSD care tips)
   - Build escalation flows (e.g., poor control → recommended interventions)

4. **Synthetic Data:**
   - Generate diabetes cohort with ICD-10-CM codes per hierarchy
   - Simulate A1c tests with realistic distributions (<8%, 8–9%, >9%)
   - Create behavioral-health + antipsychotic cohort for SSD measure simulation
