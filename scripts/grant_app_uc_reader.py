"""Grant a Databricks App's service principal the read-only UC privileges the lab needs (RUNBOOK, ECT app grants).

These used to be applied by hand from the RUNBOOK, so they vanished silently when infra deleted and recreated
`eswanson_demo` (2026-11-20). Re-run after a fresh app deploy or a catalog recreate. Idempotent (adding a privilege
the principal already has is a no-op); read-only privileges only, to the app's own identity. --dry-run prints them.

    .venv/bin/python -I scripts/grant_app_uc_reader.py --profile ECT --app care-protocol-context-ect [--dry-run]

Reversible: `REVOKE <privilege> ON <securable> FROM <sp>` for each line printed.
"""

from __future__ import annotations

import argparse

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import DatabricksError
from databricks.sdk.service.catalog import PermissionsChange, Privilege

LAB = "eli_test_classic_catalog"
ONTOBRICKS = "eswanson_demo"  # Ontobricks publishes every triplestore to eswanson_demo.ontobricks (Eli-owned)
READ = [Privilege.USE_SCHEMA, Privilege.SELECT]

GRANTS: list[tuple[str, str, list[Privilege]]] = [
    ("catalog", LAB, [Privilege.USE_CATALOG]),
    *[("schema", f"{LAB}.{s}", READ) for s in (
        "care_protocol", "care_protocol_semantic", "care_protocol_terminology",
        "clinical_study", "clinical_study_semantic", "clinical_study_standards", "clinical_study_graph",
    )],
    ("volume", f"{LAB}.care_protocol.documents", [Privilege.READ_VOLUME]),
    ("catalog", ONTOBRICKS, [Privilege.USE_CATALOG]),
    ("schema", f"{ONTOBRICKS}.ontobricks", READ),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--app", required=True, help="Databricks App name; its service principal gets the grants")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    w = WorkspaceClient(profile=a.profile)
    sp = w.apps.get(a.app).service_principal_client_id
    failed = 0
    for kind, name, privs in GRANTS:
        line = f"{kind:7} {name:55} {', '.join(p.value for p in privs)}"
        if a.dry_run:
            print("would grant", line)
            continue
        try:
            w.grants.update(kind, name, changes=[PermissionsChange(principal=sp, add=privs)])
            print("granted    ", line)
        except DatabricksError as e:  # keep going; report every failure, then exit non-zero
            failed += 1
            print("FAILED     ", line, "--", str(e).splitlines()[0][:160])
    done = f"{len(GRANTS)} planned (dry run)" if a.dry_run else f"{len(GRANTS) - failed}/{len(GRANTS)} applied"
    print(f"app {a.app} sp {sp}: {done}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
