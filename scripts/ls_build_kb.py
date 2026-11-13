"""Build the vendored life-sciences knowledge base (KB) from pinned open-standards releases.

ADR-0022 / ADR-0025. Inputs: the raw releases listed in src/standards/life_sciences/standards_manifest.yaml,
already downloaded to a cache directory. Checksums are verified before parsing, and a mismatch is fatal.
Outputs are small curated CSVs in src/standards/life_sciences/ (committed, ADR-0007 pattern):

  kb_concept.csv   concept_id, scheme, code, notation, label, definition, concept_type, release
  kb_edge.csv      edge_id, subject, predicate, object, source_artifact, authority, release
  kb_build_report.json  counts, unresolved seeds, pruned branches

DIRECT assertions only. No transitive facts are written here. Closures are derived downstream (closure
approach), and the graph traverses (graph approach). The same kb_edge rows feed every retrieval approach
(ADR-0025 parity).

    .venv/bin/python -I scripts/ls_build_kb.py --cache ~/.cache/care_lab/standards
        [--seeds src/standards/life_sciences/kb_seeds.yaml] [--out src/standards/life_sciences]

Expected cache layout (file names as published): mondo.obo, Core_MEDRT_XML.zip, desc2026.gz,
"SDTM Terminology.txt", cdisc_biomedical_concepts_latest.csv, cdisc_biomedical_concepts_hierarchy_latest.csv,
cdisc_sdtm_dataset_specializations_latest.csv, Thesaurus_26.10d.FLAT.zip
"""

from __future__ import annotations

import argparse
import collections
import csv
import gzip
import hashlib
import io
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
STD = REPO / "src" / "standards" / "life_sciences"

FILES = {  # artifact_id -> cache file name
    "mondo": "mondo.obo",
    "medrt": "Core_MEDRT_XML.zip",
    "mesh": "desc2026.gz",
    "cdisc_sdtm_ct": "SDTM Terminology.txt",
    "cdisc_cosmos_bc": "cdisc_biomedical_concepts_latest.csv",
    "cdisc_cosmos_bc_hierarchy": "cdisc_biomedical_concepts_hierarchy_latest.csv",
    "cdisc_cosmos_sdtm_dss": "cdisc_sdtm_dataset_specializations_latest.csv",
    "ncit": "Thesaurus_26.10d.FLAT.zip",
    "mesh_supp": "supp2026.gz",
}

# MED-RT relations kept (public release; Synonym Of dropped -- UMLS/SNOMED-sourced synonyms)
# Scope = what the demo's questions use (ADR-0025: the trim applies to every retrieval approach equally).
# Dropped (no rule or question uses them): has_PK, has_SC, CI_ChemClass, may_diagnose, induces,
# site_of_metabolism.
MEDRT_KEEP = {"has_MoA", "has_PE", "has_TC", "CI_with", "CI_MoA", "CI_PE", "may_treat", "may_prevent"}


class KB:
    def __init__(self, release: dict[str, str]):
        self.concepts: dict[str, dict] = {}
        self.edges: dict[str, dict] = {}
        self.release = release

    def concept(
        self,
        cid: str,
        scheme: str,
        code: str,
        label: str,
        *,
        concept_type: str,
        definition: str = "",
        notation: str = "",
        artifact: str,
    ) -> str:
        cur = self.concepts.get(cid)
        if cur is None or (not cur["label"] and label):
            self.concepts[cid] = dict(
                concept_id=cid,
                scheme=scheme,
                code=code,
                notation=notation,
                label=label or "",
                definition=(definition or "")[:600],
                concept_type=concept_type,
                release=self.release[artifact],
            )
        return cid

    def edge(self, s: str, p: str, o: str, *, artifact: str, authority: str = "") -> None:
        eid = hashlib.sha1(f"{s}|{p}|{o}".encode()).hexdigest()[:16]
        if eid not in self.edges:
            self.edges[eid] = dict(
                edge_id=eid,
                subject=s,
                predicate=p,
                object=o,
                source_artifact=artifact,
                authority=authority,
                release=self.release[artifact],
            )


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return "sha256:" + h.hexdigest()


def verify(cache: Path, manifest: dict) -> dict[str, str]:
    by_id = {a["artifact_id"]: a for a in manifest["artifacts"]}
    release = {}
    for aid, fname in FILES.items():
        p = cache / fname
        if not p.exists():
            sys.exit(f"MISSING {p} -- download {by_id[aid]['source_location']} (see standards_manifest.yaml)")
        got, want = sha256(p), by_id[aid]["checksum"]
        if got != want:
            sys.exit(
                f"CHECKSUM MISMATCH {fname}: {got} != manifest {want}. Re-pin the manifest deliberately."
            )
        release[aid] = str(by_id[aid]["release_version"])
    return release


# ----------------------------------------------------------------------------------------------- MONDO
def parse_mondo(path: Path) -> dict[str, dict]:
    T, cur = {}, None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if line == "[Term]":
            cur = {"is_a": [], "xref": [], "def": ""}
            continue
        if line.startswith("["):
            cur = None
            continue
        if cur is None or ": " not in line:
            continue
        k, v = line.split(": ", 1)
        if k == "id":
            T[v] = cur
            cur["id"] = v
        elif k == "name":
            cur["name"] = v
        elif k == "def":
            m = re.match(r'"(.*)"', v)
            cur["def"] = m.group(1) if m else ""
        elif k == "is_a":
            cur["is_a"].append(v.split(" ")[0])
        elif k == "xref":
            code = v.split(" ")[0]
            q = re.search(r'source="([^"]+)"', v)
            cur["xref"].append((code, q.group(1) if q else ""))
        elif k == "is_obsolete" and v == "true":
            cur["obsolete"] = True
    return {k: t for k, t in T.items() if k.startswith("MONDO:") and not t.get("obsolete")}


def build_mondo(kb: KB, T: dict, seeds: dict, report: dict) -> set[str]:
    kids = collections.defaultdict(list)
    for t in T.values():
        for p in t["is_a"]:
            kids[p].append(t["id"])

    def desc(c):
        out, st = set(), [c]
        while st:
            for k in kids.get(st.pop(), []):
                if k not in out:
                    out.add(k)
                    st.append(k)
        return out

    def anc(c):
        out, st = set(), [c]
        while st:
            for p in T.get(st.pop(), {}).get("is_a", []):
                if p in T and p not in out:
                    out.add(p)
                    st.append(p)
        return out

    prune_root = next((k for k, t in T.items() if t.get("name") == seeds["mondo_prune_branch_label"]), None)
    pruned = desc(prune_root) | {prune_root} if prune_root else set()
    cap = seeds["max_descendants_per_seed"]
    keep: set[str] = set()
    for s in seeds["mondo_subtrees"]:
        sid = s["id"]
        if sid not in T:
            report["unresolved"].append(f"MONDO seed {sid} ({s['note']})")
            continue
        d = sorted(desc(sid) - pruned)
        if len(d) > cap:
            report["truncated"].append(
                f"{sid} {s['note']}: {len(d)} descendants > cap {cap}; kept nearest {cap}"
            )
            d = d[:cap]
        keep |= {sid, *d}
        report["mondo_seed_sizes"][sid] = {"note": s["note"], "role": s["role"], "descendants": len(d)}
    keep |= {a for c in list(keep) for a in anc(c)}
    keep -= pruned
    for c in sorted(keep):
        t = T[c]
        kb.concept(
            c,
            "MONDO",
            c.split(":")[1],
            t.get("name", ""),
            concept_type="Disease",
            definition=t["def"],
            artifact="mondo",
        )
        for p in t["is_a"]:
            if p in keep:
                kb.edge(c, "rdfs:subClassOf", p, artifact="mondo")
        for code, src in t["xref"]:
            pre = code.split(":")[0]
            if pre not in ("MESH", "NCIT", "ICD10CM"):  # DOID dropped: ~500 nodes, no question uses them
                continue
            pred = "skos:exactMatch" if src == "MONDO:equivalentTo" else "oboInOwl:hasDbXref"
            kb.edge(c, pred, code, artifact="mondo", authority=src)
    report["mondo_pruned_branch"] = {"root": prune_root, "terms": len(pruned)}
    return keep


# ----------------------------------------------------------------------------------------------- MeSH
def parse_mesh(path: Path):
    m2d, dname, dtrees, tree2d = {}, {}, {}, {}
    for _, el in ET.iterparse(gzip.open(path)):
        if el.tag == "DescriptorRecord":
            d = el.findtext("DescriptorUI")
            dname[d] = el.findtext("DescriptorName/String")
            dtrees[d] = [t.text for t in el.findall("TreeNumberList/TreeNumber")]
            for t in dtrees[d]:
                tree2d[t] = d
            for c in el.findall("ConceptList/Concept"):
                m2d[c.findtext("ConceptUI")] = (d, c.findtext("ConceptName/String"))
            el.clear()
    return m2d, dname, dtrees, tree2d


def parse_mesh_supp(path: Path):
    """Supplementary Concept Records: SCR UI -> (name, [mapped-to descriptor UIs]); concept UI -> SCR UI."""
    scr, m2s = {}, {}
    for _, el in ET.iterparse(gzip.open(path)):
        if el.tag == "SupplementalRecord":
            c = el.findtext("SupplementalRecordUI")
            heads = [
                h.text.lstrip("*")
                for h in el.findall("HeadingMappedToList/HeadingMappedTo/DescriptorReferredTo/DescriptorUI")
            ]
            scr[c] = (el.findtext("SupplementalRecordName/String"), heads)
            for k in el.findall("ConceptList/Concept"):
                m2s[k.findtext("ConceptUI")] = c
            el.clear()
    return scr, m2s


def add_mesh_scr(kb: KB, c: str, scr, dname, dtrees, tree2d, seen: set) -> None:
    """SCR node (MESH:C...; same id MONDO xrefs use) + headingMappedTo descriptor(s)."""
    if c not in scr:
        return
    name, heads = scr[c]
    kb.concept(
        f"MESH:{c}", "MESH_SCR", c, name, concept_type="MeshSupplementaryConcept", artifact="mesh_supp"
    )
    for d in heads:
        if d in dname:
            kb.edge(f"MESH:{c}", "mesh:headingMappedTo", f"MESH:{d}", artifact="mesh_supp")
            add_mesh_descriptor(kb, d, dname, dtrees, tree2d, seen)


def add_mesh_descriptor(kb: KB, d: str, dname, dtrees, tree2d, seen: set) -> None:
    """Descriptor node + MeSH tree ancestors (broader by tree number)."""
    st = [d]
    while st:
        x = st.pop()
        if x in seen or x not in dname:
            continue
        seen.add(x)
        kb.concept(f"MESH:{x}", "MESH", x, dname[x], concept_type="MeshDescriptor", artifact="mesh")
        for t in dtrees.get(x, []):
            if "." in t:
                parent = tree2d.get(t.rsplit(".", 1)[0])
                if parent:
                    kb.edge(f"MESH:{x}", "mesh:broaderDescriptor", f"MESH:{parent}", artifact="mesh")
                    st.append(parent)


# ----------------------------------------------------------------------------------------------- MED-RT
ASSOC = re.compile(
    r"<association><namespace>[^<]+</namespace><name>([^<]+)</name><from_namespace>([^<]+)</from_namespace>"
    r"<from_name>([^<]*)</from_name><from_code>([^<]+)</from_code><to_namespace>([^<]+)</to_namespace>"
    r"<to_name>([^<]*)</to_name><to_code>([^<]+)</to_code>(.*?)</association>"
)
CONCEPT = re.compile(
    r"<concept><namespace>MED-RT</namespace><name>([^<]+)</name><code>([^<]+)</code>(.*?)</concept>"
)


def parse_medrt(path: Path):
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.endswith("_XML.xml"))
        x = z.read(name).decode("utf-8").replace("\t", "").replace("\n", "")
    import html

    assoc = []
    for m in ASSOC.finditer(x):
        rel, fns, fname, fcode, tns, tname, tcode, rest = m.groups()
        auth = re.search(r"<name>Authority</name><value>([^<]+)</value>", rest)
        assoc.append(
            dict(
                rel=rel,
                fns=fns,
                fname=html.unescape(fname),
                fcode=fcode,
                tns=tns,
                tname=html.unescape(tname),
                tcode=tcode,
                auth=auth.group(1) if auth else "",
            )
        )
    cty = {}
    for m in CONCEPT.finditer(x):
        t = re.search(r"<name>CTY</name><value>([^<]+)</value>", m.group(3))
        cty[m.group(2)] = (html.unescape(m.group(1)), t.group(1) if t else "")
    return assoc, cty


def node_id(ns: str, code: str) -> str:
    return {"RxNorm": f"RXNORM:{code}", "MED-RT": f"MEDRT:{code}", "MeSH": f"MESHC:{code}"}.get(
        ns, f"{ns}:{code}"
    )


def build_medrt(kb: KB, assoc, cty, mesh, supp, seeds: dict, report: dict, mondo_mesh: set[str]) -> None:
    m2d, dname, dtrees, tree2d = mesh
    scr, m2s = supp
    by_from = collections.defaultdict(list)
    parents_of = collections.defaultdict(list)  # child code -> [(parent ns, code, name, auth)]
    rx_by_name = {}
    for a in assoc:
        by_from[(a["fns"], a["fcode"])].append(a)
        if a["rel"] == "Parent Of":
            parents_of[(a["tns"], a["tcode"])].append(a)
        if a["fns"] == "RxNorm":
            rx_by_name.setdefault(a["fname"].lower(), a["fcode"])
        if a["tns"] == "RxNorm":
            rx_by_name.setdefault(a["tname"].lower(), a["tcode"])
    medrt_by_name = {v[0]: k for k, v in cty.items()}

    drugs: dict[str, str] = {}
    for c in seeds["medrt_classes"]:
        code = medrt_by_name.get(c["name"])
        if not code:
            report["unresolved"].append(f"MED-RT class {c['name']}")
            continue
        for a in by_from[("MED-RT", code)]:
            if a["rel"] == "Parent Of" and a["tns"] == "RxNorm":
                drugs[a["tcode"]] = a["tname"]
    for pe in seeds["medrt_pe_members"]:
        code = medrt_by_name.get(pe["name"])
        if not code:
            report["unresolved"].append(f"MED-RT PE {pe['name']}")
            continue
        for a in assoc:
            if a["rel"] == "has_PE" and a["tcode"] == code and a["fns"] == "RxNorm":
                drugs[a["fcode"]] = a["fname"]
    for n in seeds["medrt_drugs"]:
        code = rx_by_name.get(n.lower())
        if not code:
            report["unresolved"].append(f"RxNorm ingredient '{n}' not in MED-RT")
            continue
        drugs[code] = n

    mesh_seen: set[str] = set()

    def add_medrt_class(code: str) -> None:
        """MED-RT class node + its MED-RT class ancestors (Parent Of between MED-RT concepts)."""
        st = [code]
        while st:
            c = st.pop()
            nid = f"MEDRT:{c}"
            if nid in kb.concepts:
                continue
            name, t = cty.get(c, ("", ""))
            kb.concept(
                nid, "MEDRT", c, name, concept_type=f"MedrtClass:{t}" if t else "MedrtClass", artifact="medrt"
            )
            for p in parents_of.get(("MED-RT", c), []):
                if p["fns"] == "MED-RT":
                    kb.edge(
                        nid, "rdfs:subClassOf", f"MEDRT:{p['fcode']}", artifact="medrt", authority=p["auth"]
                    )
                    st.append(p["fcode"])

    def add_mesh_concept(mcode: str, mname: str) -> None:
        nid = f"MESHC:{mcode}"
        kb.concept(nid, "MESH", mcode, mname, concept_type="MeshConcept", artifact="mesh")
        hit = m2d.get(mcode)
        if hit:
            kb.edge(nid, "mesh:conceptOf", f"MESH:{hit[0]}", artifact="mesh")
            add_mesh_descriptor(kb, hit[0], dname, dtrees, tree2d, mesh_seen)
        elif mcode in m2s:
            kb.edge(nid, "mesh:conceptOf", f"MESH:{m2s[mcode]}", artifact="mesh_supp")
            add_mesh_scr(kb, m2s[mcode], scr, dname, dtrees, tree2d, mesh_seen)
        else:
            report["mesh_unmapped_concepts"].append(f"{mcode} {mname}")

    for rx, name in sorted(drugs.items()):
        did = kb.concept(f"RXNORM:{rx}", "RXNORM", rx, name, concept_type="Ingredient", artifact="rxnorm")
        for p in parents_of.get(("RxNorm", rx), []):  # EPC / APC membership
            if p["fns"] == "MED-RT":
                add_medrt_class(p["fcode"])
                kb.edge(did, "medrt:memberOf", f"MEDRT:{p['fcode']}", artifact="medrt", authority=p["auth"])
        for a in by_from[("RxNorm", rx)]:
            if a["rel"] not in MEDRT_KEEP or a["tns"] == "SNOMED CT":
                continue
            if a["tns"] == "MED-RT":
                add_medrt_class(a["tcode"])
            elif a["tns"] == "MeSH":
                add_mesh_concept(a["tcode"], a["tname"])
            kb.edge(
                did, f"medrt:{a['rel']}", node_id(a["tns"], a["tcode"]), artifact="medrt", authority=a["auth"]
            )
    # class-level assertions on included classes (e.g. EPC has_MoA), same filters
    for nid in [c for c in kb.concepts if c.startswith("MEDRT:")]:
        for a in by_from[("MED-RT", nid.split(":")[1])]:
            if a["rel"] in MEDRT_KEEP and a["tns"] != "SNOMED CT":
                if a["tns"] == "MED-RT":
                    add_medrt_class(a["tcode"])
                elif a["tns"] == "MeSH":
                    add_mesh_concept(a["tcode"], a["tname"])
                kb.edge(
                    nid,
                    f"medrt:{a['rel']}",
                    node_id(a["tns"], a["tcode"]),
                    artifact="medrt",
                    authority=a["auth"],
                )
    # MeSH descriptors referenced by included MONDO terms (so the MONDO<->MED-RT bridge closes)
    for d in sorted(mondo_mesh):
        if d.startswith("C"):
            add_mesh_scr(kb, d, scr, dname, dtrees, tree2d, mesh_seen)
        else:
            add_mesh_descriptor(kb, d, dname, dtrees, tree2d, mesh_seen)
    report["drugs"] = len(drugs)


# ----------------------------------------------------------------------------------------------- CDISC
def build_cdisc(kb: KB, cache: Path, seeds: dict, report: dict) -> None:
    rows = list(csv.DictReader(open(cache / FILES["cdisc_sdtm_ct"], encoding="utf-8"), delimiter="\t"))
    heads = {r["Code"]: r for r in rows if not r["Codelist Code"]}
    for cl, allow in seeds["cdisc_ct_codelists"].items():
        h = heads.get(cl)
        if not h:
            report["unresolved"].append(f"CT codelist {cl}")
            continue
        clid = kb.concept(
            f"CDISC_CT:{cl}",
            "CDISC_CT",
            cl,
            h["Codelist Name"],
            notation=h["CDISC Submission Value"],
            definition=h["CDISC Definition"],
            concept_type="Codelist",
            artifact="cdisc_sdtm_ct",
        )
        kb.concepts[clid]["definition"] += f" [extensible={h['Codelist Extensible (Yes/No)']}]"
        terms = [r for r in rows if r["Codelist Code"] == cl]
        if allow:
            want = set(allow)
            terms = [r for r in terms if r["CDISC Submission Value"] in want]
            missing = want - {r["CDISC Submission Value"] for r in terms}
            if missing:
                report["unresolved"].append(f"CT {cl} submission values not found: {sorted(missing)}")
        for r in terms:
            tid = kb.concept(
                f"CDISC_CT:{cl}.{r['Code']}",
                "CDISC_CT",
                r["Code"],
                r["NCI Preferred Term"],
                notation=r["CDISC Submission Value"],
                definition=r["CDISC Definition"],
                concept_type="CodelistTerm",
                artifact="cdisc_sdtm_ct",
            )
            kb.edge(tid, "cdisc:inCodelist", clid, artifact="cdisc_sdtm_ct")
            kb.edge(tid, "cdisc:nciConcept", f"NCIT:{r['Code']}", artifact="cdisc_sdtm_ct")

    bc = list(csv.DictReader(open(cache / FILES["cdisc_cosmos_bc"], encoding="utf-8")))
    bc_by = collections.defaultdict(list)
    for r in bc:
        bc_by[r["bc_id"]].append(r)
    want = list(seeds["cosmos_bc_ids"])
    seen = set()
    while want:
        b = want.pop()
        if b in seen:
            continue
        seen.add(b)
        rs = bc_by.get(b)
        if not rs:
            report["unresolved"].append(f"COSMoS BC {b}")
            continue
        r0 = rs[0]
        bid = kb.concept(
            f"COSMOS_BC:{b}",
            "COSMOS_BC",
            b,
            r0["short_name"],
            definition=r0["definition"],
            concept_type="BiomedicalConcept",
            artifact="cdisc_cosmos_bc",
        )
        if r0["ncit_code"]:
            kb.edge(bid, "cosmos:ncitCode", f"NCIT:{r0['ncit_code']}", artifact="cdisc_cosmos_bc")
        if r0["parent_bc_id"]:
            kb.edge(bid, "cosmos:parentBC", f"COSMOS_BC:{r0['parent_bc_id']}", artifact="cdisc_cosmos_bc")
            want.append(r0["parent_bc_id"])
        # Data-element concepts and LOINC codings are out of scope (no rule or question uses them).

    dss = list(csv.DictReader(open(cache / FILES["cdisc_cosmos_sdtm_dss"], encoding="utf-8")))
    ct_term_ids = {
        (c["notation"], c["concept_id"].split(".")[0]): c["concept_id"]
        for c in kb.concepts.values()
        if c["concept_type"] == "CodelistTerm"
    }
    cl_by_sv = {
        c["notation"]: c["concept_id"] for c in kb.concepts.values() if c["concept_type"] == "Codelist"
    }
    n = 0
    for r in dss:
        if f"COSMOS_BC:{r['bc_id']}" not in kb.concepts or r["domain"] != "VS":
            continue
        if any(r["vlm_group_id"].endswith(sfx) for sfx in seeds.get("cosmos_dss_skip_suffixes", [])):
            continue
        sid = kb.concept(
            f"COSMOS_DSS:{r['vlm_group_id']}",
            "COSMOS_DSS",
            r["vlm_group_id"],
            r["short_name"],
            notation=f"SDTMIG {r['sdtmig_start_version']}-{r['sdtmig_end_version'] or ''}",
            concept_type="DatasetSpecialization",
            artifact="cdisc_cosmos_sdtm_dss",
        )
        kb.edge(sid, "cosmos:specializes", f"COSMOS_BC:{r['bc_id']}", artifact="cdisc_cosmos_sdtm_dss")
        var = kb.concept(
            f"SDTM:{r['domain']}.{r['sdtm_variable']}",
            "SDTM_VAR",
            r["sdtm_variable"],
            f"{r['domain']}.{r['sdtm_variable']}",
            concept_type="DatasetVariable",
            definition="Variable name and role from the COSMoS DSS; SDTMIG text not vendored "
            "(CDISC Library not used).",
            notation=r["role"],
            artifact="cdisc_cosmos_sdtm_dss",
        )
        kb.edge(var, "cosmos:inDomain", f"SDTM:{r['domain']}", artifact="cdisc_cosmos_sdtm_dss")
        kb.concept(
            f"SDTM:{r['domain']}",
            "SDTM_VAR",
            r["domain"],
            f"SDTM {r['domain']} domain",
            concept_type="Domain",
            artifact="cdisc_cosmos_sdtm_dss",
        )
        # one DSS-variable binding node per (dss, variable) so value lists and mandatory flags stay attached
        bnd = kb.concept(
            f"COSMOS_DSSVAR:{r['vlm_group_id']}.{r['sdtm_variable']}",
            "COSMOS_DSS",
            f"{r['vlm_group_id']}.{r['sdtm_variable']}",
            f"{r['short_name']} — {r['sdtm_variable']}",
            notation=f"mandatory={r['mandatory_variable']}",
            concept_type="DSSVariableBinding",
            artifact="cdisc_cosmos_sdtm_dss",
        )
        kb.edge(sid, "cosmos:hasVariableBinding", bnd, artifact="cdisc_cosmos_sdtm_dss")
        kb.edge(bnd, "cosmos:constrains", var, artifact="cdisc_cosmos_sdtm_dss")
        if r["codelist_submission_value"] and r["codelist_submission_value"] in cl_by_sv:
            cl = cl_by_sv[r["codelist_submission_value"]]
            kb.edge(bnd, "cosmos:usesCodelist", cl, artifact="cdisc_cosmos_sdtm_dss")
            for v in [x for x in (r["value_list"] or "").split(";") if x]:
                t = ct_term_ids.get((v, cl))
                if t:
                    kb.edge(bnd, "cosmos:allowedValue", t, artifact="cdisc_cosmos_sdtm_dss")
                else:
                    report["unresolved"].append(
                        f"DSS {r['vlm_group_id']}.{r['sdtm_variable']} value '{v}' not in CT subset"
                    )
            if r["assigned_value"]:
                t = ct_term_ids.get((r["assigned_value"], cl))
                if t:
                    kb.edge(bnd, "cosmos:assignedValue", t, artifact="cdisc_cosmos_sdtm_dss")
        n += 1
    report["dss_bindings"] = n


# ----------------------------------------------------------------------------------------------- NCIt labels
def label_ncit(kb: KB, cache: Path) -> None:
    want = {e["object"].split(":")[1] for e in kb.edges.values() if e["object"].startswith("NCIT:")}
    with zipfile.ZipFile(cache / FILES["ncit"]) as z:
        with z.open("Thesaurus.txt") as f:
            for line in io.TextIOWrapper(f, encoding="utf-8"):
                p = line.rstrip("\n").split("\t")
                if p[0] in want:
                    label = p[5] if len(p) > 5 and p[5] else p[3].split("|")[0]
                    kb.concept(
                        f"NCIT:{p[0]}",
                        "NCIT",
                        p[0],
                        label,
                        definition=p[4] if len(p) > 4 else "",
                        concept_type="NcitConcept",
                        artifact="ncit",
                    )


def add_curated(kb: KB, path: Path, report: dict) -> None:
    """Namespaced demo-extension edges (cpl:), each with a reason. Never presented as official content."""
    n = 0
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if not r["predicate"].startswith("cpl:"):
            sys.exit(f"curated edge must use the cpl: namespace: {r}")
        for end in (r["subject"], r["object"]):
            if end not in kb.concepts:
                sys.exit(f"curated edge endpoint not in KB: {end}")
        kb.edge(r["subject"], r["predicate"], r["object"], artifact="demo_curation", authority=r["authority"])
        n += 1
    report["curated_edges"] = n


def write(kb: KB, out: Path, report: dict) -> None:
    # every edge endpoint must be a concept row, except external-code xrefs (ICD10CM/DOID/coding systems)
    dangling = collections.Counter()
    for e in kb.edges.values():
        for end in (e["subject"], e["object"]):
            if end not in kb.concepts:
                pre = end.split(":")[0]
                if pre == "MESH" and end.split(":")[1].startswith("C"):
                    pre = "MESH_SCR"  # MeSH Supplementary Concept Record: not in the descriptor file
                if pre in ("MESH", "NCIT"):
                    dangling[pre] += 1
                else:
                    kb.concept(
                        end,
                        pre,
                        end.split(":", 1)[1],
                        "",
                        concept_type="ExternalCode",
                        artifact={"ICD10CM": "mondo", "DOID": "mondo"}.get(pre, "cdisc_cosmos_bc"),
                    )
    report["dangling_by_scheme"] = dict(dangling)
    cols_c = ["concept_id", "scheme", "code", "notation", "label", "definition", "concept_type", "release"]
    cols_e = ["edge_id", "subject", "predicate", "object", "source_artifact", "authority", "release"]
    with open(out / "kb_concept.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, cols_c)
        w.writeheader()
        w.writerows(sorted(kb.concepts.values(), key=lambda r: r["concept_id"]))
    with open(out / "kb_edge.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, cols_e)
        w.writeheader()
        w.writerows(sorted(kb.edges.values(), key=lambda r: (r["subject"], r["predicate"], r["object"])))
    report["concepts_by_scheme"] = dict(collections.Counter(c["scheme"] for c in kb.concepts.values()))
    report["edges_by_predicate"] = dict(
        collections.Counter(e["predicate"] for e in kb.edges.values()).most_common()
    )
    report["concepts"] = len(kb.concepts)
    report["edges"] = len(kb.edges)
    (out / "kb_build_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True, type=Path)
    ap.add_argument("--seeds", type=Path, default=STD / "kb_seeds.yaml")
    ap.add_argument("--out", type=Path, default=STD)
    a = ap.parse_args()
    manifest = yaml.safe_load(open(STD / "standards_manifest.yaml"))
    seeds = yaml.safe_load(open(a.seeds))
    release = verify(a.cache, manifest)
    release["rxnorm"] = "2026.10.05.26AA (as referenced by MED-RT 2026.11.02)"
    report = {"unresolved": [], "truncated": [], "mesh_unmapped_concepts": [], "mondo_seed_sizes": {}}
    kb = KB(release)

    T = parse_mondo(a.cache / FILES["mondo"])
    keep = build_mondo(kb, T, seeds, report)
    mondo_mesh = {x[0].split(":")[1] for c in keep for x in T[c]["xref"] if x[0].startswith("MESH:")}
    mesh = parse_mesh(a.cache / FILES["mesh"])
    supp = parse_mesh_supp(a.cache / FILES["mesh_supp"])
    assoc, cty = parse_medrt(a.cache / FILES["medrt"])
    build_medrt(kb, assoc, cty, mesh, supp, seeds, report, mondo_mesh)
    build_cdisc(kb, a.cache, seeds, report)
    label_ncit(kb, a.cache)
    kb.release["demo_curation"] = "kb_curated_edges.csv (repo)"
    add_curated(kb, STD / "kb_curated_edges.csv", report)
    write(kb, a.out, report)
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "concepts",
                    "edges",
                    "concepts_by_scheme",
                    "unresolved",
                    "truncated",
                    "dangling_by_scheme",
                )
            },
            indent=1,
        )
    )
    print("edges_by_predicate:", report["edges_by_predicate"])


if __name__ == "__main__":
    main()
