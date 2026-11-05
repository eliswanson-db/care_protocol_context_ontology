"""Retrieval-as-context for the two "knowledge" arms, shared by the app's Retrieval Arena and the eval harness
(src/benchmark/retrieval_eval/providers.py), so the Arena shows exactly the context that gets scored.

Both functions take a question and a `run_sql(sql) -> list[dict]` callable and return MLflow-retriever-shaped
documents ({page_content, metadata}). Neither computes an answer: they return what each knowledge layer HOLDS
for the question, which a fixed agent then reasons over.

  ontology_context  Genie Ontology's MODELED layer: the Genie Pages (read from the UC volume they are imported
                    from), selected by synonym / keyword match against the question, plus the certified metric
                    views those Pages link to (comment, governed rule expressions, certification + domain tags).
                    Genie One's own snippet search is semantic and its payload is not exposed by the API, so
                    this is a transparent stand-in over the same content -- and Genie's INFERRED snippets are not
                    included.
  graph_context     Ontobricks: entity-link the question's clinical terms to graph nodes, return their typed
                    1-hop neighbourhood (cross-vocabulary guideline edges first, then a small sample of patient
                    membership edges) from the live triplestore.
"""
from __future__ import annotations

import json
import re

import yaml

# --------------------------------------------------- graph -----------------------------------------------------
ONTO_NS = "https://care-protocol.example/ontology/"

# The cross-vocabulary guideline + structural predicates -- the graph's lift over a closure join.
GUIDELINE_PREDS = ["recommendedFor", "inDrugClass", "contraindicatedWith", "contraindicatedWhen",
                   "monitoredBy", "hasThreshold", "firstLineFor", "definedBy", "subClassOf"]
# Patient-level ABox predicates -- sampled (not exhaustively dumped) so the agent sees membership exists.
MEMBER_PREDS = ["hasDiagnosis", "eligibleFor", "prescribed", "hasCareGap"]

# Synonym -> IRI-node anchors (local names). Entity-linking only: every value is a NODE in the graph -- never a
# question-specific answer edge.
LEXICON: dict[str, list[str]] = {
    "diabetes": ["icd/E10", "icd/E11", "icd/E13"], "diabetic": ["icd/E10", "icd/E11", "icd/E13"],
    "kidney": ["icd/N18", "icd/N17", "Measure/KED", "ValueSet/COMORBID_CKD"],
    "nephropathy": ["icd/N18", "icd/E11.2"], "renal": ["icd/N18", "Measure/KED"],
    "ckd": ["icd/N18", "ValueSet/COMORBID_CKD"], "retinopathy": ["icd/E11.3", "icd/E10.3"],
    "heart failure": ["icd/I50", "ValueSet/COMORBID_HF"],
    "cardiorenal": ["icd/I50", "icd/N18", "icd/E11", "ValueSet/COMORBID_HF", "ValueSet/COMORBID_CKD"],
    "statin": ["DrugClass/DRUGCLASS-STATIN", "Measure/SPD"],
    "simvastatin": ["DrugClass/DRUGCLASS-STATIN", "Measure/SPD"],
    "metformin": ["DrugClass/DRUGCLASS-BIGUANIDE", "Threshold/eGFR_LT_30"],
    "biguanide": ["DrugClass/DRUGCLASS-BIGUANIDE"], "sglt2": ["DrugClass/DRUGCLASS-SGLT2"],
    "ace inhibitor": ["DrugClass/DRUGCLASS-ACE"], "ace": ["DrugClass/DRUGCLASS-ACE"],
    "arb": ["DrugClass/DRUGCLASS-ARB"],
    "albuminuria": ["ValueSet/ALBUMINURIA", "DrugClass/DRUGCLASS-ACE", "DrugClass/DRUGCLASS-ARB"],
    "uacr": ["ValueSet/ALBUMINURIA"], "pregnan": ["ValueSet/CONTRA_PREGNANCY"],
    "hepatic": ["ValueSet/CONTRA_HEPATIC"], "contraindicat": ["ValueSet/CONTRA_PREGNANCY", "ValueSet/CONTRA_HEPATIC"],
    "a1c": ["Measure/GSD", "part/LP-HBA1C"], "hba1c": ["Measure/GSD", "part/LP-HBA1C"],
    "glycemic": ["Measure/GSD", "ValueSet/GLYCEMIC"],
    "egfr": ["part/LP-EGFR", "Measure/KED", "Threshold/eGFR_LT_30"],
    "blood pressure": ["Measure/BPD"], "systolic": ["Measure/BPD", "Threshold/systolic_lt_140"],
    "diastolic": ["Measure/BPD", "Threshold/diastolic_lt_90"],
}
MEASURE_CODES = {"gsd": "Measure/GSD", "ked": "Measure/KED", "bpd": "Measure/BPD",
                 "spd": "Measure/SPD", "eed": "Measure/EED"}


def link_entities(question: str) -> tuple[set[str], set[str]]:
    """Resolve the question to (exact IRIs, icd-subtree prefixes)."""
    q = question.lower()
    exact: set[str] = set()
    prefixes: set[str] = set()
    for term, anchors in LEXICON.items():
        if term in q:
            for a in anchors:
                (prefixes if a.startswith("icd/") else exact).add(a)
    for code, iri in MEASURE_CODES.items():
        if re.search(rf"\b{code}\b", q):
            exact.add(iri)
    for m in re.findall(r"\b([A-TV-Z][0-9]{2}(?:\.[0-9]{1,3})?)\b", question):  # raw ICD-10 codes in the prompt
        prefixes.add("icd/" + m)
    return exact, prefixes


def _short(iri: str) -> str:
    return iri[len(ONTO_NS):] if iri and iri.startswith(ONTO_NS) else (iri or "").rsplit("/", 1)[-1]


def graph_context(question: str, run_sql, graph: str) -> list[dict]:
    """Typed 1-hop neighbourhood of the question's linked entities. `graph` = catalog.schema.<base>_graph."""
    exact, prefixes = link_entities(question)
    if not exact and not prefixes:
        return []

    def _match(col: str) -> str:
        cl = []
        if exact:
            cl.append(f"{col} IN ({', '.join(chr(39) + ONTO_NS + n + chr(39) for n in sorted(exact))})")
        for p in sorted(prefixes):
            cl.append(f"{col} LIKE '{ONTO_NS}{p}%'")  # p is from the lexicon or a regex-validated ICD code
        return "(" + " OR ".join(cl) + ")"

    guideline_in = ", ".join(f"'{ONTO_NS}{p}'" for p in GUIDELINE_PREDS)
    member_in = ", ".join(f"'{ONTO_NS}{p}'" for p in MEMBER_PREDS)
    sql = (f"(SELECT subject, predicate, object, 'guideline' AS tier FROM {graph} "
           f"  WHERE predicate IN ({guideline_in}) AND ({_match('subject')} OR {_match('object')}) LIMIT 55) "
           f"UNION ALL "
           f"(SELECT subject, predicate, object, 'member' AS tier FROM {graph} "
           f"  WHERE predicate IN ({member_in}) AND {_match('object')} LIMIT 8)")
    rows = run_sql(sql)
    linked = sorted(exact | {p + "*" for p in prefixes})
    return [{"page_content": f"({_short(r['subject'])}) -[{_short(r['predicate'])}]-> ({_short(r['object'])})  [{r['tier']}]",
             "metadata": {"source": "ontobricks", "kind": "triple", "tier": r["tier"], "graph": graph,
                          "subject": _short(r["subject"]), "predicate": _short(r["predicate"]),
                          "object": _short(r["object"]), "linked_entities": linked}}
            for r in rows]


# ------------------------------------------------ Genie Ontology -----------------------------------------------
_STOP = set("a an and any are as at be by can count does each for from had has have how in is it its many me "
            "of on or per show tell that the their them there these this to under was what when where which who "
            "why with within year patients patient".split())


def _stem(t: str) -> str:
    return t[:-1] if len(t) > 4 and t.endswith("s") and not t.endswith("ss") else t


def _terms(text: str) -> set[str]:
    return {_stem(t) for t in re.findall(r"[a-z0-9][a-z0-9\-]+", text.lower()) if t not in _STOP and len(t) > 2}


def _parse_page(text: str) -> tuple[dict, str]:
    if text.startswith("---"):
        _, fm, body = text.split("---", 2)
        return (yaml.safe_load(fm) or {}), body.strip()
    return {}, text.strip()


def _score_page(question: str, front: dict, body: str) -> tuple[float, list[str]]:
    """Phrase hits on name/synonyms count most; shared content words add a little. Returns (score, matched)."""
    q = question.lower()
    phrases = [str(front.get("name", ""))] + [str(s) for s in front.get("synonyms") or []]
    hits = sorted({p for p in phrases if p and re.search(rf"(?<![a-z0-9]){re.escape(p.lower())}(?![a-z0-9])", q)})
    qt = _terms(question)
    syn_terms = qt & _terms(" ".join(phrases))
    body_terms = (qt & _terms(body)) - syn_terms
    score = 3.0 * len(hits) + 1.0 * len(syn_terms) + 0.25 * len(body_terms)
    # report the question's own words (not stems) for display
    orig = {_stem(w): w for w in re.findall(r"[a-z0-9][a-z0-9\-]+", q)}
    extra = sorted(orig.get(t, t) for t in syn_terms - {t for h in hits for t in _terms(h)})
    return score, hits + extra


_MV_CACHE: dict = {}
# Dimensions every metric view shares -- matching on them would select views by "clinic" / "year" alone.
_GENERIC_FIELDS = {"Measurement Year", "Clinic", "Panel", "Measure", "Age Band", "Eligible Patients", "Month"}


def _describe(fqn: str, run_sql) -> dict | None:
    import time
    hit = _MV_CACHE.get(fqn)
    if hit and time.time() - hit[0] < 300:
        return hit[1]
    meta = run_sql(f"DESCRIBE TABLE EXTENDED {fqn} AS JSON")
    m = json.loads(meta[0]["json_metadata"]) if meta else None
    _MV_CACHE[fqn] = (time.time(), m)
    return m


def _metric_view_doc(fqn: str, run_sql, catalog: str, matched: list[str] | None = None) -> dict | None:
    m = _describe(fqn, run_sql)
    if not m:
        return None
    spec = yaml.safe_load(m.get("view_text") or "") or {}
    _, sch, tbl = fqn.split(".")
    tags = run_sql(f"SELECT tag_name, tag_value FROM {catalog}.information_schema.table_tags "
                   f"WHERE schema_name = '{sch}' AND table_name = '{tbl}'")
    certified = any(t["tag_name"] == "system.certification_status" and t["tag_value"] == "certified" for t in tags)
    domain = any(t["tag_name"] == "Clinical Domain" for t in tags)

    def _fields(items):
        return "; ".join(f"{d['name']} = {d['expr']}" + (f" ({d['comment']})" if d.get("comment") else "")
                         for d in items if d.get("name") not in ("Measurement Year", "Clinic", "Panel", "Measure"))
    badges = ", ".join(b for b, on in (("certified", certified), ("Clinical Domain", domain)) if on) or "uncertified"
    text = (f"Metric view {sch}.{tbl} [{badges}]. {spec.get('comment') or m.get('comment') or ''} "
            f"Dimensions: {_fields(spec.get('dimensions', []))}. Measures: {_fields(spec.get('measures', []))}.")
    return {"page_content": text[:2200],
            "metadata": {"source": "genie_ontology", "kind": "metric_view", "asset": f"{sch}.{tbl}",
                         "certified": certified, "clinical_domain": domain, "matched_on": matched or ["linked from a Page"]}}


def ontology_context(question: str, run_sql, catalog: str, schema: str, semantic_schema: str,
                     k: int = 3, min_score: float = 2.0) -> list[dict]:
    """Top-k Genie Pages for the question + the certified metric views they link to."""
    rows = run_sql(f"SELECT _metadata.file_path AS path, value FROM read_files("
                   f"'/Volumes/{catalog}/{schema}/ontology_pages/', format => 'text', wholeText => true)")
    scored = []
    for r in rows:
        name = r["path"].rsplit("/", 1)[-1]
        if not name.endswith(".md") or name.lower() == "readme.md":
            continue
        front, body = _parse_page(r["value"])
        s, matched = _score_page(question, front, body)
        if s >= min_score:
            scored.append((s, name, front, body, matched))
    scored.sort(key=lambda x: (-x[0], x[1]))
    docs, views = [], []
    for s, name, front, body, matched in scored[:k]:
        docs.append({"page_content": f"Genie Ontology Page — {front.get('name', name)}\n{body}"[:2600],
                     "metadata": {"source": "genie_ontology", "kind": "page", "page": front.get("name", name),
                                  "file": name, "domain": front.get("domain"), "score": round(s, 2),
                                  "matched_on": matched, "body": body[:2600]}})
        for a in front.get("related_assets") or []:
            if f".{semantic_schema}." in a and a not in views:
                views.append(a)
    # Genie also indexes certified metric views directly (comments, display names, synonyms) -- match those too.
    direct = []
    mvs = run_sql(f"SELECT table_name FROM {catalog}.information_schema.tables "
                  f"WHERE table_schema = '{semantic_schema}' AND table_type = 'METRIC_VIEW'")
    from concurrent.futures import ThreadPoolExecutor
    fqns = [f"{catalog}.{semantic_schema}.{r['table_name']}" for r in mvs]
    with ThreadPoolExecutor(max_workers=8) as ex:
        metas = dict(zip(fqns, ex.map(lambda f: _describe(f, run_sql), fqns)))
    for r in mvs:
        fqn = f"{catalog}.{semantic_schema}.{r['table_name']}"
        m = metas.get(fqn)
        if not m:
            continue
        spec = yaml.safe_load(m.get("view_text") or "") or {}
        syns = [str(x) for d in spec.get("dimensions", []) + spec.get("measures", [])
                if d.get("name") not in _GENERIC_FIELDS
                for x in [d.get("display_name") or d.get("name")] + list(d.get("synonyms") or [])
                if str(x).lower() not in _STOP]
        s, matched = _score_page(question, {"name": r["table_name"].replace("_", " "), "synonyms": syns},
                                 spec.get("comment") or "")
        if s >= min_score:
            direct.append((s, fqn, matched))
    direct.sort(key=lambda x: -x[0])
    chosen = [(fqn, m) for _, fqn, m in direct[:2]] + [(v, None) for v in views]
    seen = set()
    for fqn, matched in chosen:
        if fqn in seen or len(seen) >= 3:
            continue
        seen.add(fqn)
        d = _metric_view_doc(fqn, run_sql, catalog, matched)
        if d:
            docs.append(d)
    return docs
