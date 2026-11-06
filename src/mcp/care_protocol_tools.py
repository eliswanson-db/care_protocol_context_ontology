"""Governed, deterministic tools for the Care Protocol domain (A6 custom MCP).

These are the heart of the A6 arm: instead of an LLM generating SQL (A2), a supervisor calls these
*trusted* tools, each a fixed, reviewed query over the governed semantic layer. They encode the ontology
(subsumption closures, value sets, metric views) so answers are deterministic and auditable.

Each function takes a `query(sql) -> list[dict]` callable, so the same logic runs against any executor
(the SQL warehouse via the SDK, `aitools query`, or Lakebase). No LLM, no free-form SQL generation.
Catalog/schema are injected once via make_tools(catalog).
"""
from __future__ import annotations

# table = gold EVIDENCE base; view = governed metric view (the rule lives here, computed live); gap = the
# NOT_MET predicate derived from evidence (same rule the metric view applies), for the per-patient care-gap list.
MEASURES = {
    "GSD": {"table": "gold_adherence_gsd", "view": "gsd_compliance_metrics", "rate": "GSD Compliance Rate", "numerator": "Compliant Patients",
            "gap": "evidence_datetime IS NULL", "name": "Glycemic Status Assessment", "age": "18-75"},
    "KED": {"table": "gold_adherence_ked", "view": "ked_compliance_metrics", "rate": "KED Compliance Rate", "numerator": "Compliant Patients",
            "gap": "egfr_datetime IS NULL OR uacr_datetime IS NULL", "name": "Kidney Health Evaluation", "age": "18-85"},
    "BPD": {"table": "gold_adherence_bpd", "view": "bpd_compliance_metrics", "rate": "BPD Compliance Rate", "numerator": "Controlled Patients",
            "gap": "systolic IS NULL OR systolic >= 140 OR diastolic >= 90", "name": "Blood Pressure control", "age": "18-75"},
    "SPD": {"table": "gold_adherence_spd", "view": "spd_compliance_metrics", "rate": "SPD Compliance Rate", "numerator": "On Statin Patients",
            "gap": "evidence_datetime IS NULL", "name": "Statin Therapy", "age": "40-75"},
    "EED": {"table": "gold_adherence_eed", "view": "eed_compliance_metrics", "rate": "EED Compliance Rate", "numerator": "Eye Exam Patients",
            "gap": "evidence_datetime IS NULL", "name": "Eye Exam", "age": "18-75"},
}
CLOSURES = {"ICD10CM": "icd10_closure", "RXNORM": "rxnorm_closure"}


def make_tools(catalog: str, schema: str = "care_protocol", term_schema: str = "care_protocol_terminology",
               semantic_schema: str = "care_protocol_semantic"):
    """Bind the tool set to a catalog/schema. Returns a dict of {tool_name: callable(query, **kwargs)}."""
    care = f"{catalog}.{schema}"
    term = f"{catalog}.{term_schema}"
    sem = f"{catalog}.{semantic_schema}"

    def get_measure_rate(query, measure_id: str) -> dict:
        """Compliance rate for a HEDIS measure (GSD/KED/BPD/SPD/EED), from the GOVERNED metric view — the rule
        lives in the semantic layer and is computed live (not a baked flag in gold)."""
        m = MEASURES.get(measure_id.upper())
        if not m:
            return {"error": f"unknown measure {measure_id!r}; known: {', '.join(MEASURES)}"}
        rows = query(
            f"SELECT MEASURE(`Eligible Patients`) AS eligible, MEASURE(`{m['numerator']}`) AS numerator, "
            f"ROUND(MEASURE(`{m['rate']}`), 4) AS rate FROM {sem}.{m['view']}")
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
        gap = m["gap"]  # the NOT_MET predicate, derived from evidence (same rule the metric view applies)
        rows = query(
            f"SELECT patient_id, age FROM {care}.{m['table']} "
            f"WHERE {gap} ORDER BY age DESC LIMIT {int(limit)}")
        total = query(f"SELECT COUNT(*) AS n FROM {care}.{m['table']} WHERE {gap}")[0]["n"]
        return {"measure_id": measure_id.upper(), "care_gap_count": int(total), "sample": rows}

    return {
        "get_measure_rate": get_measure_rate,
        "diabetes_cohort_size": diabetes_cohort_size,
        "subsumption_expand": subsumption_expand,
        "resolve_value_set": resolve_value_set,
        "list_care_gaps": list_care_gaps,
    }
