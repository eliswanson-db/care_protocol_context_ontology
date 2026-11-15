# Unmanaged Pages in Clinical Domain (ECT): flagged, NOT modified

Generated 2026-11-15 after the first `scripts/sync_pages.py` runs. Every Page below was created outside the sync
(Genie Code bulk imports on 2026-10-30 and 2026-11-01). **None were edited, unpublished or deleted.** A read-only
copy of each is in `docs/ontology/pages_unmanaged_snapshot/`, so nothing is lost whatever you decide.

Managed now: 15 life-sciences + 14 HEDIS Pages (published, footer + content hash). **Blocked: 2 HEDIS Pages**
("Diabetes Cohort", "Measurement Year"): the API refuses a second PUBLISHED Page with the same title in a
domain, and older published Pages already hold those titles.

"Terms only here" = distinct words in the old Page that the managed Page doesn't contain (a rough signal of
content that would be lost; review the snapshot before deleting).

| # | Title | State | Updated | Kind | Managed counterpart | Terms only here | Recommendation |
|---|---|---|---|---|---|---|---|
| 1 | Diabetes Cohort | PUBLISHED | 2026-10-30 | duplicate_title | Diabetes Cohort | 15 | BLOCKING: delete or unpublish, then rerun sync (managed version can't be published while this is) |
| 2 | Measurement Year | PUBLISHED | 2026-10-30 | duplicate_title | Measurement Year | 11 | BLOCKING: delete or unpublish, then rerun sync (managed version can't be published while this is) |
| 3 | BPD — Blood Pressure Control for Patients With Diabetes | DRAFT | 2026-11-01 | duplicate_title | BPD — Blood Pressure Control for Patients With Diabetes | 0 | delete: unpublished draft of a Page now managed + published |
| 4 | Care Gap (Numerator, Denominator, MET / NOT_MET) | DRAFT | 2026-11-01 | duplicate_title | Care Gap (Numerator, Denominator, MET / NOT_MET) | 0 | delete: unpublished draft of a Page now managed + published |
| 5 | Diabetes Cohort | DRAFT | 2026-11-01 | duplicate_title | Diabetes Cohort | 0 | delete: unpublished draft of a Page now managed + published |
| 6 | Document Access Scope — Care Team vs Population Quality Analytics | DRAFT | 2026-11-01 | duplicate_title | Document Access Scope — Care Team vs Population Quality Analytics | 0 | delete: unpublished draft of a Page now managed + published |
| 7 | EED — Eye Exam for Patients With Diabetes | DRAFT | 2026-11-01 | duplicate_title | EED — Eye Exam for Patients With Diabetes | 0 | delete: unpublished draft of a Page now managed + published |
| 8 | HbA1c (A1c) — Hemoglobin A1c | DRAFT | 2026-11-01 | duplicate_title | HbA1c (A1c) — Hemoglobin A1c | 0 | delete: unpublished draft of a Page now managed + published |
| 9 | ICD-10 Subsumption & the Closure Table | DRAFT | 2026-11-01 | duplicate_title | ICD-10 Subsumption & the Closure Table | 0 | delete: unpublished draft of a Page now managed + published |
| 10 | KED — Kidney Health Evaluation for Patients With Diabetes | DRAFT | 2026-11-01 | duplicate_title | KED — Kidney Health Evaluation for Patients With Diabetes | 0 | delete: unpublished draft of a Page now managed + published |
| 11 | Measure Drift (Value-Set Versioning) | DRAFT | 2026-11-01 | duplicate_title | Measure Drift (Value-Set Versioning) | 0 | delete: unpublished draft of a Page now managed + published |
| 12 | Measurement Year | DRAFT | 2026-11-01 | duplicate_title | Measurement Year | 1 | delete: unpublished draft of a Page now managed + published |
| 13 | SPD — Statin Therapy for Patients With Diabetes | DRAFT | 2026-11-01 | duplicate_title | SPD — Statin Therapy for Patients With Diabetes | 0 | delete: unpublished draft of a Page now managed + published |
| 14 | SSD — Diabetes Screening for People With Schizophrenia or Bipolar Disorder Using Antipsychotics | DRAFT | 2026-11-01 | duplicate_title | SSD — Diabetes Screening for People With Schizophrenia or Bipolar Disorder Using Antipsychotics | 0 | delete: unpublished draft of a Page now managed + published |
| 15 | uACR — Urine Albumin-Creatinine Ratio | DRAFT | 2026-11-01 | duplicate_title | uACR — Urine Albumin-Creatinine Ratio | 0 | delete: unpublished draft of a Page now managed + published |
| 16 | Code Subsumption (Closure Table) | PUBLISHED | 2026-10-30 | no_managed_counterpart | — |  | decide: adopt into the repo as a managed source, or retire |
| 17 | Compliance Rate | PUBLISHED | 2026-10-30 | no_managed_counterpart | — |  | decide: adopt into the repo as a managed source, or retire |
| 18 | HEDIS | PUBLISHED | 2026-10-30 | no_managed_counterpart | — |  | decide: adopt into the repo as a managed source, or retire |
| 19 | BPD (Blood Pressure Control) | PUBLISHED | 2026-10-30 | older_version_of_topic | BPD — Blood Pressure Control for Patients With Diabetes | 10 | unpublish or delete: superseded by the managed Page; review 'terms only here' first |
| 20 | Care Gap | PUBLISHED | 2026-10-30 | older_version_of_topic | Care Gap (Numerator, Denominator, MET / NOT_MET) | 17 | unpublish or delete: superseded by the managed Page; review 'terms only here' first |
| 21 | EED (Eye Exam for Diabetes) | PUBLISHED | 2026-10-30 | older_version_of_topic | EED — Eye Exam for Patients With Diabetes | 14 | unpublish or delete: superseded by the managed Page; review 'terms only here' first |
| 22 | GSD (Glycemic Status Assessment) | PUBLISHED | 2026-10-30 | older_version_of_topic | GSD — Glycemic Status Assessment for Patients With Diabetes | 12 | unpublish or delete: superseded by the managed Page; review 'terms only here' first |
| 23 | HbA1c (Hemoglobin A1c) | PUBLISHED | 2026-10-30 | older_version_of_topic | HbA1c (A1c) — Hemoglobin A1c | 6 | unpublish or delete: superseded by the managed Page; review 'terms only here' first |
| 24 | KED (Kidney Health Evaluation) | PUBLISHED | 2026-10-30 | older_version_of_topic | KED — Kidney Health Evaluation for Patients With Diabetes | 17 | unpublish or delete: superseded by the managed Page; review 'terms only here' first |
| 25 | Measure Drift | PUBLISHED | 2026-10-30 | older_version_of_topic | Measure Drift (Value-Set Versioning) | 11 | unpublish or delete: superseded by the managed Page; review 'terms only here' first |
| 26 | SPD (Statin Therapy) | PUBLISHED | 2026-10-30 | older_version_of_topic | SPD — Statin Therapy for Patients With Diabetes | 14 | unpublish or delete: superseded by the managed Page; review 'terms only here' first |
| 27 | Value Set | PUBLISHED | 2026-10-30 | older_version_of_topic | Value Set (Code Segment) | 16 | unpublish or delete: superseded by the managed Page; review 'terms only here' first |
| 28 | eGFR (Estimated Glomerular Filtration Rate) | PUBLISHED | 2026-10-30 | older_version_of_topic | eGFR — Estimated Glomerular Filtration Rate | 12 | unpublish or delete: superseded by the managed Page; review 'terms only here' first |
| 29 | uACR (Urine Albumin-Creatinine Ratio) | PUBLISHED | 2026-10-30 | older_version_of_topic | uACR — Urine Albumin-Creatinine Ratio | 10 | unpublish or delete: superseded by the managed Page; review 'terms only here' first |

## Page ids and snapshots

| Title | Page | Snapshot |
|---|---|---|
| BPD (Blood Pressure Control) (PUBLISHED) | `pages/c460dae0-4e87-4176-bf48-c30e423c1966` | `bpd-blood-pressure-control__published__c460dae0.md` |
| BPD — Blood Pressure Control for Patients With Diabetes (DRAFT) | `pages/4d584784-6771-45f2-b69f-2585bcca785d` | `bpd-blood-pressure-control-for-patients-with-diabetes__draft__4d584784.md` |
| Care Gap (PUBLISHED) | `pages/4ae0fb88-3dc7-4b45-93e0-4491de7b9f08` | `care-gap__published__4ae0fb88.md` |
| Care Gap (Numerator, Denominator, MET / NOT_MET) (DRAFT) | `pages/2b0fb6b7-9689-4c0e-aefa-7af040f0beea` | `care-gap-numerator-denominator-met-not-met__draft__2b0fb6b7.md` |
| Code Subsumption (Closure Table) (PUBLISHED) | `pages/79503778-0e4b-4f80-af63-47bbca97d35e` | `code-subsumption-closure-table__published__79503778.md` |
| Compliance Rate (PUBLISHED) | `pages/7644609a-924b-416d-80f0-461e4ab5ea20` | `compliance-rate__published__7644609a.md` |
| Diabetes Cohort (PUBLISHED) | `pages/402e8af3-3e5a-4a46-aa36-22dcd8df5e64` | `diabetes-cohort__published__402e8af3.md` |
| Diabetes Cohort (DRAFT) | `pages/a9808138-3aba-4053-a080-e405d405721e` | `diabetes-cohort__draft__a9808138.md` |
| Document Access Scope — Care Team vs Population Quality Analytics (DRAFT) | `pages/a5bb74e9-015f-4883-bee6-16baea560dd5` | `document-access-scope-care-team-vs-population-quality-analyt__draft__a5bb74e9.md` |
| EED (Eye Exam for Diabetes) (PUBLISHED) | `pages/ffde4925-9200-4d93-96bc-7f1cb5cb860e` | `eed-eye-exam-for-diabetes__published__ffde4925.md` |
| EED — Eye Exam for Patients With Diabetes (DRAFT) | `pages/86f6b767-6407-4ced-91fa-95975a643cdf` | `eed-eye-exam-for-patients-with-diabetes__draft__86f6b767.md` |
| GSD (Glycemic Status Assessment) (PUBLISHED) | `pages/1045ab28-3390-4c2f-a056-381c1019c345` | `gsd-glycemic-status-assessment__published__1045ab28.md` |
| HEDIS (PUBLISHED) | `pages/dc04d5d6-2d8b-470e-95a4-4e81e297d7ad` | `hedis__published__dc04d5d6.md` |
| HbA1c (A1c) — Hemoglobin A1c (DRAFT) | `pages/ba2bd2b4-c6e3-4dad-a3e9-89e9946b11e4` | `hba1c-a1c-hemoglobin-a1c__draft__ba2bd2b4.md` |
| HbA1c (Hemoglobin A1c) (PUBLISHED) | `pages/af157d9d-48f0-4ecc-80f4-5110c59018e9` | `hba1c-hemoglobin-a1c__published__af157d9d.md` |
| ICD-10 Subsumption & the Closure Table (DRAFT) | `pages/19b0d253-a325-493e-ba7b-9ffb42c6ab53` | `icd-10-subsumption-the-closure-table__draft__19b0d253.md` |
| KED (Kidney Health Evaluation) (PUBLISHED) | `pages/2917aa8e-38e0-48a0-90b5-040c2931541a` | `ked-kidney-health-evaluation__published__2917aa8e.md` |
| KED — Kidney Health Evaluation for Patients With Diabetes (DRAFT) | `pages/9edbb1f7-62bd-405e-9bb6-fa9413b7d243` | `ked-kidney-health-evaluation-for-patients-with-diabetes__draft__9edbb1f7.md` |
| Measure Drift (PUBLISHED) | `pages/1c03bd0f-573e-4dc8-b03e-0c05bb4473cc` | `measure-drift__published__1c03bd0f.md` |
| Measure Drift (Value-Set Versioning) (DRAFT) | `pages/4ee5a80a-a4b7-47d5-93aa-f765943b8605` | `measure-drift-value-set-versioning__draft__4ee5a80a.md` |
| Measurement Year (PUBLISHED) | `pages/c84e5ba4-05b5-47b2-9126-370c57c488a9` | `measurement-year__published__c84e5ba4.md` |
| Measurement Year (DRAFT) | `pages/c4aacb75-c618-44b0-b93e-1d703604ea2f` | `measurement-year__draft__c4aacb75.md` |
| SPD (Statin Therapy) (PUBLISHED) | `pages/90137b0e-d1a0-4667-aea0-8aff1f754984` | `spd-statin-therapy__published__90137b0e.md` |
| SPD — Statin Therapy for Patients With Diabetes (DRAFT) | `pages/c8324591-625b-44db-9f8b-c57e9ba5dd7b` | `spd-statin-therapy-for-patients-with-diabetes__draft__c8324591.md` |
| SSD — Diabetes Screening for People With Schizophrenia or Bipolar Disorder Using Antipsychotics (DRAFT) | `pages/daf1c1e0-3a33-4c44-ab7a-fbdeec213255` | `ssd-diabetes-screening-for-people-with-schizophrenia-or-bipo__draft__daf1c1e0.md` |
| Value Set (PUBLISHED) | `pages/013c65de-c5b8-4fc8-824f-2d80cd5ca8ed` | `value-set__published__013c65de.md` |
| eGFR (Estimated Glomerular Filtration Rate) (PUBLISHED) | `pages/150dfd59-85b9-4efd-8014-bb170bfe626e` | `egfr-estimated-glomerular-filtration-rate__published__150dfd59.md` |
| uACR (Urine Albumin-Creatinine Ratio) (PUBLISHED) | `pages/fd610d42-21c5-48c3-8a29-dfc348e7c7b9` | `uacr-urine-albumin-creatinine-ratio__published__fd610d42.md` |
| uACR — Urine Albumin-Creatinine Ratio (DRAFT) | `pages/3a8d56e4-2f06-456e-8c90-0bbfe65ddba4` | `uacr-urine-albumin-creatinine-ratio__draft__3a8d56e4.md` |

## Words only in the old Page (first 8), for older versions

- **BPD (Blood Pressure Control)** (PUBLISHED): data, definition, detail, diabetes., gold, level, metric, reading.
- **Care Gap** (PUBLISHED): business, care., data, definition, drive, every, gap., holds
- **EED (Eye Exam for Diabetes)** (PUBLISHED): built, catches, definition, detail, gold, level, medications, metric
- **GSD (Glycemic Status Assessment)** (PUBLISHED): assessed, data, definition, detail, evidence, framing., gold, level
- **HbA1c (Hemoglobin A1c)** (PUBLISHED): data, definition, diabetes., feeds, included, set.
- **KED (Kidney Health Evaluation)** (PUBLISHED): code, data, definition, detail, diabetes., drift, example, examples
- **Measure Drift** (PUBLISHED): business, change., defined., edit, emits, examples, happens, list.
- **SPD (Statin Therapy)** (PUBLISHED): data, definition, detail, diabetes., gold, ingredients., level, metric
- **Value Set** (PUBLISHED): columns, data, definitions, each, exam, exams, hba1c, reference
- **eGFR (Estimated Glomerular Filtration Rate)** (PUBLISHED): concept., containing, data, definition, estimate, every, feeds, metric.
- **uACR (Urine Albumin-Creatinine Ratio)** (PUBLISHED): business, containing, creatinine., data, definition, feeds, gaps., lever
