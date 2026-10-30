"""Governed, deterministic tools for the Care Protocol domain (A6 custom MCP).

These are the heart of the A6 arm: instead of an LLM generating SQL (A2), a supervisor calls these
*trusted* tools, each a fixed, reviewed query over the governed semantic layer. They encode the ontology
(subsumption closures, value sets, metric views) so answers are deterministic and auditable.

Each function takes a `query(sql) -> list[dict]` callable, so the same logic runs against any executor
(the SQL warehouse via the SDK, `aitools query`, or Lakebase). No LLM, no free-form SQL generation.
Catalog/schema are injected once via make_tools(catalog).
"""
from __future__ import annotations

MEASURES = {
    "GSD": {"table": "gold_adherence_gsd", "name": "Glycemic Status Assessment", "age": "18-75"},
    "KED": {"table": "gold_adherence_ked", "name": "Kidney Health Evaluation", "age": "18-85"},
    "BPD": {"table": "gold_adherence_bpd", "name": "Blood Pressure control", "age": "18-75"},
    "SPD": {"table": "gold_adherence_spd", "name": "Statin Therapy", "age": "40-75"},
    "EED": {"table": "gold_adherence_eed", "name": "Eye Exam", "age": "18-75"},
}
CLOSURES = {"ICD10CM": "icd10_closure", "RXNORM": "rxnorm_closure"}


def make_tools(catalog: str, schema: str = "care_protocol", term_schema: str = "care_protocol_terminology"):
    """Bind the tool set to a catalog/schema. Returns a dict of {tool_name: callable(query, **kwargs)}."""
    care = f"{catalog}.{schema}"
    term = f"{catalog}.{term_schema}"

    def get_measure_rate(query, measure_id: str) -> dict:
        """Compliance rate for a HEDIS measure (GSD/KED/BPD/SPD/EED), computed deterministically from Gold."""
        m = MEASURES.get(measure_id.upper())
        if not m:
            return {"error": f"unknown measure {measure_id!r}; known: {', '.join(MEASURES)}"}
        rows = query(
            f"SELECT COUNT(*) AS eligible, SUM(CAST(numerator_flag AS INT)) AS numerator, "
            f"ROUND(AVG(CAST(numerator_flag AS INT)), 4) AS rate FROM {care}.{m['table']}")
        r = rows[0]
        return {"measure_id": measure_id.upper(), "measure_name": m["name"], "eligible_ages": m["age"],
                "eligible": int(r["eligible"]), "numerator": int(r["numerator"]),
                "compliance_rate": float(r["rate"]), "compliance_rate_pct": round(float(r["rate"]) * 100, 1)}

    def diabetes_cohort_size(query) -> dict:
        """Distinct patients in the diabetes cohort (ICD-10 subsumption over E10/E11/E13)."""
        rows = query(f"SELECT COUNT(*) AS n FROM {care}.silver_diabetes_cohort")
        return {"cohort": "diabetes", "method": "ICD-10-CM subsumption (E10/E11/E13 + descendants)",
                "patient_count": int(rows[0]["n"])}

    def subsumption_expand(query, code_system: str, ancestor_code: str) -> dict:
        """Expand a code to all descendants via the transitive closure (ICD-10-CM or RxNorm)."""
        cl = CLOSURES.get(code_system.upper())
        if not cl:
            return {"error": f"no closure for {code_system!r}; known: {', '.join(CLOSURES)}"}
        rows = query(
            f"SELECT descendant_code, descendant_name, depth FROM {term}.{cl} "
            f"WHERE ancestor_code = '{ancestor_code}' ORDER BY depth, descendant_code")
        return {"code_system": code_system.upper(), "ancestor_code": ancestor_code,
                "descendants": rows, "count": len(rows)}

    def resolve_value_set(query, segment_id: str) -> dict:
        """Return the codes in a value set (the governed definition used by the measures)."""
        rows = query(
            f"SELECT code, code_system, measurement_year FROM {term}.value_set_segment "
            f"WHERE segment_id = '{segment_id}' ORDER BY measurement_year, code")
        return {"segment_id": segment_id, "codes": rows, "count": len(rows)}

    def list_care_gaps(query, measure_id: str, limit: int = 20) -> dict:
        """Patients eligible but NOT_MET for a measure (the actionable care-gap list)."""
        m = MEASURES.get(measure_id.upper())
        if not m:
            return {"error": f"unknown measure {measure_id!r}"}
        rows = query(
            f"SELECT patient_id, age, status FROM {care}.{m['table']} "
            f"WHERE status = 'NOT_MET' ORDER BY age DESC LIMIT {int(limit)}")
        total = query(f"SELECT COUNT(*) AS n FROM {care}.{m['table']} WHERE status = 'NOT_MET'")[0]["n"]
        return {"measure_id": measure_id.upper(), "care_gap_count": int(total), "sample": rows}

    return {
        "get_measure_rate": get_measure_rate,
        "diabetes_cohort_size": diabetes_cohort_size,
        "subsumption_expand": subsumption_expand,
        "resolve_value_set": resolve_value_set,
        "list_care_gaps": list_care_gaps,
    }
