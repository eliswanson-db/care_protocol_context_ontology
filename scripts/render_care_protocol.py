"""Render the committed care-protocol HTML to a PDF in a UC Volume (serverless task).

The care protocol (docs/care_protocol/html/*.html) is the version-controlled source of truth; this renders it
to PDF into /Volumes/<catalog>/care_protocol/documents/pdf/ so it can be parsed (ai_parse_document) and fed to
RAG / Pages / the graph. Pure-Python xhtml2pdf (no native deps) for reproducible serverless rendering.

See docs/BENCHMARK_CHARTER.md (lineage anchor) and docs/RUNBOOK.md.
"""
import argparse
import glob
import os

from xhtml2pdf import pisa


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src_dir", required=True, help="Workspace dir with care-protocol *.html.")
    ap.add_argument("--out_dir", required=True, help="Target Volume dir for the rendered PDFs.")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    files = sorted(glob.glob(os.path.join(args.src_dir, "*.html")))
    if not files:
        raise SystemExit(f"No *.html found in {args.src_dir}")

    for html_path in files:
        out_path = os.path.join(args.out_dir, os.path.basename(html_path)[:-5] + ".pdf")
        with open(html_path) as f:
            html = f.read()
        with open(out_path, "wb") as out:
            result = pisa.CreatePDF(html, dest=out)
        if result.err:
            raise SystemExit(f"PDF render failed for {html_path}: {result.err} error(s)")
        print(f"  rendered {os.path.basename(out_path)} ({os.path.getsize(out_path)} bytes)")

    print(f"Rendered {len(files)} care-protocol PDF(s) to {args.out_dir}.")


if __name__ == "__main__":
    main()
