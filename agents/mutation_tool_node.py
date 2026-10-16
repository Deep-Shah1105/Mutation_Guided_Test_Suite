from __future__ import annotations
import os
from tools.mutmut_runner import run_mutmut
from agents.util import traced, error_update


def run_mutations(state: dict) -> dict:
    try:
        use_fallback = bool(state.get("mutmut_failed", False))
        result = run_mutmut(state.get("source_code", ""), state.get("generated_tests", ""),
                            timeout_seconds=int(os.getenv("MUTATION_TIMEOUT_SECONDS", "45")),
                            prefer_fallback=use_fallback)
        attempts = int(state.get("mutation_attempts", 0)) + 1
        rounds = int(state.get("round_index", 0)) + (1 if result.get("status") == "completed" else 0)
        return traced(state, "mutation_runner", "mutation_run_completed",
                      {"engine": result.get("engine"), "status": result.get("status"),
                       "total": result.get("total"), "killed": result.get("killed"),
                       "survivor_count": len(result.get("survived", [])),
                       "fallback_reason": result.get("fallback_reason")},
                      {"mutation_result": result, "mutation_attempts": attempts, "round_index": rounds,
                       "mutmut_failed": bool(state.get("mutmut_failed", False) or result.get("status") == "error"),
                       "mutation_analysis": {}, "needs_regeneration": False})
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        return {**error_update(state, "mutation_runner", message),
                "mutation_result": {"status": "error", "engine": "mutmut", "error": message},
                "mutation_attempts": int(state.get("mutation_attempts", 0)) + 1,
                "mutmut_failed": True}
