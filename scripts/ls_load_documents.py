"""Bundle task: load the synthetic study documents and the RAG corpus; render HTML/PDF; stage Pages.

Writes (overwrite, reference data only):
  clinical_study.doc_document, doc_section     parsed corpus (frontmatter + numbered sections)
  clinical_study.rule_assertion                extracted rule assertions + review state (never executed)
  clinical_study.rag_corpus                    document sections + KB reference entries + registry entries,
                                               one row per retrievable unit, with access scope and fact ids
Files:
  /Volumes/<cat>/clinical_study/documents/{md,html,pdf}/<document_id>.*
  /Volumes/<cat>/clinical_study/ontology_pages/*.md
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

from pyspark.sql import SparkSession


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--repo_dir", required=True, help="Workspace path of the bundle root")
    a = ap.parse_args()
    repo = Path(a.repo_dir)
    sys.path.insert(0, str(repo / "src"))
    from clinical_study import documents as dm
    from clinical_study.standardize import load_registry

    spark = SparkSession.builder.getOrCreate()
    t = f"{a.catalog}.clinical_study"
    docs = dm.load_corpus(repo / "docs/life_sciences/documents/corpus")
    reg = load_registry()
    concepts, edges = dm.load_kb(repo / "src/standards/life_sciences")
    asserts = dm.apply_reviews(dm.extract(docs), repo / "src/clinical_study/rules/assertion_reviews.yaml")

    def write(name, rows, schema, comment):
        df = spark.createDataFrame(rows, schema)
        df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{t}.{name}")
        spark.sql(f"COMMENT ON TABLE {t}.{name} IS {json.dumps(comment)}")
        print(f"  {t}.{name}: {df.count()} rows")

    write(
        "doc_document",
        [
            {
                k: (None if d.meta.get(k) is None else str(d.meta[k]))
                for k in (
                    "document_id",
                    "title",
                    "study_id",
                    "doc_type",
                    "version",
                    "status",
                    "effective_date",
                    "approval",
                    "access",
                )
            }
            for d in docs
        ],
        "document_id string, title string, study_id string, doc_type string, version string, status string, "
        "effective_date string, approval string, access string",
        "Synthetic study documents (protocols, amendments, SAPs, memo, mapping spec, note). SYNTHETIC. "
        "status=DRAFT documents are candidates only; approvals are demo fixtures.",
    )
    write(
        "doc_section",
        [
            {
                "section_id": s.section_id,
                "document_id": s.document_id,
                "section_number": s.section_number,
                "heading": s.heading,
                "level": s.level,
                "parent_number": s.parent_number,
                "text": s.text,
            }
            for d in docs
            for s in d.sections
        ],
        "section_id string, document_id string, section_number string, heading string, level int, "
        "parent_number string, text string",
        "Numbered sections of the synthetic documents; rules cite (document_id, section_number).",
    )
    write(
        "rule_assertion",
        [vars(x) for x in asserts],
        "assertion_id string, document_id string, section_id string, section_number string, "
        "assertion_type string, value string, evidence_text string, review_state string, rule_ref string, "
        "superseded_by string, reviewer string, reviewed_on string, review_note string, "
        "extractor_version string",
        "Rule assertions extracted deterministically from documents, with review state (approved / "
        "superseded / "
        "rejected / candidate). Reviews are demo fixtures. Only rule_version (approved) ever executes.",
    )
    rag = (
        dm.document_chunks(docs) + dm.reference_entries(concepts, edges) + dm.registry_entries(reg, concepts)
    )
    write(
        "rag_corpus",
        [
            {
                "entry_id": r["entry_id"],
                "source": r["source"],
                "title": r["title"],
                "text": r["text"],
                "concept_id": r.get("concept_id"),
                "scheme": r.get("scheme"),
                "document_id": r.get("document_id"),
                "document_status": r.get("document_status"),
                "access": r["access"],
                "edge_ids": r["edge_ids"],
                "inverse_edge_ids": r["inverse_edge_ids"],
                "demo_id": "life_sciences_clinical",
            }
            for r in rag
        ],
        "entry_id string, source string, title string, text string, concept_id string, scheme string, "
        "document_id string, document_status string, access string, edge_ids array<string>, "
        "inverse_edge_ids array<string>, demo_id string",
        "Clinical Study RAG corpus: document sections + one reference entry per KB concept (direct facts, "
        "both "
        "directions; edge_ids = the kb_edge facts stated) + registry rules/classes. Same facts as the graph "
        "(ADR-0025). access = study scope for document-level RLS.",
    )

    vol = Path(f"/Volumes/{a.catalog}/clinical_study/documents")
    from xhtml2pdf import pisa

    for sub in ("md", "html", "pdf"):
        (vol / sub).mkdir(parents=True, exist_ok=True)
    src = repo / "docs/life_sciences/documents/corpus"
    for d in docs:
        did = d.meta["document_id"]
        shutil.copyfile(src / f"{did}.md", vol / "md" / f"{did}.md")
        h = dm.to_html(d)
        (vol / "html" / f"{did}.html").write_text(h, encoding="utf-8")
        with open(vol / "pdf" / f"{did}.pdf", "wb") as f:
            if pisa.CreatePDF(h, dest=f).err:
                raise SystemExit(f"PDF render failed: {did}")
    print(f"  rendered {len(docs)} documents to {vol}/{{md,html,pdf}}")
    pages = Path(f"/Volumes/{a.catalog}/clinical_study/ontology_pages")
    pages.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in sorted((repo / "docs/life_sciences/pages").glob("*.md")):
        shutil.copyfile(p, pages / p.name)
        n += 1
    print(f"  staged {n} Page files (incl. README.md) to {pages}")


if __name__ == "__main__":
    main()
