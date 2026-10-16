from __future__ import annotations
from core.llm import ask_json
from agents.util import traced


def reporter(state: dict) -> dict:
    analysis = state.get("analysis") or {}
    ast_info = analysis.get("ast", {})
    pytest_result = state.get("pytest_result") or {}
    mutation = state.get("mutation_result") or {}
    mutation_analysis = state.get("mutation_analysis") or {}
    prompt = f"""Write a concise final report for a developer reviewing generated tests.
Be factual. Mention uncertainty or fallback behavior; do not claim a mutation score if unavailable.
Return JSON keys: headline, summary, strengths (list), remaining_gaps (list), next_steps (list).
Function: {ast_info.get('function_name')}
Pytest result: {pytest_result}
Critic review: {state.get('critic_review', {})}
Mutation result: {mutation}
Mutation analysis: {mutation_analysis}
Run errors: {state.get('errors', [])}
"""
    llm_report = ask_json("You are the Reporter agent. Summarize the run accurately and make uncertainty explicit.", prompt)
    if llm_report and llm_report.get("_llm_error"):
        llm_report = None
    if llm_report is None:
        llm_report = {
            "headline": "Test generation run completed with caveats",
            "summary": (f"Function `{ast_info.get('function_name', 'unknown')}`: pytest status is "
                        f"{pytest_result.get('status', 'not run')}; mutation engine is "
                        f"{mutation.get('engine', 'not run')} with status {mutation.get('status', 'not run')}."),
            "strengths": (["Generated tests executed in a subprocess."] if pytest_result.get("status") else []),
            "remaining_gaps": list(mutation_analysis.get("uncertain", [])) + list(mutation_analysis.get("genuine_gaps", [])),
            "next_steps": ["Review generated tests and mutation output manually.",
                           "Configure the LLM API key for agent-driven reasoning and critic review."],
        }
    report = {
        **llm_report,
        "run_id": state.get("run_id"),
        "function_name": ast_info.get("function_name", state.get("function_name")),
        "pytest": pytest_result,
        "critic": state.get("critic_review", {}),
        "mutation": mutation,
        "mutation_analysis": mutation_analysis,
        "revision_count": state.get("revision_count", 0),
        "round_index": state.get("round_index", 0),
        "errors": state.get("errors", []),
        "trace_path": state.get("trace_path", "trace.jsonl"),
    }
    return traced(state, "reporter", "final_report_created",
                  {"pytest_status": pytest_result.get("status"), "mutation_status": mutation.get("status"),
                   "rounds": state.get("round_index", 0)}, {"report": report})
