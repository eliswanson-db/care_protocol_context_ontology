"""Care Protocol custom MCP server (A6) — exposes the governed tools over the MCP protocol.

A thin FastMCP wrapper around care_protocol_tools. Each MCP tool runs a fixed, reviewed query over the
governed semantic layer via a SQL warehouse (Statement Execution API), so a supervisor/agent gets
deterministic, auditable answers instead of generating SQL. Deploy as a Databricks App (see README.md);
locally, `python src/mcp/server.py` runs it over stdio for an MCP client.

Env: DATABRICKS_WAREHOUSE_ID (SQL warehouse), CARE_CATALOG (default eli_test_classic_catalog).
"""
import os

from databricks.sdk import WorkspaceClient
from mcp.server.fastmcp import FastMCP

from care_protocol_tools import make_tools

CATALOG = os.environ.get("CARE_CATALOG", "eli_test_classic_catalog")
WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID")

_w = WorkspaceClient()
_tools = make_tools(CATALOG)


def _query(sql: str):
    """Run read-only SQL on the configured warehouse; return a list of dict rows."""
    r = _w.statement_execution.execute_statement(warehouse_id=WAREHOUSE_ID, statement=sql, wait_timeout="30s")
    cols = [c.name for c in r.manifest.schema.columns] if r.manifest and r.manifest.schema else []
    data = (r.result.data_array if r.result and r.result.data_array else []) or []
    return [dict(zip(cols, row)) for row in data]


mcp = FastMCP("care-protocol")


@mcp.tool()
def get_measure_rate(measure_id: str) -> dict:
    """HEDIS measure compliance rate (measure_id in GSD, KED, BPD, SPD, EED), computed from governed Gold."""
    return _tools["get_measure_rate"](_query, measure_id)


@mcp.tool()
def diabetes_cohort_size() -> dict:
    """Count of patients in the diabetes cohort (ICD-10-CM subsumption over E10/E11/E13)."""
    return _tools["diabetes_cohort_size"](_query)


@mcp.tool()
def subsumption_expand(code_system: str, ancestor_code: str) -> dict:
    """Expand a code to all descendants via the transitive closure (code_system: ICD10CM or RXNORM)."""
    return _tools["subsumption_expand"](_query, code_system, ancestor_code)


@mcp.tool()
def resolve_value_set(segment_id: str) -> dict:
    """Return the governed codes in a value set (e.g. SPD_STATIN, KED_EGFR, GSD_A1C_TEST)."""
    return _tools["resolve_value_set"](_query, segment_id)


@mcp.tool()
def list_care_gaps(measure_id: str, limit: int = 20) -> dict:
    """List patients eligible but NOT_MET for a measure (the actionable care-gap list)."""
    return _tools["list_care_gaps"](_query, measure_id, limit)


if __name__ == "__main__":
    mcp.run()
