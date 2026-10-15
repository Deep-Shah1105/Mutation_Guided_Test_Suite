from __future__ import annotations
from typing import Any
from agents.util import traced, error_update


def adversary(state: dict[str, Any]) -> dict[str, Any]:
    try:
        ast_info = (state.get("analysis") or {}).get("ast", {})
        params = ast_info.get("parameters", [])
        proposed = [
            {"id": "EC-boundary-1", "category": "boundary", "description": "Exercise boundary values around each comparison.",
             "input_idea": f"Try boundary inputs for parameters {params}.", "expected_behavior": "Follow the implemented comparison and return path.", "priority": "high", "targets_mutants": []},
            {"id": "EC-empty-1", "category": "type", "description": "Check empty strings or collections where applicable.",
             "input_idea": "Try an empty string/list/dict for compatible parameters.", "expected_behavior": "Return the function's documented or implied result, or raise the intended exception.", "priority": "medium", "targets_mutants": []},
        ]
        existing = state.get("edge_cases", [])
        seen = {item.get("description") for item in existing}
        additions = [item for item in proposed if item.get("description") not in seen]
        combined = existing + additions
        return traced(state, "adversary", "edge_cases_proposed",
                      {"added": len(additions), "total": len(combined), "llm_used": False},
                      {"edge_cases": combined, "needs_regeneration": False})
    except Exception as exc:
        return {**error_update(state, "adversary", f"{type(exc).__name__}: {exc}"), "edge_cases": state.get("edge_cases", [])}
