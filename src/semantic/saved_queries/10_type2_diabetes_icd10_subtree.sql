-- name: ICD-10 codes under type 2 diabetes (E11)
-- description: Every ICD-10-CM code subsumed by E11 (type 2 diabetes mellitus) and its depth below E11, from the materialized closure.
-- Cohort membership is by subsumption: a patient is diabetic when any diagnosis is a descendant of E10, E11 or E13.
-- icd10_closure holds every (ancestor, descendant) pair, so this is one equality filter, no recursion.
SELECT descendant_code, descendant_name, depth
FROM eli_test_classic_catalog.care_protocol_terminology.icd10_closure
WHERE ancestor_code = 'E11'
ORDER BY depth, descendant_code
