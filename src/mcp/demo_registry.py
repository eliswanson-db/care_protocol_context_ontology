"""Demo-scoped tool registry (prompt §6 / §13): backend enforcement of demo isolation for A6.

A caller gets the tools and supervisor of exactly ONE demo. There is no API that returns tools across demos,
so a healthcare question can't reach clinical-study tables through A6 (or the reverse), whatever the prompt
says.
"""

from __future__ import annotations

from collections.abc import Callable

DEMOS = ("healthcare_hedis", "life_sciences_clinical")


class DemoScopeError(ValueError):
    pass


def tools_for(demo_id: str, catalog: str) -> dict[str, Callable]:
    if demo_id == "healthcare_hedis":
        from care_protocol_tools import make_tools
    elif demo_id == "life_sciences_clinical":
        from clinical_study_tools import make_tools
    else:
        raise DemoScopeError(f"unknown demo {demo_id!r}; one of {DEMOS}")
    return make_tools(catalog)


def answer(demo_id: str, question: str, catalog: str, query) -> dict:
    """Route a question with the demo's own supervisor and tools only."""
    tools = tools_for(demo_id, catalog)
    if demo_id == "healthcare_hedis":
        import supervisor as sup
    else:
        import clinical_study_supervisor as sup
    out = sup.answer(question, tools, query)
    out["demo_id"] = demo_id
    return out
