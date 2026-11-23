"""Drop life-sciences tables whose producers were removed from the repo (approved by Eli, 2026-11-23).

Removing a table from the Lakeflow pipeline or a loader does not drop the table it once wrote, so these stay in the
catalog, stale, until dropped. Only the tables listed here are touched; each is checked first: it must exist, and no
code in the repo may still name it (the RETIRED reason says what replaced it).

    .venv/bin/python -I scripts/ls_drop_retired_tables.py --profile ECT            # dry run: what it would drop
    .venv/bin/python -I scripts/ls_drop_retired_tables.py --profile ECT --apply
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound

ROOT = Path(__file__).resolve().parents[1]
CATALOG = "eli_test_classic_catalog"
RETIRED = {
    "clinical_study.gold_tracer_registry":
        "registry of the hand-authored FX-* participants; they left the demo data (decision 1). The app picks "
        "heroes by rule (src/app/server/ls_heroes.py).",
    "clinical_study.rag_corpus":
        "old LS retrieval table; LS documents now live in the shared Lakebase corpus (corpus = clinical_study, "
        "scripts/lakebase_rag_corpus.py).",
}


def _still_referenced(table: str) -> list[str]:
    name = table.split(".")[-1]
    # a qualified reference (clinical_study.<name>, {CS}.<name>): a bare word can be a module alias or prose
    out = subprocess.run(["git", "grep", "-l", "-E", rf"\.{name}\b", "--", "*.py", "*.sql", "*.yml", "*.yaml", "*.ts", "*.tsx",
                          "*.ttl", ":!scripts/ls_drop_retired_tables.py"],
                         cwd=ROOT, capture_output=True, text=True, check=False).stdout.split()
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    w = WorkspaceClient(profile=a.profile)
    for t, why in RETIRED.items():
        full = f"{CATALOG}.{t}"
        refs = _still_referenced(t)
        if refs:
            raise SystemExit(f"{full}: still named in {refs}; not dropping")
        try:
            w.tables.get(full)
        except NotFound:
            print(f"gone     {full}")
            continue
        if not a.apply:
            print(f"would    drop {full} ({why})")
            continue
        w.tables.delete(full)
        print(f"dropped  {full}")


if __name__ == "__main__":
    main()
