---
document_id: CSL-DMS-v1.0
title: "Data mapping specification: EDC exports to SDTM-shaped datasets (CSL-A and CSL-B)"
study_id: null
doc_type: SPEC
version: "1.0"
status: APPROVED
effective_date: "2025-01-15"
approval: "demo-fixture (seeded; no real human approval)"
access: "all"
---
# Data mapping specification, version 1.0

SYNTHETIC DOCUMENT. The datasets are SDTM-shaped for a narrow scope; they are not conformant, submission-ready SDTM.

## 2 Vital signs (VS)

### 2.1 Body weight

EDC weight records map to VS with VSTESTCD = WEIGHT and VSTEST = Weight (CDISC CT codelists C66741 / C67153, NCIt
C25208). The record represents the CDISC biomedical concept Body Weight (C81328), and its shape follows the COSMoS
SDTM dataset specialization WEIGHT, which requires VSTESTCD, VSTEST, VSORRES, VSORRESU and VSDTC and allows
VSORRESU values LB, g and kg.

### 2.2 Units

The raw unit keyed at the site maps to a CDISC CT VSRESU submission value: kg, KG, Kg and kgs map to kg; lb, lbs
and Lb map to LB; g maps to g. Any other raw unit (for example st, stone) is kept as recorded, flagged as unmapped,
and is not valid for the endpoint. VSSTRESN holds the weight in kg (LB × 0.45359237; g × 0.001). The raw unit and
the mapping status are kept on every record for lineage.

### 2.3 Study day

VSDY is computed from VSDTC and the reference start date with no day 0. Partial dates give no study day.

## 3 Medical history and concomitant medications

Medical history terms are coded to MONDO disease concepts and concomitant medications to RxNorm ingredients.
MedDRA and WHODrug are not used (licensed); this is a documented deviation from usual SDTM practice. The codes are
carried in the demo-extension columns CPL_MONDO_ID and CPL_RXNORM_ID.

## 4 Lineage

Every standardized record carries its EDC source record id and source file, so any endpoint result can be traced
back to the exact raw rows.
