"""Load the vendored life-sciences KB + approved rule registry into <catalog>.clinical_study_standards.

Bundle task (resources/jobs_life_sciences.yml: ls_bootstrap / load_standards). Overwrites only these
reference tables, never study data. Every table carries the release/registry version it came from.

Tables:
  kb_concept, kb_edge              the KB, direct assertions only (ADR-0025)
  standards_manifest               one row per pinned source artifact (publisher, release, checksum, terms)
  rule_registry                    registry_version + full YAML text (what the pipeline executes)
  rule_version                     endpoint rule versions, flattened (params JSON, review state, source)
  concept_class / class_root       concept classes and their roots / carve-outs (versioned)
  eligibility_criterion            criteria per eligibility rule version
  rule_document_support            rule -> document section links (registry source_section)
  *_hier                           adjacency tables for build_closure.py (mondo, medrt_class, mesh, bc)
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import yaml
from pyspark.sql import SparkSession


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--schema", default="clinical_study_standards")
    ap.add_argument("--src_dir", required=True, help="Workspace path of the repo's src/ directory")
    a = ap.parse_args()
    spark = SparkSession.builder.getOrCreate()
    tgt = f"{a.catalog}.{a.schema}"
    std = Path(a.src_dir) / "standards" / "life_sciences"
    reg_path = Path(a.src_dir) / "clinical_study" / "rules" / "registry.yaml"

    def write(name: str, rows: list[dict], schema: str, comment: str) -> None:
        df = spark.createDataFrame(rows, schema)
        df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{tgt}.{name}")
        spark.sql(f"COMMENT ON TABLE {tgt}.{name} IS {json.dumps(comment)}")
        print(f"  {tgt}.{name}: {df.count()} rows")

    with open(std / "kb_concept.csv", encoding="utf-8") as f:
        concepts = list(csv.DictReader(f))
    with open(std / "kb_edge.csv", encoding="utf-8") as f:
        edges = list(csv.DictReader(f))
    write(
        "kb_concept",
        concepts,
        "concept_id string, scheme string, code string, notation string, label string, definition string, "
        "concept_type string, release string",
        "Life-sciences KB concepts (MONDO, MED-RT, MeSH, RxNorm, CDISC CT, COSMoS BC/DSS, NCIt). Open "
        "subsets, pinned releases (standards_manifest). SYNTHETIC demo; validate before any non-demo use.",
    )
    write(
        "kb_edge",
        edges,
        "edge_id string, subject string, predicate string, object string, source_artifact string, "
        "authority string, release string",
        "Life-sciences KB edges: DIRECT assertions only (no transitive facts). cpl: predicates are demo "
        "extensions, never official CDISC. Same facts feed the graph, closures, RAG and Genie (ADR-0025).",
    )

    manifest = yaml.safe_load(open(std / "standards_manifest.yaml", encoding="utf-8"))
    write(
        "standards_manifest",
        [
            {
                k: str(art.get(k) or "")
                for k in (
                    "artifact_id",
                    "publisher",
                    "artifact_type",
                    "source_location",
                    "release_version",
                    "retrieved_at",
                    "checksum",
                    "license_or_terms_reference",
                    "access_method",
                    "local_storage_location",
                    "transformation_version",
                )
            }
            for art in manifest["artifacts"]
        ],
        "artifact_id string, publisher string, artifact_type string, source_location string, "
        "release_version string, retrieved_at string, checksum string, license_or_terms_reference string, "
        "access_method string, local_storage_location string, transformation_version string",
        "Pinned open-standards sources for the KB (no CDISC Library, MedDRA, SNOMED CT or ATC; ADR-0022).",
    )

    text = reg_path.read_text(encoding="utf-8")
    reg = yaml.safe_load(text)
    rv = reg["registry_version"]
    write(
        "rule_registry",
        [{"registry_version": rv, "yaml_text": text}],
        "registry_version string, yaml_text string",
        "Approved executable rule registry (full YAML). The pipeline runs ONLY review_state=approved rules. "
        "Approvals are seeded demo fixtures (approved_by=demo-fixture), not real human review.",
    )

    rows, sup = [], []
    for ep_id, ep in reg["endpoints"].items():
        for ver, r in ep["rule_versions"].items():
            rows.append(
                {
                    "registry_version": rv,
                    "study_id": ep["study"],
                    "endpoint_id": ep_id,
                    "rule_version": ver,
                    "endpoint_version": f"{ep_id}.{ver}",
                    "label": ep["label"],
                    "population": ep["population"],
                    "biomedical_concept": ep["biomedical_concept"],
                    "dataset_specialization": ep["dataset_specialization"],
                    "formula": ep["formula"],
                    "protocol_version": r["protocol_version"],
                    "sap_version": r["sap_version"],
                    "amends": r.get("amends"),
                    "baseline_method": r["baseline"]["method"],
                    "baseline_window_start": r["baseline"]["window_days"][0],
                    "baseline_window_end": r["baseline"]["window_days"][1],
                    "same_day_predose": r["baseline"]["same_day_predose"],
                    "target_offset_days": r["followup"]["target_offset_days"],
                    "window_half_width_days": r["followup"]["window_half_width_days"],
                    "tie_breaker": ",".join(r["followup"]["tie_breaker"]),
                    "params_json": json.dumps(r, sort_keys=True),
                    "review_state": r["review_state"],
                    "approved_by": r.get("approved_by"),
                    "approved_on": r.get("approved_on"),
                    "source_document": r["source_section"]["document"],
                    "source_section": r["source_section"]["section"],
                }
            )
            sup.append(
                {
                    "rule_id": f"{ep_id}.{ver}",
                    "rule_kind": "endpoint",
                    "document_id": r["source_section"]["document"],
                    "section": r["source_section"]["section"],
                    "registry_version": rv,
                }
            )
    write(
        "rule_version",
        rows,
        "registry_version string, study_id string, endpoint_id string, rule_version string, "
        "endpoint_version string, "
        "label string, population string, biomedical_concept string, dataset_specialization string, "
        "formula string, protocol_version string, sap_version string, amends string, baseline_method string, "
        "baseline_window_start int, baseline_window_end int, same_day_predose string, "
        "target_offset_days int, "
        "window_half_width_days int, tie_breaker string, params_json string, review_state string, "
        "approved_by string, approved_on string, source_document string, source_section string",
        "Endpoint rule versions (flattened). Study day: no day 0; windows inclusive; dates drive selection.",
    )

    studies, versions = [], []
    for sid, st in reg["studies"].items():
        studies.append(
            {
                "study_id": sid,
                "title": " ".join(st["title"].split()),
                "phase": st["phase"],
                "duration_weeks": st["duration_weeks"],
                "registry_version": rv,
            }
        )
        for v in st["study_versions"]:
            versions.append(
                {
                    "study_version_id": f"{sid}.P{v['protocol_version']}",
                    "study_id": sid,
                    "protocol_version": v["protocol_version"],
                    "sap_version": v["sap_version"],
                    "effective_date": v["effective_date"],
                    "amendment": v.get("amendment"),
                    "change_summary": v.get("change_summary"),
                    "documents": ",".join(v["documents"]),
                    "registry_version": rv,
                }
            )
    write(
        "study",
        studies,
        "study_id string, title string, phase string, duration_weeks int, registry_version string",
        "Synthetic studies (USDM Study). SYNTHETIC, illustrative; not any real trial.",
    )
    write(
        "study_version",
        versions,
        "study_version_id string, study_id string, protocol_version string, sap_version string, "
        "effective_date string, amendment int, change_summary string, documents string, "
        "registry_version string",
        "Protocol versions per study (USDM StudyVersion), effective by date, with amendment summaries.",
    )
    write(
        "analysis_population",
        [
            {"population_id": k, "label": p["label"], "definition": p["definition"], "registry_version": rv}
            for k, p in reg["populations"].items()
        ],
        "population_id string, label string, definition string, registry_version string",
        "Analysis populations (FAS, PPS) as defined in the registry.",
    )

    pe_by_label = {c["label"]: c["concept_id"] for c in concepts if c["scheme"] == "MEDRT"}
    cls, roots = [], []
    for cid, c in reg["concept_classes"].items():
        cls.append(
            {
                "class_id": cid,
                "label": c["label"],
                "scheme": c["scheme"],
                "extends": c.get("extends"),
                "definition_json": json.dumps(c, sort_keys=True),
                "registry_version": rv,
            }
        )
        for r in c.get("roots", []) + c.get("add_roots", []):
            roots.append(
                {"class_id": cid, "concept_id": r, "kind": "root", "reason": None, "registry_version": rv}
            )
        for x in c.get("exclude_roots", []):
            roots.append(
                {
                    "class_id": cid,
                    "concept_id": x["id"],
                    "kind": "exclude_root",
                    "reason": x["reason"],
                    "registry_version": rv,
                }
            )
        for x in c.get("excluded_ci_targets", []):
            roots.append(
                {
                    "class_id": cid,
                    "concept_id": x["target"],
                    "kind": "excluded_ci_target",
                    "reason": x["reason"].strip(),
                    "registry_version": rv,
                }
            )
        for x in c.get("member_of_classes", []):
            roots.append(
                {
                    "class_id": cid,
                    "concept_id": x,
                    "kind": "member_of_class",
                    "reason": None,
                    "registry_version": rv,
                }
            )
        for x in c.get("has_physiologic_effect", []):
            if x not in pe_by_label:
                raise SystemExit(f"{cid}: physiologic effect '{x}' not in the KB")
            roots.append(
                {
                    "class_id": cid,
                    "concept_id": pe_by_label[x],
                    "kind": "physiologic_effect",
                    "reason": None,
                    "registry_version": rv,
                }
            )
        if c.get("drug_class"):
            roots.append(
                {
                    "class_id": cid,
                    "concept_id": c["drug_class"],
                    "kind": "drug_class",
                    "reason": None,
                    "registry_version": rv,
                }
            )
    write(
        "concept_class",
        cls,
        "class_id string, label string, scheme string, extends string, "
        "definition_json string, registry_version string",
        "Versioned concept classes for eligibility / prohibited-medication rules. Membership is is_a* over "
        "the KB minus exclude_root subtrees (exclusion wins), never a flat code list. extends = inherits "
        "roots.",
    )
    write(
        "class_root",
        roots,
        "class_id string, concept_id string, kind string, reason string, registry_version string",
        "Roots, carve-outs and policy exceptions of each concept class (see concept_class).",
    )

    crit = []
    for rid, r in reg["eligibility"].items():
        for c in r["criteria"]:
            crit.append(
                {
                    "eligibility_rule_id": rid,
                    "study_id": r["study"],
                    "protocol_versions": ",".join(r["applies_to_protocol_versions"]),
                    "criterion_id": c["id"],
                    "criterion_type": c["type"],
                    "text": c["text"],
                    "class_id": c.get("class") or c.get("comorbidity_class"),
                    "params_json": json.dumps(c, sort_keys=True),
                    "review_state": r["review_state"],
                    "approved_by": r.get("approved_by"),
                    "registry_version": rv,
                }
            )
        sup.append(
            {
                "rule_id": rid,
                "rule_kind": "eligibility",
                "document_id": r["source_section"]["document"],
                "section": r["source_section"]["section"],
                "registry_version": rv,
            }
        )
    write(
        "eligibility_criterion",
        crit,
        "eligibility_rule_id string, study_id string, protocol_versions string, criterion_id string, "
        "criterion_type string, text string, class_id string, params_json string, review_state string, "
        "approved_by string, registry_version string",
        "Eligibility criteria per approved eligibility rule version (protocol version picks which applies).",
    )
    write(
        "rule_document_support",
        sup,
        "rule_id string, rule_kind string, document_id string, section string, registry_version string",
        "Which protocol/SAP section supports each executable rule version.",
    )

    by = {c["concept_id"]: c for c in concepts}
    hier = {
        "mondo_hier": ("rdfs:subClassOf", "MONDO", "is_a"),
        "medrt_class_hier": ("rdfs:subClassOf", "MEDRT", "is_a"),
        "mesh_hier": ("mesh:broaderDescriptor", "MESH", "broader"),
        "bc_hier": ("cosmos:parentBC", "COSMOS_BC", "parent_bc"),
    }
    for name, (pred, scheme, rel) in hier.items():
        rows = [
            {
                "code": e["subject"],
                "parent_code": e["object"],
                "name": by[e["subject"]]["label"],
                "relationship": rel,
            }
            for e in edges
            if e["predicate"] == pred and by[e["subject"]]["scheme"] == scheme
        ]
        # roots get a NULL-parent row so build_closure sees every node
        kids = {r["code"] for r in rows}
        parents = {r["parent_code"] for r in rows}
        rows += [
            {"code": p, "parent_code": None, "name": by[p]["label"], "relationship": rel}
            for p in sorted(parents - kids)
        ]
        write(
            name,
            rows,
            "code string, parent_code string, name string, relationship string",
            f"Adjacency ({pred}) for {scheme}, derived from kb_edge; input to build_closure.py.",
        )


if __name__ == "__main__":
    main()
