"""Authorize a Databricks App service principal to read the A4 RAG corpus (ADR-0014 RLS).

The Lakebase corpus is doc-level RLS-protected (rag.acl_allows): an unknown identity sees ZERO documents, so
a deployed app SP returns nothing until it's (a) provisioned as a Postgres role and (b) authorized via the ACL.
This does (b) + the SQL grants; (a) is a one-time CLI step done first:

    SP=<app service principal client id>            # databricks apps get <app> -> service_principal_client_id
    databricks postgres create-role projects/care-protocol/branches/production \
      --role-id care-protocol-app \
      --json "{\"spec\":{\"identity_type\":\"SERVICE_PRINCIPAL\",\"postgres_role\":\"$SP\",\"auth_method\":\"LAKEBASE_OAUTH_V1\"}}" \
      --profile DMVM
    python3 -I scripts/lakebase_grant_app_reader.py --sp "$SP" --profile DMVM

This keeps RLS fully ON — the SP is a normal authorized reader via a group (care_app_service), NOT a bypass.
Run as a Lakebase admin (the connecting profile identity). Idempotent. Reversible: REVOKE rag_reader + delete
the group_membership / document_acl rows.
"""
import argparse

import psycopg
from databricks.sdk import WorkspaceClient


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sp", required=True, help="app SP's postgres_role (= its client id)")
    ap.add_argument("--group", default="care_app_service", help="ACL group to authorize on all docs")
    ap.add_argument("--profile", default=None)
    ap.add_argument("--endpoint", default="projects/care-protocol/branches/production/endpoints/primary")
    ap.add_argument("--admin_user", default=None, help="Lakebase admin identity (default: current user)")
    args = ap.parse_args()

    w = WorkspaceClient(profile=args.profile) if args.profile else WorkspaceClient()
    host = w.postgres.get_endpoint(args.endpoint).status.hosts.host
    token = w.postgres.generate_database_credential(args.endpoint).token
    admin = args.admin_user or w.current_user.me().user_name

    conn = psycopg.connect(host=host, user=admin, password=token, dbname="databricks_postgres", sslmode="require")
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(f'GRANT rag_reader TO "{args.sp}"')                      # SELECT rag.{documents,chunks} + EXECUTE acl_allows
        cur.execute(
            "INSERT INTO rag.group_membership (user_id, group_id) SELECT %s, %s "
            "WHERE NOT EXISTS (SELECT 1 FROM rag.group_membership WHERE user_id=%s AND group_id=%s)",
            (args.sp, args.group, args.sp, args.group))
        cur.execute("SELECT document_id FROM rag.documents")
        docs = [r[0] for r in cur.fetchall()]
        for d in docs:
            cur.execute(
                "INSERT INTO rag.document_acl (document_id, principal_type, principal_id, effect, permission) "
                "SELECT %s, 'GROUP', %s, 'ALLOW', 'READ' WHERE NOT EXISTS ("
                "  SELECT 1 FROM rag.document_acl WHERE document_id=%s AND principal_type='GROUP' "
                "    AND principal_id=%s AND permission='READ' AND effect='ALLOW')",
                (d, args.group, d, args.group))
        # Verify the RLS decision for the SP (we can't SET ROLE to it, but acl_allows is the policy itself).
        allowed = sum(cur.execute("SELECT rag.acl_allows(%s, %s)", (d, args.sp)) or cur.fetchone()[0] for d in docs)
    print(f"{args.sp}: rag_reader + group {args.group!r} ALLOW READ on {len(docs)} docs; acl_allows true for {allowed}/{len(docs)}.")


if __name__ == "__main__":
    main()
