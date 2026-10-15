from __future__ import annotations
from typing import Any
from tools.ast_parser import analyse_code
from agents.util import traced, error_update


def code_analyst(state: dict[str, Any]) -> dict[str, Any]:
    try:
        facts = analyse_code(state["source_code"], state.get("function_name"))
        analysis = {"ast": facts, "llm_notes": {}, "llm_available": False}
        return traced(state, "code_analyst", "analysis_completed",
                      {"function": facts["function_name"], "complexity": facts["decision_complexity_estimate"],
                       "branches": facts["branch_count"], "llm_used": False},
                      {"function_name": facts["function_name"], "analysis": analysis})
    except Exception as exc:
        return {**error_update(state, "code_analyst", f"{type(exc).__name__}: {exc}"),
                "analysis": {"error": f"{type(exc).__name__}: {exc}"}}
