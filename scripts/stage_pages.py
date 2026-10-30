"""Stage the Genie Ontology Pages content into a UC Volume for Genie Code bulk import (serverless task).

The Page source lives in docs/ontology/pages/*.md (version-controlled). The bundle uploads the repo to the
workspace on deploy; this task copies those files into /Volumes/<catalog>/care_protocol/ontology_pages/ so
Genie Code (Discover -> Pages -> Bulk import) can read them from a governed Volume. Re-runnable (overwrites).

See docs/RUNBOOK.md (Pages). Reproducible-by-code: no manual upload.
"""
import argparse
import glob
import os
import shutil


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src_dir", required=True, help="Workspace dir holding the *.md Page sources.")
    ap.add_argument("--volume_dir", required=True, help="Target Volume dir, e.g. /Volumes/<cat>/care_protocol/ontology_pages")
    args = ap.parse_args()

    os.makedirs(args.volume_dir, exist_ok=True)
    files = sorted(glob.glob(os.path.join(args.src_dir, "*.md")))
    if not files:
        raise SystemExit(f"No *.md Page sources found in {args.src_dir}")

    for path in files:
        dest = os.path.join(args.volume_dir, os.path.basename(path))
        shutil.copyfile(path, dest)
        print(f"  staged {os.path.basename(path)}")

    print(f"Staged {len(files)} Page file(s) to {args.volume_dir}.")


if __name__ == "__main__":
    main()
