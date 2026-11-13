"""Synthetic study documents -> sections, HTML, candidate rule assertions, and the RAG reference corpus.

Governed rule flow (prompt §9): document -> parsed section -> candidate assertion -> review state -> approved rule.
The extractor is deterministic (regex over prose), so it is testable. Review decisions live in
src/clinical_study/rules/assertion_reviews.yaml. Only the registry's approved rule versions ever execute; an
assertion, whatever its state, is explanation and evidence, never calculation input.

The reference corpus (ADR-0025) states every KB fact in sentences: one entry per concept, its direct edges in both
directions, and each entry lists the kb_edge ids it expresses. No transitive facts are written.
"""

from __future__ import annotations

import csv
import html
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CORPUS = REPO / "docs" / "life_sciences" / "documents" / "corpus"
STD = HERE.parent / "standards" / "life_sciences"
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


# --------------------------------------------------------------------------------------------- reference corpus
PRED_PHRASE = {
    "rdfs:subClassOf": ("is a", "has subtype"),
    "skos:exactMatch": ("is an exact match for", "is an exact match for"),
    "oboInOwl:hasDbXref": ("has a database cross-reference to", "is cross-referenced from"),
    "cpl:curatedEquivalent": (
        "is curated as equivalent (demo extension) to",
        "is curated as equivalent (demo extension) to",
    ),
    "mesh:broaderDescriptor": ("has broader MeSH descriptor", "has narrower MeSH descriptor"),
    "mesh:headingMappedTo": ("is indexed under MeSH descriptor", "has supplementary concept record"),
    "mesh:conceptOf": ("is a concept of MeSH record", "has MeSH concept"),
    "medrt:memberOf": ("is a member of drug class", "has member drug"),
    "medrt:has_MoA": ("has mechanism of action", "is the mechanism of action of"),
    "medrt:has_PE": ("has physiologic effect", "is a physiologic effect of"),
    "medrt:has_TC": ("has therapeutic category", "is the therapeutic category of"),
    "medrt:CI_with": ("is contraindicated with condition", "is a contraindication for"),
    "medrt:CI_MoA": ("is contraindicated with mechanism", "is a contraindicated mechanism for"),
    "medrt:CI_PE": ("is contraindicated with physiologic effect", "is a contraindicated effect for"),
    "medrt:may_treat": ("may treat", "may be treated by"),
    "medrt:may_prevent": ("may prevent", "may be prevented by"),
    "cdisc:inCodelist": ("is a term in codelist", "has term"),
    "cdisc:nciConcept": ("has NCIt concept", "is the NCIt concept of CDISC term"),
    "cosmos:specializes": ("is a dataset specialization of biomedical concept", "has dataset specialization"),
    "cosmos:hasVariableBinding": ("has variable binding", "is a variable binding of"),
    "cosmos:constrains": ("constrains SDTM variable", "is constrained by"),
    "cosmos:usesCodelist": ("uses codelist", "is used by variable binding"),
    "cosmos:allowedValue": ("allows value", "is an allowed value of"),
    "cosmos:assignedValue": ("assigns value", "is the assigned value of"),
    "cosmos:inDomain": ("is in SDTM domain", "contains variable"),
    "cosmos:ncitCode": ("has NCIt code", "is the NCIt code of biomedical concept"),
    "cosmos:parentBC": ("has parent biomedical concept", "has child biomedical concept"),
}
TYPE_NAME = {
    "MONDO": "Disease (MONDO)",
    "RXNORM": "Drug ingredient (RxNorm)",
    "MEDRT": "Drug class (MED-RT)",
    "MESH": "MeSH record",
    "MESH_SCR": "MeSH supplementary concept record",
    "NCIT": "NCIt concept",
    "ICD10CM": "ICD-10-CM code",
    "CDISC_CT": "CDISC controlled terminology",
    "COSMOS_BC": "CDISC biomedical concept",
    "COSMOS_DSS": "CDISC SDTM dataset specialization",
    "SDTM_VAR": "SDTM",
}


def load_kb(std: Path = STD) -> tuple[list[dict], list[dict]]:
    with open(std / "kb_concept.csv", encoding="utf-8") as f:
        concepts = list(csv.DictReader(f))
    with open(std / "kb_edge.csv", encoding="utf-8") as f:
        edges = list(csv.DictReader(f))
    return concepts, edges


def reference_entries(concepts: list[dict], edges: list[dict]) -> list[dict]:
    by = {c["concept_id"]: c for c in concepts}
    out_e: dict[str, list[dict]] = {}
    in_e: dict[str, list[dict]] = {}
    for e in edges:
        out_e.setdefault(e["subject"], []).append(e)
        in_e.setdefault(e["object"], []).append(e)

    def name(cid: str) -> str:
        c = by[cid]
        return f"{c['label'] or c['code']} ({cid})"

    rows = []
    for cid in sorted(by):
        c = by[cid]
        lines = [f"{TYPE_NAME.get(c['scheme'], c['scheme'])}: {name(cid)}. Source release: {c['release']}."]
        if c["notation"]:
            lines.append(f"Notation / submission value: {c['notation']}.")
        if c["definition"]:
            lines.append(f"Definition: {c['definition']}")
        ids = []
        for e in sorted(out_e.get(cid, []), key=lambda x: (x["predicate"], x["object"])):
            fwd = PRED_PHRASE[e["predicate"]][0]
            extra = f" [authority: {e['authority']}]" if e["authority"] else ""
            lines.append(f"{name(cid)} {fwd} {name(e['object'])}{extra}.")
            ids.append(e["edge_id"])
        inv = sorted(in_e.get(cid, []), key=lambda x: (x["predicate"], x["subject"]))
        for e in inv[:INVERSE_CAP]:
            lines.append(f"{name(cid)} {PRED_PHRASE[e['predicate']][1]} {name(e['subject'])}.")
        if len(inv) > INVERSE_CAP:
            lines.append(
                f"({len(inv) - INVERSE_CAP} more incoming relations are stated in their own entries.)"
            )
        rows.append(
            {
                "entry_id": f"KB::{cid}",
                "concept_id": cid,
                "scheme": c["scheme"],
                "title": name(cid),
                "text": "\n".join(lines),
                "edge_ids": ids,
                "inverse_edge_ids": [e["edge_id"] for e in inv[:INVERSE_CAP]],
                "source": "kb",
                "access": "all",
            }
        )
    return rows


def registry_entries(registry: dict, concepts: list[dict]) -> list[dict]:
    """Rules and classes as reference entries (the same facts the graph and Genie read from the registry tables)."""
    by = {c["concept_id"]: c for c in concepts}
    lab = lambda x: f"{by[x]['label']} ({x})" if x in by else x  # noqa: E731
    rows = []
    for cid, c in registry["concept_classes"].items():
        t = [f"Concept class {cid}: {c['label']} (registry {registry['registry_version']})."]
        if c.get("extends"):
            t.append(f"{cid} extends {c['extends']} and inherits its roots.")
        for r in c.get("roots", []) + c.get("add_roots", []):
            t.append(
                f"{cid} has root {lab(r)}; the root and every concept under it (is a, any depth) are members."
            )
        for r in c.get("exclude_roots", []):
            t.append(f"{cid} excludes root {lab(r['id'])}: {r['reason']}. Exclusion wins over membership.")
        for r in c.get("excluded_ci_targets", []):
            t.append(
                f"{cid} ignores contraindication target {lab(r['target'])}: {' '.join(r['reason'].split())}"
            )
        for r in c.get("member_of_classes", []):
            t.append(f"{cid} includes every drug that is a member of drug class {lab(r)}.")
        for r in c.get("has_physiologic_effect", []):
            t.append(f"{cid} includes every drug with physiologic effect {r}.")
        if c.get("drug_class"):
            t.append(
                f"{cid} is defined over drug class {lab(c['drug_class'])}; policy: {c.get('class_policy')}."
            )
        if c.get("cpl_derivation"):
            t.append(" ".join(c["cpl_derivation"].split()))
        if c.get("lookback_days_before_screening"):
            t.append(f"Lookback: {c['lookback_days_before_screening']} days before screening.")
        rows.append(
            {
                "entry_id": f"REG::class::{cid}",
                "concept_id": cid,
                "scheme": "REGISTRY",
                "title": c["label"],
                "text": "\n".join(t),
                "edge_ids": [],
                "inverse_edge_ids": [],
                "source": "registry",
                "access": "all",
            }
        )
    for ep_id, ep in registry["endpoints"].items():
        for rv, r in ep["rule_versions"].items():
            b, f = r["baseline"], r["followup"]
            t = [
                f"Endpoint rule {ep_id}.{rv} ({ep['label']}), study {ep['study']}, protocol {r['protocol_version']}, "
                f"SAP {r['sap_version']}, review state {r['review_state']} (approved_by {r.get('approved_by')}).",
                f"Baseline: {b['method']} valid weight, study days {b['window_days'][0]} to {b['window_days'][1]}; "
                f"same-day pre-dose policy {b['same_day_predose']}.",
                f"Follow-up target: reference date + {f['target_offset_days']} days; window ±"
                f"{f['window_half_width_days']} days inclusive; select {f['select']}; tie-breaker "
                f"{', '.join(f['tie_breaker'])}.",
                f"Formula: {ep['formula']}. Population: {ep['population']}. Source: {r['source_section']['document']} "
                f"section {r['source_section']['section']}.",
            ]
            if r.get("amends"):
                t.append(f"{ep_id}.{rv} amends {ep_id}.{r['amends']}.")
            rows.append(
                {
                    "entry_id": f"REG::rule::{ep_id}.{rv}",
                    "concept_id": f"{ep_id}.{rv}",
                    "scheme": "REGISTRY",
                    "title": f"{ep_id} {rv}",
                    "text": "\n".join(t),
                    "edge_ids": [],
                    "inverse_edge_ids": [],
                    "source": "registry",
                    "access": f"study:{ep['study']}",
                }
            )
    for rid, r in registry["eligibility"].items():
        t = [
            f"Eligibility rule {rid}, study {r['study']}, protocol versions {', '.join(r['applies_to_protocol_versions'])}, "
            f"review state {r['review_state']}. Source: {r['source_section']['document']} section "
            f"{r['source_section']['section']}."
        ]
        for c in r["criteria"]:
            cls = c.get("class") or c.get("comorbidity_class")
            t.append(f"{c['type']} {c['id']}: {c['text']}" + (f" (concept class {cls})" if cls else "") + ".")
        rows.append(
            {
                "entry_id": f"REG::elig::{rid}",
                "concept_id": rid,
                "scheme": "REGISTRY",
                "title": rid,
                "text": "\n".join(t),
                "edge_ids": [],
                "inverse_edge_ids": [],
                "source": "registry",
                "access": f"study:{r['study']}",
            }
        )
    return rows


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
