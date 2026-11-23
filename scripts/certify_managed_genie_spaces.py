"""Certify the bundle's managed Genie spaces (system.certification_status = certified), like the metric views.

On ECT the only certified HEDIS Genie space was a stale dev copy, and it was the largest source of Genie One's inferred
snippets; none of the seven managed (ect) spaces was certified (docs/ontology/GENIE_SPACES_FLAGGED.md). This tags only
the spaces this bundle deploys (titles + body files from the bundle config). It never touches any other space.

    .venv/bin/python -I scripts/certify_managed_genie_spaces.py --profile ECT            # dry run: list what it would tag
    .venv/bin/python -I scripts/certify_managed_genie_spaces.py --profile ECT --apply    # tag them

Reversible: delete the tag assignment (databricks workspace-entity-tag-assignments delete-tag-assignment geniespaces
<space_id> system.certification_status).
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import DatabricksError
from databricks.sdk.service.tags import TagAssignment

ROOT = Path(__file__).resolve().parents[1]
KEY, VALUE = "system.certification_status", "certified"


def _titles() -> dict[str, str]:
    spec = importlib.util.spec_from_file_location("ex", ROOT / "scripts/exercise_genie_spaces.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m._titles()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    w = WorkspaceClient(profile=a.profile)
    spaces = {s.title: s.space_id for s in w.genie.list_spaces().spaces or []}
    failed = 0
    for res, title in sorted(_titles().items()):
        sid = spaces.get(title)
        if not sid:
            print(f"skip   {title}: not deployed")
            continue
        cur = {t.tag_key: t.tag_value for t in w.workspace_entity_tag_assignments.list_tag_assignments("geniespaces", sid)}
        if cur.get(KEY) == VALUE:
            print(f"ok     {title} ({sid}) already certified")
            continue
        if not a.apply:
            print(f"would  certify {title} ({sid}); current: {cur.get(KEY) or 'none'}")
            continue
        try:
            w.workspace_entity_tag_assignments.create_tag_assignment(
                TagAssignment(entity_type="geniespaces", entity_id=sid, tag_key=KEY, tag_value=VALUE))
            print(f"tagged {title} ({sid})")
        except DatabricksError as e:
            failed += 1
            print(f"FAILED {title} ({sid}): {str(e).splitlines()[0][:200]}")
    if failed:
        raise SystemExit(f"{failed} space(s) not certified")


if __name__ == "__main__":
    main()
