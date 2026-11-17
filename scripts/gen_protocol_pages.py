"""Generate the HEDIS Page that states the care-protocol knowledge edges (ADR-0025 parity for the HEDIS lab).

protocol_edges.csv is the source the graph (Ontobricks) and the closure/edge tables are built from. This Page states
exactly those facts in prose for Genie Ontology, so all approaches hold the same rules:
    .venv/bin/python -I scripts/gen_protocol_pages.py   # rewrites docs/ontology/pages/care-protocol-rules.md
tests/test_hedis_context_parity.py fails if the Page is stale.
"""

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERM = ROOT / "src/terminology"
OUT = ROOT / "docs/ontology/pages/care-protocol-rules.md"

NAMES = {"DRUGCLASS-STATIN": "Statins", "DRUGCLASS-ACE": "ACE inhibitors", "DRUGCLASS-ARB": "ARBs",
         "DRUGCLASS-SGLT2": "SGLT2 inhibitors", "DRUGCLASS-BIGUANIDE": "Metformin (biguanide)",
         "SPD": "the SPD measure (statin therapy, ages 40-75)", "ALBUMINURIA": "albuminuria",
         "GLYCEMIC": "glucose lowering", "LP-HBA1C": "HbA1c (LOINC part LP-HBA1C)", "LP-EGFR": "eGFR (LP-EGFR)",
         "LP-UACR": "uACR (LP-UACR)", "LP-SBP": "systolic blood pressure (LP-SBP)",
         "LP-DBP": "diastolic blood pressure (LP-DBP)", "GSD": "GSD", "KED": "KED", "BPD": "BPD"}
THRESH = {"eGFR_LT_30": "eGFR below 30 mL/min/1.73m²", "eGFR_LT_20": "eGFR below 20 mL/min/1.73m²",
          "uACR_GTE_30": "uACR of 30 mg/g or more", "systolic_lt_140": "systolic below 140 mmHg",
          "diastolic_lt_90": "diastolic below 90 mmHg", "a1c_good_lt_8": "good control: A1c below 8%",
          "a1c_poor_gt_9": "poor control: A1c above 9%"}
VERB = {"recommendedFor": "are recommended for", "firstLineFor": "is first-line for",
        "contraindicatedWith": "are contraindicated with", "contraindicatedWhen": "are contraindicated when",
        "monitoredBy": "is monitored by", "definedBy": "is defined by", "hasThreshold": "has the threshold"}


def name(code: str, vs: dict[str, str]) -> str:
    if code in NAMES:
        return NAMES[code]
    if code in THRESH:
        return THRESH[code]
    return f"{vs.get(code, code)} (value set `{code}`)"


def build() -> str:
    with open(TERM / "value_sets_demo.csv", encoding="utf-8") as f:
        # short lower-case label: drop "[MY...]" and "(...)" qualifiers
        vs = {r["segment_id"]: re.sub(r"\s*[\[(].*$", "", r["segment_name"]).lower() for r in csv.DictReader(f)}
    with open(TERM / "protocol_edges.csv", encoding="utf-8") as f:
        edges = list(csv.DictReader(f))
    groups = [("Drug-class recommendations", ("recommendedFor", "firstLineFor")),
              ("Contraindications", ("contraindicatedWith", "contraindicatedWhen")),
              ("What each measure is monitored by", ("monitoredBy",)),
              ("Thresholds and definitions", ("hasThreshold", "definedBy"))]
    body = [
        "---",
        "name: Care-protocol rules (drug classes, contraindications, thresholds)",
        "synonyms: [care protocol, protocol rules, contraindication, recommended for, first-line, SGLT2, ACE, ARB, "
        "statin, metformin, albuminuria, threshold, monitored by]",
        "domain: Clinical Domain",
        "owner: eli.swanson@databricks.com",
        "related_assets:",
        "  - eli_test_classic_catalog.care_protocol_terminology.protocol_edges",
        "  - eli_test_classic_catalog.care_protocol_terminology.value_set_segment",
        "---",
        "",
        "These are the care-protocol knowledge edges, one sentence per edge. They are the same facts the knowledge graph",
        "and `protocol_edges` hold: this Page is generated from `src/terminology/protocol_edges.csv` "
        "(`scripts/gen_protocol_pages.py`), so it can't drift from them. Synthetic demo protocol; not clinical guidance.",
        "",
    ]
    for title, preds in groups:
        rows = [e for e in edges if e["predicate"] in preds]
        if not rows:
            continue
        body += [f"## {title}", ""]
        for e in rows:
            s, o = name(e["subject"], vs), name(e["object"], vs)
            verb = VERB[e["predicate"]]
            if e["subject"] in ("GSD", "KED", "BPD", "ALBUMINURIA", "DRUGCLASS-BIGUANIDE") and verb.startswith("are "):
                verb = verb.replace("are ", "is ", 1)
            line = f"{s} {verb} {o}"
            body.append(f"- {line[0].upper() + line[1:]}. *(protocol section {e['source']})*")
        body.append("")
    body.append("For the A1c recheck rule (Protocol Step 3) see the Page *Protocol Step 3 — A1c recheck within 90 days*.")
    return "\n".join(body) + "\n"


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print("wrote", OUT.relative_to(ROOT))
