from __future__ import annotations
from typing import Any
from core.llm import ask_json
from tools.ast_parser import analyse_code
from agents.util import traced, error_update


def code_analyst(state: dict[str, Any]) -> dict[str, Any]:
    try:
        facts = analyse_code(state["source_code"], state.get("function_name"))
        prompt = f"""Analyse this Python function for test design. Identify behavior, branch boundaries,
likely failure modes, argument types that can be inferred, and uncertainties. Do not invent a
specification that is not implied by the code. Return JSON keys: purpose, behavior_points (list),
branch_targets (list), risks (list), assumptions (list), recommended_analysis_depth (brief|normal|deep).

AST facts: {facts}
User notes: {state.get('request_notes', '')}
Source:
```python
{state['source_code']}
```"""
        insight = ask_json("You are the Code Analyst agent in a mutation-guided test generation system.", prompt)
        if insight and insight.get("_llm_error"):
            err_update = error_update(state, "code_analyst", insight["_llm_error"])
            event_update = traced(state, "code_analyst", "analysis_completed_with_fallback", {"function": facts["function_name"]},
                                 {"analysis": {"ast": facts, "llm_notes": {}, "llm_available": False}})
            merged = {**err_update, **event_update}
            merged["trace_events"] = err_update.get("trace_events", []) + event_update.get("trace_events", [])
            merged["errors"] = err_update.get("errors", [])
            return merged
        analysis = {"ast": facts, "llm_notes": insight or {}, "llm_available": insight is not None}
        return traced(state, "code_analyst", "analysis_completed",
                      {"function": facts["function_name"], "complexity": facts["decision_complexity_estimate"],
                       "branches": facts["branch_count"], "llm_used": insight is not None},
                      {"function_name": facts["function_name"], "analysis": analysis})
    except Exception as exc:
        return {**error_update(state, "code_analyst", f"{type(exc).__name__}: {exc}"),
                "analysis": {"error": f"{type(exc).__name__}: {exc}"}}
