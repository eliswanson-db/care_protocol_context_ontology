"""Create the Care Protocol business domains + subdomains on a workspace (idempotent).

ADR-0008: domains are NOT a DAB resource. They are created via the Beta `databricks domains` API, and each
domain is built on a GOVERNED TAG (`databricks tag-policies`). A domain's displayed name IS its tag_key;
a subdomain's tag_key is `Parent/Child` and it references the parent via --parent-domain-id.

This script is the reproducible source of truth for the domain tree. It is idempotent: it lists existing
tag policies + domains and creates only what is missing, so re-runs are safe. Pages (content-as-code in
docs/ontology/pages/) attach to these domains after this runs — see docs/RUNBOOK.md.

Usage:
    python scripts/create_domains.py --profile ECT
"""
import argparse
import json
import subprocess
import sys

# Domain tree. tag_key is the human-readable display name. Subdomains use "Parent/Child" and parent=<root key>.
ROOT_KEY = "Care Protocol"
DOMAINS = [
    {
        "tag_key": ROOT_KEY,
        "parent": None,
        "subtitle": "HEDIS diabetes quality measures with a clinical terminology + ontology context layer.",
        "description": (
            "The Care Protocol domain holds the semantics for computing HEDIS diabetes quality measures from "
            "synthetic Epic/Clarity-shaped data, plus the terminology and ontology (ICD-10-CM hierarchy, LOINC, "
            "RxNorm, curated value sets) that give the measures meaning. HEDIS-aligned demo, not NCQA-certified."
        ),
    },
    {
        "tag_key": f"{ROOT_KEY}/Measures",
        "parent": ROOT_KEY,
        "subtitle": "HEDIS diabetes measures: GSD, KED, BPD, EED, SPD.",
        "description": (
            "Deterministic HEDIS-aligned measure results (Gold). GSD = Glycemic Status Assessment; KED = Kidney "
            "Health Evaluation; BPD = Blood Pressure control; EED = Eye Exam; SPD = Statin Therapy. Denominators, "
            "numerators, exclusions, and record-level evidence for traceability."
        ),
    },
    {
        "tag_key": f"{ROOT_KEY}/Terminology",
        "parent": ROOT_KEY,
        "subtitle": "LOINC, ICD-10-CM, RxNorm, curated value sets, and the ICD-10 hierarchy closure.",
        "description": (
            "The terminology and ontology layer: LOINC (labs), ICD-10-CM (diagnoses + subsumption hierarchy), "
            "RxNorm (medications), hand-curated HEDIS value sets (demo, not VSAC), and the transitive closure "
            "table that resolves cohorts by subsumption over the ICD-10-CM hierarchy."
        ),
    },
    {
        "tag_key": f"{ROOT_KEY}/Clinical Data",
        "parent": ROOT_KEY,
        "subtitle": "Conformed patient, condition, observation, and cohort tables (Silver/Gold).",
        "description": (
            "Conformed clinical data: diabetes diagnoses (ICD-10-CM mapped from SNOMED), lab observations (LOINC), "
            "the diabetes cohort resolved via the ICD-10 closure, and patient demographics. Synthetic (Synthea)."
        ),
    },
]


def db(args, profile, parse=True):
    """Run a databricks CLI command; return parsed JSON (when parse) or raw stdout."""
    cmd = ["databricks"] + args + ["--profile", profile]
    if parse:
        cmd += ["-o", "json"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{res.stderr.strip()}")
    if not parse:
        return res.stdout
    out = res.stdout.strip()
    return json.loads(out) if out else []


def ensure_tag_policy(tag_key, description, profile, existing_keys):
    if tag_key in existing_keys:
        print(f"  tag policy exists: {tag_key!r}")
        return
    print(f"  creating tag policy: {tag_key!r}")
    db(["tag-policies", "create-tag-policy", tag_key, "--description", description], profile)
    existing_keys.add(tag_key)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True, help="Databricks CLI profile (e.g. ECT).")
    args = ap.parse_args()
    profile = args.profile

    # --- governed tag policies (prereq for domains) ---
    print("Tag policies:")
    tp = db(["tag-policies", "list-tag-policies"], profile)
    tp_list = tp.get("tag_policies", tp) if isinstance(tp, dict) else tp
    existing_tag_keys = {p.get("tag_key") or p.get("key") for p in tp_list}
    for d in DOMAINS:
        ensure_tag_policy(d["tag_key"], d["subtitle"], profile, existing_tag_keys)

    # --- domains (idempotent by tag_key); root first so subdomains can reference its id ---
    print("Domains:")
    dom = db(["domains", "list-domains"], profile)
    dom_list = dom.get("domains", dom) if isinstance(dom, dict) else dom
    by_tag = {d.get("tag_key"): d for d in dom_list}

    def ensure_domain(spec, parent_id):
        key = spec["tag_key"]
        if key in by_tag:
            print(f"  domain exists: {key!r} ({by_tag[key]['domain_id']})")
            return by_tag[key]
        cmd = ["domains", "create-domain", key,
               "--subtitle", spec["subtitle"], "--description", spec["description"]]
        if parent_id:
            cmd += ["--parent-domain-id", parent_id]
        print(f"  creating domain: {key!r}" + (f" (parent {parent_id})" if parent_id else ""))
        created = db(cmd, profile)
        by_tag[key] = created
        return created

    root = ensure_domain(DOMAINS[0], None)
    root_id = root["domain_id"]
    for spec in DOMAINS[1:]:
        ensure_domain(spec, root_id)

    print(f"\nDone. Root domain {ROOT_KEY!r} = {root_id}; {len(DOMAINS) - 1} subdomain(s).")
    print("Next: author docs/ontology/pages/*.md and bulk-import via Genie Code (RUNBOOK).")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
