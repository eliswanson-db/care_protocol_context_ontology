"""Stage care-protocol SOURCE documents into a second UC Volume for Genie Code Pages bulk import (serverless task).

Companion to stage_pages.py. That one stages the finished Ontology Pages (docs/ontology/pages/*.md) into the
`ontology_pages` volume. THIS one stages the upstream, Pages-ready SOURCE material — the facts-only mined
extracts and the synthesized care-protocol corpus — into a separate `source_documents` volume, so you can
build MORE Pages from it via Genie Code (Discover -> Pages -> Bulk import) without mixing it with the
finished Pages.

Licensing (ADR-0002 / ADR-0015): only version-controlled, facts-only / synthetic Markdown is staged here.
Facts were paraphrased from public references; NO proprietary text is reproduced. The raw source PDFs are NOT
staged by this task: several (NCQA HEDIS SSD measure, HEDIS Quality Measure Toolkit, Johns Hopkins GSD page)
are proprietary and must not be redistributed via a Volume. The public-domain PDFs (VA/DoD CPG, CMS QRS tech
specs) MAY be uploaded manually — see docs/RUNBOOK.md ("Source-document volume").

Each file is staged flat as <group>__<name>.md (group = the source subdir) so bulk import sees a clean list.
Re-runnable (clears + rewrites the target). Reproducible-by-code: no manual upload for the Markdown.
"""
import argparse
import glob
import os
import shutil


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src_dir", action="append", required=True,
                    help="Workspace dir holding *.md source files. Repeatable; the dir's basename becomes the group prefix.")
    ap.add_argument("--volume_dir", required=True,
                    help="Target Volume dir, e.g. /Volumes/<cat>/care_protocol/source_documents")
    args = ap.parse_args()

    os.makedirs(args.volume_dir, exist_ok=True)
    # Clear prior run (flat *.md only; never touch anything else that may live in the volume, e.g. manually-uploaded PDFs).
    for old in glob.glob(os.path.join(args.volume_dir, "*.md")):
        os.remove(old)

    total = 0
    for src in args.src_dir:
        group = os.path.basename(os.path.normpath(src))
        files = sorted(glob.glob(os.path.join(src, "*.md")))
        if not files:
            print(f"  (no *.md in {src})")
            continue
        for path in files:
            dest = os.path.join(args.volume_dir, f"{group}__{os.path.basename(path)}")
            shutil.copyfile(path, dest)
            print(f"  staged {group}__{os.path.basename(path)}")
            total += 1

    if total == 0:
        raise SystemExit(f"No *.md source files found in {args.src_dir}")
    print(f"Staged {total} source Markdown file(s) to {args.volume_dir}. "
          f"Build Pages from these via Genie Code -> Discover -> Pages -> Bulk import.")


if __name__ == "__main__":
    main()
