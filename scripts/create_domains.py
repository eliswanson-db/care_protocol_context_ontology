"""Create the Care Protocol business domains + subdomains on a workspace (idempotent).

ADR-0008: domains are NOT a DAB resource. They are created via the Beta `databricks domains` API, and each
domain is built on a GOVERNED TAG (`databricks tag-policies`). A domain's displayed name IS its tag_key;
a subdomain's tag_key is `Parent/Child` and it references the parent via --parent-domain-id.

This script is the reproducible source of truth for the domain tree. It is idempotent: it lists existing
tag policies + domains and creates only what is missing, so re-runs are safe. Pages (content-as-code in
docs/ontology/pages/) attach to these domains after this runs — see docs/RUNBOOK.md.

A domain's displayed name IS its tag_key. On a fresh workspace, pass the default root tag and the script
creates the governed tags + full tree. On an account at the tag-policy cap (e.g. ECT — ADR-0008/RUNBOOK),
new tags can't be created, so pass --root-tag with an EXISTING free governed tag to reuse; the script then
creates only the root domain (subdomain tags can't be minted under the cap) and skips the rest gracefully.

Usage:
    python scripts/create_domains.py --profile ECT                          # fresh workspace: full tree
    python scripts/create_domains.py --profile ECT --root-tag "Clinical Domain"   # capped: reuse a free tag
"""
import argparse
import json
import subprocess
import sys

# Domain tree. tag_key is the human-readable display name. Subdomains use "Parent/Child" and parent=<root key>.
# ROOT_KEY is the default; overridable via --root-tag (to reuse an existing free governed tag under the cap).
ROOT_KEY = "Care Protocol"


def build_domains(root_key):
  return [
    {
        "tag_key": root_key,
        "parent": None,
        "subtitle": "HEDIS diabetes quality measures with a clinical terminology + ontology context layer.",
        "description": (
            "The Care Protocol domain holds the semantics for computing HEDIS diabetes quality measures from "
            "synthetic Epic/Clarity-shaped data, plus the terminology and ontology (ICD-10-CM hierarchy, LOINC, "
            "RxNorm, curated value sets) that give the measures meaning. HEDIS-aligned demo, not NCQA-certified."
        ),
    },
    {
        "tag_key": f"{root_key}/Measures",
        "parent": root_key,
        "subtitle": "HEDIS diabetes measures: GSD, KED, BPD, EED, SPD.",
        "description": (
            "Deterministic HEDIS-aligned measure results (Gold). GSD = Glycemic Status Assessment; KED = Kidney "
            "Health Evaluation; BPD = Blood Pressure control; EED = Eye Exam; SPD = Statin Therapy. Denominators, "
            "numerators, exclusions, and record-level evidence for traceability."
        ),
    },
    {
        "tag_key": f"{root_key}/Terminology",
        "parent": root_key,
        "subtitle": "LOINC, ICD-10-CM, RxNorm, curated value sets, and the ICD-10 hierarchy closure.",
        "description": (
            "The terminology and ontology layer: LOINC (labs), ICD-10-CM (diagnoses + subsumption hierarchy), "
            "RxNorm (medications), hand-curated HEDIS value sets (demo, not VSAC), and the transitive closure "
            "table that resolves cohorts by subsumption over the ICD-10-CM hierarchy."
        ),
    },
    {
        "tag_key": f"{root_key}/Clinical Data",
        "parent": root_key,
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
    """Ensure a governed tag policy exists. Returns True if usable (pre-existing or created),
    False if it couldn't be created because the account is at its tag-policy cap."""
    if tag_key in existing_keys:
        print(f"  tag policy exists (reuse): {tag_key!r}")
        return True
    print(f"  creating tag policy: {tag_key!r}")
    try:
        db(["tag-policies", "create-tag-policy", tag_key, "--description", description], profile)
        existing_keys.add(tag_key)
        return True
    except RuntimeError as e:
        if "maximum number of tag policies" in str(e).lower():
            print(f"  SKIP {tag_key!r}: account at tag-policy cap (cannot mint new governed tags). See ADR-0008.")
            return False
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True, help="Databricks CLI profile (e.g. ECT).")
    ap.add_argument("--root-tag", default=ROOT_KEY,
                    help=f"Governed tag key backing the root domain (default {ROOT_KEY!r}). On a capped account, "
                         "pass an EXISTING free governed tag to reuse (e.g. 'Clinical Domain').")
    args = ap.parse_args()
    profile = args.profile
    domains = build_domains(args.root_tag)

    # --- governed tag policies (prereq for domains); track which tag_keys are usable ---
    print("Tag policies:")
    tp = db(["tag-policies", "list-tag-policies"], profile)
    tp_list = tp.get("tag_policies", tp) if isinstance(tp, dict) else tp
    existing_tag_keys = {p.get("tag_key") or p.get("key") for p in tp_list}
    usable = {}
    for d in domains:
        usable[d["tag_key"]] = ensure_tag_policy(d["tag_key"], d["subtitle"], profile, existing_tag_keys)

    # --- domains (idempotent by tag_key); root first so subdomains can reference its id ---
    print("Domains:")
    dom = db(["domains", "list-domains"], profile)
    dom_list = dom.get("domains", dom) if isinstance(dom, dict) else dom
    by_tag = {d.get("tag_key"): d for d in dom_list}

    def ensure_domain(spec, parent_id):
        key = spec["tag_key"]
        if not usable.get(key):
            print(f"  SKIP domain {key!r}: backing tag unavailable (cap).")
            return None
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

    root = ensure_domain(domains[0], None)
    if root is None:
        raise RuntimeError(
            f"Root domain tag {args.root_tag!r} is unavailable and could not be created (account at tag-policy "
            "cap). Re-run with --root-tag set to an existing free governed tag. See docs/RUNBOOK.md.")
    root_id = root["domain_id"]
    made = 0
    for spec in domains[1:]:
        if ensure_domain(spec, root_id) is not None:
            made += 1

    print(f"\nDone. Root domain {args.root_tag!r} = {root_id}; {made} subdomain(s) created/present.")
    if made < len(domains) - 1:
        print("Some subdomains were skipped (tag-policy cap). Pages can still attach to the root domain.")
    print("Next: author docs/ontology/pages/*.md and bulk-import via Genie Code (RUNBOOK).")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
