# HEDIS & QRS Diabetes Measure Specifications

## Sources & License

- **2027 QRS Technical Specifications** (261 pages; CMS QRS 2027 measure technical specifications, September 2026)
  - Source: `/Users/eli.swanson/Downloads/2027qrsmeasuretechnicalspecifications508.pdf`
  - **Public Domain**: Centers for Medicare & Medicaid Services (CMS) Health Insurance Exchange publication
  - HEDIS measures extracted from section 3.1 NCQA Measure Specifications
  - Measurement Year 2026 (QRS 2027 collection cycle)

- **HEDIS Quality Measure Toolkit** (10 pages)
  - Source: `/Users/eli.swanson/Downloads/HEDIS Quality Measure Toolkit.pdf`
  - Provides high-level reference for all HEDIS measures available in health plans

**Note on Licensing**: CMS QRS specifications are public domain. HEDIS measure names and abbreviations are from NCQA (Healthcare Effectiveness Data and Information Set, registered trademark of National Committee for Quality Assurance). Specifications paraphrased from source documents to avoid verbatim proprietary content reproduction.

---

## QRS 2027 Diabetes Measures (NCQA HEDIS Subset)

### 1. Eye Exam for Patients With Diabetes (EED)

**Measure ID**: EED  
**QRS Source Pages**: 82–87

#### Description
Percentage of persons 18–75 years with type 1 or type 2 diabetes who received a retinal eye exam during the measurement period.

#### Eligible Population (Denominator)
- **Age**: 18–75 years as of last day of measurement period
- **Enrollment**: Medical benefits; continuous enrollment during measurement period with allowable gap of ≤45 days (none on last day)
- **Diabetes Cohort Identification**:
  - ≥2 diagnoses of diabetes (Diabetes Value Set) on different dates during measurement year OR prior year, OR
  - ≥1 diabetes diagnosis + ≥1 diabetes medication dispensing (insulin or hypoglycemic/antihyperglycemic agent) during measurement year or prior year
- **Code Systems**: ICD-10-CM (diagnoses), CPT (procedures), pharmacy data

#### Denominator Exclusions
- Date of death during measurement period
- Hospice services/election any time during measurement period
- Palliative care encounter or receipt (ICD-10-CM Z51.5, relevant value sets)
- Age 66+ with both frailty (≥2 indicators) AND advanced illness (≥2 dates or dementia medication)
- Bilateral absence of eyes or bilateral eye enucleation (SNOMED CT, ICD-10-PCS codes, CPT modifiers)

#### Numerator (Compliance Criteria)
Patient had **retinal or dilated eye exam** by eye care professional (optometrist or ophthalmologist):
- During measurement period, OR
- Negative retinal/dilated eye exam in prior year (if no evidence of retinopathy) with diabetes-without-complications diagnosis
- Code sources: Retinal Eye Exams Value Set, Eye Exam With/Without Evidence of Retinopathy Value Set, Retinal Imaging Value Set (LOINC), Autonomous Eye Exam (CPT 92229 or LOINC 105914-6)
- **Time Window**: Most recent exam during measurement period, with option for prior-year negative exam
- AI-enabled autonomous retinal exams eligible per FDA approval

#### Value-Set & Code Logic
- **Multi-system requirement**: LOINC codes (71490-7 left eye retinopathy, 71491-5 right eye retinopathy), CPT codes (92004, 92012, 92229, 99203-99215 for qualifying visits), CPT Category II (3072F for negative screening)
- Left/right eye must be separately documented OR one eye enucleated with other examined
- Result finding: Diabetic Retinopathy Severity Level Value Set (LA codes for severity levels)

#### Measurement Year Conventions
- Measurement period: January 1 – December 31 (calendar year)
- **Important variation for prior year**: Negative results from prior year count if no prior retinopathy and current glycemic indicators in goal range (allows screening every 1–2 years per ADA guidance)

#### Summary of Changes & Measure Drift
**MY 2026 HEDIS for QRS Changes**:
- Updated race/ethnicity stratification categories to align with OMB SPD 15 2024 and US Core Version 6.1.0 Model Definition
- New autonomous eye exam pathways added (AI-enabled retinal photography with remote reading)
- Added explicit LOINC codes for left/right eye retinopathy findings (71490-7, 71491-5)
- **QRS-specific note**: Race/ethnicity stratification reporting NOT required for QRS submission (unlike full HEDIS)

---

### 2. Glycemic Status Assessment for Patients With Diabetes (GSD)

**Measure ID**: GSD  
**QRS Source Pages**: 94–99  
**Prior Name**: HBD (Hemoglobin A1c for Patients with Diabetes; renamed to GSD in recent years with expanded GMI option)

#### Description
Percentage of persons 18–75 years with type 1 or type 2 diabetes whose most recent glycemic status (HbA1c or Glucose Management Indicator [GMI]) was at specified thresholds. **QRS version reports Glycemic Status >9.0% indicator only.**

#### Eligible Population (Denominator)
- **Age**: 18–75 years as of last day of measurement period
- **Enrollment**: Medical benefits; continuous enrollment during measurement period with allowable gap of ≤45 days (none on last day)
- **Diabetes Cohort Identification**:
  - ≥2 diagnoses of diabetes (Diabetes Value Set) on different dates during measurement year OR prior year, OR
  - ≥1 diabetes diagnosis + ≥1 diabetes medication dispensing (insulin or hypoglycemic/antihyperglycemic agent) during measurement year or prior year
- **Code Systems**: ICD-10-CM (diagnoses), CPT (procedures), pharmacy data, LOINC lab tests

#### Denominator Exclusions
- Date of death during measurement period
- Hospice services/election any time during measurement period
- Palliative care encounter or receipt
- Age 66+ with both frailty (≥2 indicators) AND advanced illness
- Laboratory claims (POS code 81) excluded from diagnosis identification

#### Numerator (Compliance Criteria)
**GSD >9.0% (Out-of-Control Glycemia)** - Administrative version:
- Identify most recent HbA1c or GMI result during measurement period
  - If multiple assessments on same date, use lowest result
- **Compliant**: Most recent glycemic status >9.0% OR missing OR not done during measurement period
- **Not compliant**: Most recent glycemic status ≤9.0%

**Data Sources**:
- LOINC codes: 4548-4 (HbA1c), 97506-0 (GMI)
- Value Sets: HbA1c Lab Test Value Set, HbA1c Test Result or Finding Value Set
- CPT Category II codes: 3046F (compliant), HbA1c Level ≤9.0% Value Set (not compliant)
- **Time specification**: Result date must be specific enough to determine occurrence in measurement period

**Hybrid Collection Note**:
- GMI values must include documentation of CGM data date range used to derive value; use terminal date in range as assessment date
- Most recent result used regardless of data source (administrative, supplemental, or hybrid)
- GMI collected by patient and documented in medical record eligible for use

#### Value-Set & Code Logic
- **Dual-component structure**: HbA1c (lab test) + GMI (CGM-derived alternative)
  - HbA1c primary; GMI accepted alternative when HbA1c not available
  - Both measured in percentage units; threshold ≤9.0% vs >9.0%
- **Code systems**: LOINC (primary for lab results), CPT Category II (3046F for result documentation)
- **Missing/unknown criteria**: "Unknown" NOT considered valid result for compliance determination

#### Measurement Year Conventions
- Measurement period: January 1 – December 31
- **Result recency**: Must be most recent during measurement period; if multiple on same date, lowest used
- **QRS-specific indicator**: Only Glycemic Status >9.0% reported (full HEDIS has additional lower thresholds)

#### Summary of Changes & Measure Drift
**MY 2026 HEDIS for QRS Changes**:
- Updated race/ethnicity stratification categories (OMB SPD 15 2024, US Core 6.1.0)
- **NEW**: Expanded to include Glucose Management Indicator (GMI) as alternative to HbA1c
  - Driven by increased CGM adoption in diabetes care (accuracy, real-time feedback)
  - Requires CGM data date range documentation for auditability
- CPT Category II code 3046F explicitly identified for compliant results
- **Collection methodology clarification**: Both Administrative and Hybrid methods supported; organizations must use same method for all indicators
- **QRS-specific note**: Race/ethnicity stratification NOT required for QRS reporting

---

### 3. Kidney Health Evaluation for Patients With Diabetes (KED)

**Measure ID**: KED  
**QRS Source Pages**: 114–119

#### Description
Percentage of persons 18–85 years with type 1 or type 2 diabetes who received a kidney health evaluation defined by **both** estimated glomerular filtration rate (eGFR) **AND** urine albumin-creatinine ratio (uACR) during the measurement period.

#### Eligible Population (Denominator)
- **Age**: 18–85 years as of last day of measurement period
- **Enrollment**: Medical benefits; continuous enrollment during measurement period with allowable gap of ≤45 days (none on last day)
- **Diabetes Cohort Identification**:
  - ≥2 diagnoses of diabetes (Diabetes Value Set) on different dates during measurement year OR prior year, OR
  - ≥1 diabetes diagnosis + ≥1 diabetes medication dispensing (insulin or hypoglycemic/antihyperglycemic agent) during measurement year or prior year
- **Code Systems**: ICD-10-CM (diagnoses), pharmacy data, lab tests (LOINC)

#### Denominator Exclusions
- Date of death during measurement period
- Hospice services/election any time during measurement period
- Palliative care encounter or receipt
- Age 66–80 with both frailty (≥2 indicators) AND advanced illness (≥2 dates or dementia medication)
- Age 81+ with frailty (≥2 indicators) alone
- ESRD or dialysis any time during history through last day of measurement period (ESRD Diagnosis Value Set, Dialysis Procedure Value Set)
- Laboratory claims (POS code 81) excluded from diagnosis identification

#### Numerator (Compliance Criteria)
Patient received **both** components of kidney health evaluation during measurement period (same or different dates):

1. **eGFR**: ≥1 estimated glomerular filtration rate test (Estimated Glomerular Filtration Rate Lab Test Value Set)
2. **uACR**: Identified by EITHER:
   - Quantitative urine albumin test (Quantitative Urine Albumin Lab Test Value Set) AND urine creatinine test (Urine Creatinine Lab Test Value Set) with service dates ≤4 days apart
     - Example: If albumin test on Dec 1, creatinine must be Nov 27–Dec 5
   - Direct uACR test (Urine Albumin Creatinine Ratio Lab Test Value Set)

**Time specification**: Service dates must be specific enough to determine occurrence in measurement period; dates of eGFR and uACR can span entire measurement period independently.

#### Value-Set & Code Logic
- **Multi-component requirement (CRITICAL for measure engine)**:
  - Component 1: eGFR (single test result, numerical)
  - Component 2: uACR (either single direct test OR pair of tests with 4-day proximity rule)
  - Both required; cannot report numerator compliance with only one component
- **Code systems**:
  - LOINC: urine albumin (30315-0, 30316-8), urine creatinine (2160-0, 14958-3), eGFR (33959-3, 62238-1, 62239-9, 89996-2)
  - CPT (clinical lab codes specific to each test)
- **Proximity logic**: 4-day window for albumin+creatinine pair (inclusive on both ends: ±2 days from reference date)

#### Measurement Year Conventions
- Measurement period: January 1 – December 31
- **New in MY 2026**: Age stratification expanded to granular buckets (18–64, 65–75, 76–85) reflecting different comorbidity/frailty patterns
- Assessment must be current-year (no prior-year lookback for eGFR/uACR results)

#### Summary of Changes & Measure Drift
**MY 2026 HEDIS for QRS Changes**:
- Updated race/ethnicity stratification categories (OMB SPD 15 2024, US Core 6.1.0)
- **Age-specific exclusion criteria refined**: Separate frailty thresholds for age 66–80 vs 81+ (reflects KDIGO risk stratification practices)
- **NEW explicit coding**: LOINC codes for eGFR and uACR components added for clarity (addresses prior ambiguity in lab test identification)
- Measurement note clarified: Intent is to identify albumin+creatinine simultaneously (aligned with KDIGO 2024 update on CKD screening in diabetes)
- **QRS-specific note**: Race/ethnicity stratification NOT required for QRS reporting

---

### 4. Proportion of Days Covered: Statins (PQA)

**Measure ID**: PDC-STA  
**Measure Steward**: PQA (Pharmacy Quality Alliance)  
**QRS Source**: Listed in measure set; detailed specifications in Section 3.2 (PQA Measures)

#### Description
Percentage of persons with diabetes who are on statin therapy with medication possession ratio / proportion of days covered (PDC) ≥80% during the measurement period.

#### Eligible Population
- Persons prescribed statin medication (RxNorm codes for statin drug family)
- Continuous pharmacy benefit enrollment
- Diabetes identified by diagnosis or prior medication history

#### Numerator (Compliance Criteria)
- PDC for statin fills ≥80% during measurement period
- PDC = total days of drug supplied / total days in measurement period (accounting for medication gaps)

#### Value-Set & Code Logic
- **Code system**: RxNorm for statin class medications
- Calculation method: Proportion of days covered based on pharmacy claim fill dates and days supplied
- Threshold: 80% PDC (evidence-based threshold for cardiovascular risk reduction)

#### Key Notes
- Distinct from SPD-E (Statin Therapy for Patients with Diabetes, which measures initiation/continuation)
- Reflects adherence/persistence in ongoing therapy
- Impact: 2024 CMS assessment estimates health gains from 80%+ statin adherence exceed those of other diabetes metrics

---

### 5. Proportion of Days Covered: Diabetes All Class (PQA)

**Measure Steward**: PQA (Pharmacy Quality Alliance)  
**QRS Source**: Listed in measure set; detailed specifications in Section 3.2

#### Description
Percentage of persons with diabetes who have medication possession ratio / proportion of days covered (PDC) ≥80% for all diabetes medication classes combined during the measurement period.

#### Eligible Population
- Persons with diabetes diagnosis
- Prescribed any diabetes medication class (insulin, metformin, sulfonylureas, thiazolidinediones, DPP-4 inhibitors, GLP-1 agonists, SGLT2 inhibitors, etc.)
- Continuous pharmacy benefit enrollment

#### Numerator (Compliance Criteria)
- PDC for diabetes medications (any class, combined) ≥80% during measurement period
- Calculation accounts for gaps between fills and days supplied

#### Value-Set & Code Logic
- **Code system**: RxNorm for diabetes medication class codes
- Multi-class: Any diabetes medication qualifies
- Threshold: 80% PDC

---

## HEDIS Measures NOT in 2027 QRS Measure Set

The following diabetes-related HEDIS measures are part of the full HEDIS suite but were **not included** in the proposed 2027 QRS measure set (per Draft 2026 Call Letter):

### Blood Pressure Control for Patients With Diabetes (BPD-E)

**HEDIS Status**: Available in full HEDIS; NOT in 2027 QRS  
**From HEDIS Toolkit**: Persons 18–75 years with diabetes

#### Description
Percentage of persons with diabetes who had blood pressure adequately controlled (<140/90 mmHg) during the measurement period.

#### Population & Numerator
- **Age**: 18–75 years
- **Denominator**: Persons with diabetes diagnosis
- **Numerator**: Most recent BP during measurement period (both systolic AND diastolic) <140/90 mmHg
- **Exclusions**: Hospice, palliative care, frailty + advanced illness
- **Data collection**: Medical record review for actual BP readings (not derived)

#### Code Systems
- ICD-10-CM: Diabetes diagnoses, hypertension comorbidity
- CPT: Vital signs documentation (93000 series)
- LOINC: BP result codes

#### Note on Absence from QRS
- QRS includes "Blood Pressure Control for Patients With Hypertension (BPC-E)" but NOT diabetes-specific BPD
- Suggests QRS 2027 deemphasized diabetes-hypertension comorbidity measure in favor of EED, GSD, KED trio
- **Implication for demo**: BPD remains a valid HEDIS measure but would require separate implementation if targeting plan-level HEDIS compliance (not QRS)

---

### Statin Therapy for Patients With Diabetes (SPD-E)

**HEDIS Status**: Available in full HEDIS; NOT in 2027 QRS  
**From HEDIS Toolkit**: Persons 40–75 years with diabetes

#### Description
Percentage of persons 40–75 years with diabetes who are initiated on or continued on statin therapy during the measurement period.

#### Population & Numerator
- **Age**: 40–75 years (narrower than GSD/EED/KED at 18–75)
- **Denominator**: Persons with diabetes
- **Numerator**: ≥1 statin prescription (RxNorm) during measurement period OR prescription from prior year + refill during current year
- **Exclusions**: Similar to other diabetes measures (hospice, palliative, frailty + advanced illness); additional exclusion for contraindications to statin therapy
- **Data collection**: Administrative (pharmacy claims)

#### Code Systems
- ICD-10-CM: Diabetes diagnosis
- RxNorm: Statin drug codes (atorvastatin, simvastatin, rosuvastatin, pravastatin, lovastatin, fluvastatin)
- CPT: Procedure codes for lipid panel if supplemental verification

#### Time Window
- Initiation: First statin fill during measurement period
- Continuation: Prescription filled in prior year + ≥1 fill during current year

#### Note on Absence from QRS
- QRS replaced SPD with PDC-STA (Proportion of Days Covered: Statins), shifting focus from initiation to adherence/persistence
- **Clinical rationale**: PDC better reflects long-term cardiovascular risk reduction (ongoing adherence vs. initiation alone)
- **Implication for demo**: SPD available for HEDIS-only implementations; QRS tracks adherence via PDC instead

---

### Diabetes Screening for People With Schizophrenia or Bipolar Disorder Who Are Using Antipsychotic Medications (SSD)

**HEDIS Status**: Available in full HEDIS; NOT identified in 2027 QRS  
**From HEDIS Toolkit**: Priority Partners plan (specific to managed care); Persons 18–64 years

#### Description
Percentage of persons 18–64 years with schizophrenia or bipolar disorder who are on antipsychotic medication and received diabetes screening (fasting glucose or HbA1c test) during the measurement period.

#### Population & Numerator
- **Age**: 18–64 years
- **Denominator**: Persons with diagnosis of schizophrenia or bipolar disorder on antipsychotic medication (both criteria required)
- **Numerator**: ≥1 fasting glucose test OR ≥1 HbA1c test during measurement period
- **Exclusions**: Diabetes diagnosis, hospice, palliative care
- **Data collection**: Administrative (claims-based glucose/HbA1c tests and antipsychotic fills)

#### Code Systems
- ICD-10-CM: Schizophrenia (F20.x), bipolar disorder (F31.x, F32.x with bipolar specifier)
- CPT: Glucose test (82947), HbA1c test (83036)
- LOINC: Glucose (2345-7), HbA1c (4548-4, 17856-6)
- RxNorm: Antipsychotic medications (olanzapine, risperidone, quetiapine, etc.)

#### Clinical Rationale
- Metabolic syndrome risk elevated in persons with schizophrenia/bipolar + antipsychotic exposure
- Antipsychotics (especially atypical) associated with hyperglycemia and weight gain
- Early screening enables intervention to prevent incident diabetes

#### Note on Absence from QRS
- SSD is a niche measure for behavioral health population screening
- Not included in 2027 QRS measure set (may be considered speciality measure or for future inclusion)
- Available in HEDIS for plans serving this population

---

## Candidate Additional Measures for Demo

Based on diabetes care continuum and clinical guidelines, the following measures could enrich the demo's measure suite:

### 1. Medication Adherence for Diabetes Medications (MAD)

**Status**: HEDIS measure; not in 2027 QRS  
**Why valuable**: Complements GSD and SPD by measuring adherence to all diabetes medication classes (not just statins)  
**Population**: Adults 18+ with diabetes  
**Numerator**: Proportion of days covered ≥80% for diabetes medications  
**Code systems**: RxNorm (diabetes drug classes)  
**Relevance**: Bridges clinical outcome (GSD glycemic control) with medication adherence behavior; enables multi-layer ontology of treatment intensification

### 2. Controlling High Blood Pressure (CBP) — General Population

**Status**: HEDIS measure; IN 2027 QRS (page 72) but not diabetes-specific  
**Why valuable**: While BPD (diabetes-specific) not in QRS, CBP is; many diabetic patients in CBP denominator → enables comorbidity analysis  
**Population**: Adults 18–85 years with hypertension (any cause)  
**Numerator**: Most recent BP <140/90 mmHg  
**Code systems**: ICD-10-CM, CPT, LOINC  
**Relevance**: Allows stratification of diabetic subpopulation within CBP; enables HTN-DM2 care pathway analysis

### 3. Initiation and Engagement of Substance Use Disorder Treatment

**Status**: HEDIS measure; IN 2027 QRS  
**Why valuable**: Comorbidity lens; diabetes + SUD = complex care coordination  
**Population**: Persons with substance use disorder diagnosis  
**Numerator**: Treatment initiation within 14 days of diagnosis + engagement (≥2 visits within 30 days)  
**Code systems**: ICD-10-CM (SUD diagnoses), CPT (treatment codes)  
**Relevance**: Holistic patient phenotyping; enables multi-morbidity risk stratification

### 4. Advance Care Planning (ACP)

**Status**: HEDIS measure; IN 2027 QRS  
**Why valuable**: End-of-life and frailty considerations for older diabetic patients  
**Population**: Adults 66+ (especially with diabetes + advanced illness)  
**Numerator**: Documentation of advance directive or ACP discussion  
**Code systems**: CPT Category II codes (99497-99498 for ACP visits)  
**Relevance**: Complements GSD/KED in older population; enables value-based care (palliative vs. intensive management stratification)

### 5. Proportion of Days Covered: Renin-Angiotensin System Antagonists (PDC-RASA)

**Status**: PQA measure; IN 2027 QRS  
**Why valuable**: Kidney protection in diabetes; complements KED numerator (eGFR+uACR) with therapy adherence  
**Population**: Adults with diabetes or hypertension  
**Numerator**: PDC ≥80% for ACE inhibitor or ARB  
**Code systems**: RxNorm (RASA class codes)  
**Relevance**: Links KED structural finding (albuminuria via uACR) to therapeutic response (RASA adherence driving proteinuria reduction)

---

## ALLOCATION RECOMMENDATIONS

Mapping of fact-types to architectural components for demo implementation:

### A. RAG Corpus (Retrieval-Augmented Generation)

**Best fit for**:
- Full measure specifications (all sections above: denominator exclusions, numerator logic, coding guidance)
- Value-set code mappings (LOINC, ICD-10-CM, RxNorm families by measure)
- Clinical guidelines cited (ADA 2025, KDIGO updates)
- Change summaries & versioning notes (measure drift across MY 2025→2026)

**Why**: Specifications are text-heavy, multi-faceted, and benefit from semantic search and passage retrieval. Supports natural-language queries like "What makes a patient diabetic for KED?" or "Which codes identify statin therapy?"

**Implementation note**: Ingest this markdown + original PDF pages as reference corpus; index by measure + section (denominator, numerator, codes).

---

### B. Genie Ontology Pages (Knowledge Graph / Semantic Structure)

**Best fit for**:
- Measure definitions & relationships (e.g., GSD measures glycemic control; KED measures kidney function; SPD measures lipid therapy)
- Population hierarchies (age 18–75 for GSD/EED vs. 18–85 for KED; age 40–75 for SPD)
- Exclusion criteria (unified: hospice, palliative, frailty+advanced illness across all measures)
- Multi-component numerator logic (e.g., KED = eGFR AND uACR; not OR)
- Comorbidity networks (diabetes → hypertension → kidney disease → cardiovascular risk)

**Why**: Ontology excels at capturing hierarchical relationships, cardinality constraints (must-have components), and cross-measure dependencies. Enables questions like "Which measures apply to a 70-year-old with diabetes and ESRD?" (answers: GSD, EED only; KED excluded due to ESRD exclusion).

**Implementation note**: Model measures as entity types; populations & exclusions as properties; code families as relationships to value sets. Link BPD/SPD/SSD as "HEDIS-only" nodes (distinct from QRS measures).

---

### C. Metric-View Measure Engine

**Best fit for**:
- Numerator compliance logic (GSD >9.0% vs ≤9.0%; KED eGFR+uACR pair requirement)
- Time-window rules (measurement period, allowable enrollment gaps, service date proximity)
- Stratification dimensions (age cohorts, race/ethnicity; though QRS doesn't require ethnicity reporting)
- Denominator exclusion evaluations (date of death, hospice service dates, ESRD diagnosis dates)
- PDC calculations (Statins, Diabetes All Class, RASA)

**Why**: Metric views are optimized for row-by-row patient calculations with rule-based logic. Supports production-scale computation of rates, stratified breakdowns, and audit trails.

**Implementation note**: Implement each measure as a `metric_view` in Databricks SQL or Python. Handle edge cases (multiple assessments same date → use lowest; prior-year lookback for EED negative exams; 4-day albumin+creatinine window for KED).

---

### D. Value-Set & Measure-Engine Logic (Code System Mappings)

**Best fit for**:
- Explicit LOINC code assignments (EED: 71490-7 left eye retinopathy, 71491-5 right; KED: 33959-3 eGFR, 30315-0 urine albumin, 2160-0 urine creatinine)
- CPT code hierarchies (E/M codes for EED visit, vital sign codes for BP, lab codes for glucose/HbA1c)
- ICD-10-CM diagnosis hierarchies (Diabetes Value Set includes E10.x, E11.x, E13.x; not laboratory claims POS 81)
- RxNorm family groupings (Statin class: atorvastatin, simvastatin, rosuvastatin, pravastatin, lovastatin, fluvastatin)
- CPT Category II codes (3046F for HbA1c <9%, 3072F for negative retinal screening, 3077F/3080F for BP results)
- Modifier logic (CPT bilateral modifiers for eye enucleation; date-range specifications for prior-year lookback)

**Why**: Measure engines require precise code mappings and exclusion rules to operationalize specifications. Value sets ensure consistency across implementations and enable audit readiness.

**Implementation note**: Maintain a centralized code-system mapping table (measure → LOINC/CPT/ICD-10/RxNorm codes). For each measure, define:
1. Denominator identification codes (diabetes diagnosis codes)
2. Exclusion codes (ESRD, hospice service codes, palliative care, frailty indicators)
3. Numerator event codes (test results, procedure codes, medication fills)
4. Modifiers and time-window logic (e.g., "4 days or less" for albumin+creatinine pair)

---

### Summary Table: Allocation Decision Matrix

| Measure | RAG Corpus | Genie Page | Metric View | Code Mappings |
|---------|:----------:|:----------:|:-----------:|:-------------:|
| **EED** | Full specs ✓ | Population, exclusions, relationships | Numerator logic (exam types), age/enrollment | LOINC (retinopathy codes), CPT (exam codes), value sets |
| **GSD** | Full specs ✓ | Definitions (HbA1c vs GMI), comorbidity | >9.0% threshold, most-recent selection | LOINC (4548-4, 97506-0), CPT CAT-II (3046F) |
| **KED** | Full specs ✓ | Multi-component (eGFR+uACR), age stratification, ESRD exclusion | eGFR+uACR pairing, 4-day window, denominator age ranges | LOINC (eGFR, albumin, creatinine), CPT lab codes, ESRD codes |
| **PDC-STA** | Algorithm summary | Adherence measure class, threshold 80% | PDC calculation logic | RxNorm statin class |
| **PDC-DM** | Algorithm summary | Medication adherence, multi-class | PDC for all diabetes meds | RxNorm diabetes class |
| **BPD (HEDIS)** | Full specs ✓ | Comorbidity node, HEDIS-only flag | BP numerator <140/90, HTN exclusion mapping | BP codes, HTN diagnosis codes |
| **SPD (HEDIS)** | Full specs ✓ | Initiation vs. continuation, age 40–75, HEDIS-only flag | Statin fill & continuation logic, age filter | RxNorm statin class, diagnosis codes |
| **SSD (HEDIS)** | Full specs ✓ | Behavioral health–diabetes intersection, HEDIS-only flag | Antipsychotic + diabetes screening pairing | ICD-10-CM (schizophrenia, bipolar), RxNorm antipsychotics, glucose/HbA1c codes |

---

## Key Measure Drift Insights for Demo Narrative

1. **GSD Evolution: HbA1c → GMI** (MY 2026 change)
   - Reflects CGM adoption surge in diabetes care
   - GMI now equal-weight alternative to HbA1c for glycemic assessment
   - Implication: Measure engine must support dual-result logic; GMI calculation requires CGM data date-range documentation
   - **Demo angle**: "Real-time glycemic feedback (CGM) now credible for quality reporting"

2. **KED Aging Adjustment** (MY 2026 change)
   - Age-specific exclusion thresholds refined (66–80 vs 81+)
   - Reflects KDIGO 2024 CKD-in-diabetes risk stratification
   - Implication: Frailty + advanced illness exclusion lighter for 81+ (frailty alone sufficient), protecting very-elderly diabetics from underdetection
   - **Demo angle**: "Precision gerontology in kidney disease screening"

3. **QRS Diabetes Measure Trimming** (2027 vs. prior years)
   - BPD (Blood Pressure for Diabetics) → dropped in QRS; CBP (general BP) remains
   - SPD (Statin Therapy) → replaced by PDC-STA (adherence focus)
   - **Implication**: QRS emphasizes outcomes (GSD glycemic control, KED kidney health, EED eye health) over process measures (therapy initiation)
   - **Demo angle**: "Outcome-centric quality metrics; adherence matters more than initiation"

4. **Code System Modernization** (MY 2026 ongoing)
   - LOINC codes now explicit for EED (left/right eye retinopathy codes 71490-7, 71491-5)
   - KED eGFR LOINC expanded (89996-2 added for newer high-precision eGFR formulas)
   - GMI LOINC (97506-0) new in GSD
   - **Demo angle**: "LOINC standardization improves semantic interoperability; enables EHR data validation without manual review"

---

## References

1. CMS. 2027 Quality Rating System Measure Technical Specifications. September 2026. [Public Domain]
2. Johns Hopkins Health Plans. HEDIS Quality Measure Toolkit. [Referenced from toolkit]
3. American Diabetes Association Professional Practice Committee. 2025. Standards of Care in Diabetes. Diabetes Care 48(Suppl. 1).
4. National Kidney Foundation. 2012. KDOQI Clinical Practice Guideline for Diabetes and CKD: 2012 Update. Am J Kidney Dis.
5. NCQA. MY 2026 HEDIS for QRS Specifications. Healthcare Effectiveness Data and Information Set.
