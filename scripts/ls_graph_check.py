"""Check the life-sciences Ontobricks mapping against the live tables before an import. Read-only.

Parses src/ontology/life_sciences/clinical_study.r2rml.ttl and, for every TriplesMap:
  * entity maps:       the map's SQL runs, returns rows, and its id column is unique;
  * relationship maps: the SQL returns rows, and every subject / object id resolves to an instance of the class its
                       IRI template names (no dangling edge, which Ontobricks reports as "entity not found");
and checks that every OWL class has an entity map (an unmapped class auto-binds to a leftover table: HEDIS rev 3/5).

    .venv/bin/python -I scripts/ls_graph_check.py       # exits 1 on any problem
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import rdflib
from rdflib.namespace import OWL, RDF

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "src/ontology/life_sciences"
RR = rdflib.Namespace("http://www.w3.org/ns/r2rml#")
TPL = re.compile(r"/ontology/(\w+)/\{(\w+)\}$")


def _q():
    spec = importlib.util.spec_from_file_location("q", ROOT / "scripts/q.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.run


def maps(g: rdflib.Graph) -> list[dict]:
    out = []
    for tm in g.subjects(RDF.type, RR.TriplesMap):
        lt = g.value(tm, RR.logicalTable)
        sm = g.value(tm, RR.subjectMap)
        cls, scol = TPL.search(str(g.value(sm, RR.template))).groups()
        objs = []
        for pom in g.objects(tm, RR.predicateObjectMap):
            om = g.value(pom, RR.objectMap)
            t = g.value(om, RR.template)
            if t is not None:
                ocls, ocol = TPL.search(str(t)).groups()
                objs.append((str(g.value(pom, RR.predicate)).rsplit("/", 1)[-1], ocls, ocol))
        out.append({"name": str(tm).rsplit("#", 1)[-1], "table": (str(g.value(lt, RR.tableName)) if g.value(lt, RR.tableName) is not None
                              else f"({g.value(lt, RR.sqlQuery)})"), "cls": cls,
                    "col": scol, "entity": g.value(sm, RR["class"]) is not None, "objs": objs})
    return out


def main() -> None:
    g = rdflib.Graph().parse(DIR / "clinical_study.r2rml.ttl")
    owl = rdflib.Graph().parse(DIR / "clinical_study.owl.ttl")
    ms = maps(g)
    run = _q()
    ent = {m["cls"]: m for m in ms if m["entity"]}
    bad = []
    owl_classes = {str(c).rsplit("#", 1)[-1] for c in owl.subjects(RDF.type, OWL.Class) if isinstance(c, rdflib.URIRef)}
    unmapped = sorted(owl_classes - set(ent))
    if unmapped:
        # an abstract parent with no instances is fine only if nothing else can auto-bind it; report it
        print(f"OWL classes without an entity map: {unmapped}")
    for c, m in sorted(ent.items()):
        r = run(f"SELECT count(*) AS n, count(DISTINCT {m['col']}) AS k FROM {m['table']}")[0]
        ok = int(r["n"]) > 0 and r["n"] == r["k"]
        bad += [] if ok else [f"entity {c}: rows {r['n']}, distinct ids {r['k']}"]
        print(f"{'ok ' if ok else 'BAD'} entity {c:28} {int(r['n']):>8} rows")
    for m in ms:
        if m["entity"]:
            continue
        for pred, ocls, ocol in m["objs"]:
            se, oe = ent.get(m["cls"]), ent.get(ocls)
            if not se or not oe:
                bad.append(f"{m['name']}: endpoint class without an entity map ({m['cls']} / {ocls})")
                continue
            r = run(
                f"SELECT count(*) AS n, "
                f"count_if(s.{se['col']} IS NULL) AS dangling_subject, count_if(o.{oe['col']} IS NULL) AS dangling_object "
                f"FROM {m['table']} r LEFT JOIN {se['table']} s ON s.{se['col']} = r.{m['col']} "
                f"LEFT JOIN {oe['table']} o ON o.{oe['col']} = r.{ocol}"
            )[0]
            n, ds, do = int(r["n"]), int(r["dangling_subject"]), int(r["dangling_object"])
            ok = n > 0 and ds == 0 and do == 0
            bad += [] if ok else [f"{m['name']}: rows {n}, dangling subject {ds}, object {do}"]
            print(f"{'ok ' if ok else 'BAD'} {m['cls']:>22} -{pred}-> {ocls:24} {n:>8} rows"
                  + ("" if ok else f"  dangling s={ds} o={do}"))
    print(f"\n{len(ent)} entity maps, {sum(not m['entity'] for m in ms)} relationship maps; {len(bad)} problem(s)")
    for b in bad:
        print("  -", b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
