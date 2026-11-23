"""Synthetic study documents -> sections, HTML, candidate rule assertions, and RAG chunks.

Governed rule flow (prompt §9): document -> parsed section -> candidate assertion -> review state -> approved rule.
The extractor is deterministic (regex over prose), so it is testable. Review decisions live in
src/clinical_study/rules/assertion_reviews.yaml. Only the registry's approved rule versions ever execute; an
assertion, whatever its state, is explanation and evidence, never calculation input.

RAG holds the documents only (loaded into Lakebase by scripts/lakebase_rag_corpus.py), as for HEDIS.
"""

from __future__ import annotations

import csv
import html
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
STD = HERE.parent / "standards" / "life_sciences"
REPO = HERE.parents[1]
CORPUS = REPO / "docs" / "life_sciences" / "documents" / "corpus"
EXTRACTOR_VERSION = "1.0.0"
INVERSE_CAP = 25


# --------------------------------------------------------------------------------------------- parsing
@dataclass
class Section:
    section_id: str
    document_id: str
    section_number: str
    heading: str
    level: int
    text: str
    parent_number: str | None


@dataclass
class Document:
    meta: dict
    body: str
    sections: list[Section] = field(default_factory=list)


HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
NUMBERED = re.compile(r"^(\d+(?:\.\d+)*)\s+(.*)$")


def parse(path: Path) -> Document:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        raise ValueError(f"{path.name}: missing frontmatter")
    fm, body = raw[4:].split("\n---\n", 1)
    meta = yaml.safe_load(fm)
    doc = Document(meta, body)
    did = meta["document_id"]
    cur: dict | None = None
    lines: list[str] = []

    def flush():
        if cur is not None:
            doc.sections.append(Section(text="\n".join(lines).strip(), **cur))

    for line in body.splitlines():
        m = HEADING.match(line)
        if m:
            flush()
            level, title = len(m.group(1)), m.group(2).strip()
            n = NUMBERED.match(title)
            num, heading = (n.group(1), n.group(2)) if n else ("0", title)
            parent = num.rsplit(".", 1)[0] if "." in num else None
            cur = {
                "section_id": f"{did}__s{num}",
                "document_id": did,
                "section_number": num,
                "heading": heading,
                "level": level,
                "parent_number": parent,
            }
            lines = []
        else:
            lines.append(line)
    flush()
    ids = [s.section_id for s in doc.sections]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path.name}: duplicate section numbers")
    return doc


def load_corpus(corpus: Path = CORPUS) -> list[Document]:
    return [parse(p) for p in sorted(corpus.glob("*.md"))]


# --------------------------------------------------------------------------------------------- HTML
# Glyphs the built-in PDF fonts cannot draw. Dropping them silently would corrupt a formula
# ("follow-up − baseline" -> "follow-up  baseline"), so they're mapped to ASCII for HTML/PDF only.
PDF_SAFE = {"\u2212": "-", "\u2265": ">=", "\u2264": "<=", "\u2192": "->", "\u2026": "..."}


def _inline(s: str) -> str:
    for k, v in PDF_SAFE.items():
        s = s.replace(k, v)
    s = html.escape(s)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)


def to_html(doc: Document) -> str:
    """Small, dependency-free renderer for the constrained markdown used in the corpus."""
    out, para, lst, table = [], [], None, []

    def end_para():
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>")
            para.clear()

    def end_list():
        nonlocal lst
        if lst:
            tag, items = lst
            out.append(f"<{tag}>" + "".join(f"<li>{_inline(i)}</li>" for i in items) + f"</{tag}>")
            lst = None

    def end_table():
        if table:
            rows = [
                [c.strip() for c in r.strip().strip("|").split("|")]
                for r in table
                if not re.match(r"^\|[-| ]+\|$", r)
            ]
            head, rest = rows[0], rows[1:]
            out.append(
                "<table border='1' cellpadding='4'><tr>"
                + "".join(f"<th>{_inline(h)}</th>" for h in head)
                + "</tr>"
                + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in rest)
                + "</table>"
            )
            table.clear()

    for line in doc.body.splitlines():
        if line.startswith("|"):
            end_para()
            end_list()
            table.append(line)
            continue
        end_table()
        m = HEADING.match(line)
        if m:
            end_para()
            end_list()
            out.append(f"<h{len(m.group(1))}>{_inline(m.group(2))}</h{len(m.group(1))}>")
        elif re.match(r"^\d+\.\s", line):
            end_para()
            if not lst or lst[0] != "ol":
                end_list()
                lst = ("ol", [])
            lst[1].append(re.sub(r"^\d+\.\s", "", line))
        elif line.startswith("- "):
            end_para()
            if not lst or lst[0] != "ul":
                end_list()
                lst = ("ul", [])
            lst[1].append(line[2:])
        elif line.startswith("   ") and lst:
            lst[1][-1] += " " + line.strip()
        elif not line.strip():
            end_para()
            end_list()
        else:
            end_list()
            para.append(line.strip())
    end_para()
    end_list()
    end_table()
    m = doc.meta
    banner = (
        "<p style='color:#a00'><b>SYNTHETIC</b> · Clinical Study Context &amp; Evidence Lab · "
        f"{html.escape(m['document_id'])} · status {html.escape(str(m['status']))}</p>"
    )
    return (
        f"<html><head><meta charset='utf-8'><title>{html.escape(m['title'])}</title>"
        "<style>body{font-family:Helvetica,Arial,sans-serif;font-size:10pt} th{background:#eee}</style>"
        f"</head><body>{banner}{''.join(out)}</body></html>"
    )


# --------------------------------------------------------------------------------------------- assertions
PATTERNS = [
    ("FOLLOWUP_WINDOW_HALF_WIDTH", re.compile(r"±(\d+) days (?:of|around) the (?:Week 24 )?target date")),
    ("TARGET_OFFSET_DAYS", re.compile(r"reference date plus (\d+) days")),
    ("BASELINE_WINDOW", re.compile(r"from study day (-\d+) to study day (-\d+)")),
    ("BASELINE_METHOD", re.compile(r"baseline is the (last|mean)\b")),
    ("TIE_BREAKER", re.compile(r"equally close, the (later|earlier) date is used")),
    ("WINDOW_MENTION", re.compile(r"windows? of ±(\d+) days")),
    ("VISIT_SCHEDULING_WINDOW", re.compile(r"\| WEEK 24 \| (\d+) \| (-?\d+) to (-?\d+) \|")),
]


@dataclass
class Assertion:
    assertion_id: str
    document_id: str
    section_id: str
    section_number: str
    assertion_type: str
    value: str
    evidence_text: str
    review_state: str = "candidate"
    rule_ref: str | None = None
    superseded_by: str | None = None
    reviewer: str | None = None
    reviewed_on: str | None = None
    review_note: str | None = None
    extractor_version: str = EXTRACTOR_VERSION


def extract(docs: list[Document]) -> list[Assertion]:
    out = []
    for d in docs:
        for s in d.sections:
            text = " ".join((s.text or "").split())  # prose wraps across lines
            n = 0
            for kind, pat in PATTERNS:
                for m in pat.finditer(text):
                    n += 1
                    val = ",".join(m.groups())
                    a, b = max(0, m.start() - 120), min(len(text), m.end() + 80)
                    out.append(
                        Assertion(
                            f"{s.section_id}#a{n}",
                            d.meta["document_id"],
                            s.section_id,
                            s.section_number,
                            kind,
                            val,
                            " ".join(text[a:b].split()),
                        )
                    )
    return out


def apply_reviews(assertions: list[Assertion], reviews_path: Path) -> list[Assertion]:
    """Attach review decisions. Unmatched assertions stay 'candidate'. A review that matches nothing is an error
    (a stale review must not silently approve something else)."""
    reviews = yaml.safe_load(reviews_path.read_text(encoding="utf-8"))["reviews"]
    used = set()
    for a in assertions:
        for i, r in enumerate(reviews):
            m = r["match"]
            if (m["document"], str(m["section"]), m["type"], str(m["value"])) == (
                a.document_id,
                a.section_number,
                a.assertion_type,
                a.value,
            ):
                a.review_state, a.rule_ref = r["state"], r.get("rule_ref")
                a.superseded_by, a.reviewer = r.get("superseded_by"), r.get("reviewer")
                a.reviewed_on, a.review_note = r.get("reviewed_on"), r.get("note")
                used.add(i)
    stale = [r["match"] for i, r in enumerate(reviews) if i not in used]
    if stale:
        raise ValueError(f"reviews match no extracted assertion: {stale}")
    return assertions


def registry_value(registry: dict, rule_ref: str, assertion_type: str) -> str | None:
    """The approved registry parameter an assertion claims to state (for the agreement check)."""
    ep_id, rv = rule_ref.rsplit(".", 1)
    r = registry["endpoints"][ep_id]["rule_versions"][rv]
    return {
        "FOLLOWUP_WINDOW_HALF_WIDTH": str(r["followup"]["window_half_width_days"]),
        "TARGET_OFFSET_DAYS": str(r["followup"]["target_offset_days"]),
        "BASELINE_WINDOW": ",".join(str(x) for x in r["baseline"]["window_days"]),
        "BASELINE_METHOD": r["baseline"]["method"],
        "TIE_BREAKER": r["followup"]["tie_breaker"][0].split("_")[0],
    }.get(assertion_type)


def load_kb(std: Path = STD) -> tuple[list[dict], list[dict]]:
    """The vendored knowledge base (kb_concept.csv, kb_edge.csv)."""
    with open(std / "kb_concept.csv", encoding="utf-8") as f:
        concepts = list(csv.DictReader(f))
    with open(std / "kb_edge.csv", encoding="utf-8") as f:
        edges = list(csv.DictReader(f))
    return concepts, edges


def document_chunks(docs: list[Document]) -> list[dict]:
    rows = []
    for d in docs:
        m = d.meta
        for s in d.sections:
            if not s.text:
                continue
            rows.append(
                {
                    "entry_id": s.section_id,
                    "concept_id": None,
                    "scheme": "DOCUMENT",
                    "title": f"{m['document_id']} §{s.section_number} {s.heading}",
                    "text": f"{m['title']} (status {m['status']}). Section {s.section_number} {s.heading}.\n{s.text}",
                    "edge_ids": [],
                    "inverse_edge_ids": [],
                    "source": "document",
                    "access": m["access"],
                    "document_id": m["document_id"],
                    "document_status": m["status"],
                }
            )
    return rows
