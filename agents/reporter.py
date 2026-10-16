from __future__ import annotations
from agents.util import traced


def reporter(state: dict) -> dict:
    analysis = state.get("analysis") or {}
    ast_info = analysis.get("ast", {})
    pytest_result = state.get("pytest_result") or {}
    mutation = state.get("mutation_result") or {}
    mutation_analysis = state.get("mutation_analysis") or {}
    summary = {
        "headline": "Test generation run completed with caveats",
        "summary": (f"Function `{ast_info.get('function_name', 'unknown')}`: pytest status is "
                    f"{pytest_result.get('status', 'not run')}; mutation engine is "
                    f"{mutation.get('engine', 'not run')} with status {mutation.get('status', 'not run')}."),
        "strengths": (["Generated tests executed in a subprocess."] if pytest_result.get("status") else []),
        "remaining_gaps": list(mutation_analysis.get("uncertain", [])) + list(mutation_analysis.get("genuine_gaps", [])),
        "next_steps": ["Review generated tests and mutation output manually."],
    }
    report = {
        **summary,
        "run_id": state.get("run_id"),
        "function_name": ast_info.get("function_name", state.get("function_name")),
        "pytest": pytest_result,
        "mutation": mutation,
        "mutation_analysis": mutation_analysis,
        "errors": state.get("errors", []),
        "trace_path": state.get("trace_path", "trace.jsonl"),
    }
    return traced(state, "reporter", "final_report_created",
                  {"pytest_status": pytest_result.get("status"), "mutation_status": mutation.get("status")},
                  {"report": report})
