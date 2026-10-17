from __future__ import annotations
import os
from core.llm import ask_json
from tools.pytest_runner import run_pytest
from agents.util import traced, error_update


def _fallback_test(function_name: str) -> str:
    # Intentionally weak fallback: the critic should reject it. A real run should use the configured LLM.
    return ("import pytest\nfrom candidate import " + function_name + "\n\n"
            f"def test_{function_name}_is_callable():\n"
            f"    assert callable({function_name})\n")


def test_writer(state: dict) -> dict:
    function_name = state.get("function_name") or (state.get("analysis") or {}).get("ast", {}).get("function_name")
    if not function_name:
        return {**error_update(state, "test_writer", "Cannot write tests because function_name is unknown."),
                "generated_tests": "", "pytest_result": {"status": "error", "passed": False, "output": "Unknown function."}}
    test_code = state.get("generated_tests", "")
    last_output = (state.get("pytest_result") or {}).get("output", "")
    prior_feedback = (state.get("critic_review") or {}).get("revision_instructions", [])
    max_repairs = 2
    llm_used = False
    repair_log = []
    for attempt in range(max_repairs + 1):
        prompt = f"""Write a strong pytest test module for the function source shown below. Tests import the function from `candidate`.
Use explicit expected values or specific exceptions, not vacuous assertions such as `is not None` or merely checking callability.
Cover normal behavior, boundaries, branches and the supplied edge cases. Do not test invented requirements; mark uncertainty clearly.
Return JSON with key `tests` containing the entire Python test file as a string.
Function name: {function_name}
User notes: {state.get('request_notes', '')}
Analysis: {state.get('analysis', {})}
Edge cases: {state.get('edge_cases', [])}
Surviving mutants and analysis: {(state.get('mutation_result') or {}).get('survived', [])} / {state.get('mutation_analysis', {})}
Measured coverage from previous run: {(state.get('pytest_result') or {}).get('coverage', {})}
Coverage feedback: {(state.get('mutation_analysis') or {}).get('coverage_gaps', [])}
Critic feedback: {prior_feedback}
When revising, add targeted tests for uncovered lines/branches and surviving mutants; do not merely duplicate existing cases.
Prior test code (revise it if present):
```python
{test_code}
```
Prior pytest output / repair target:
{last_output[-6000:]}
Attempt: {attempt + 1} of {max_repairs + 1}
Function source:
```python
{state['source_code']}
```"""
        response = ask_json("You are the Test Writer agent. Generate executable, discriminating pytest tests.", prompt)
        if response and response.get("_llm_error"):
            err = response["_llm_error"]
            repair_log.append({"attempt": attempt + 1, "llm_error": err})
            test_code = test_code or _fallback_test(function_name)
        elif response and isinstance(response.get("tests"), str) and response["tests"].strip():
            test_code = response["tests"].strip()
            llm_used = True
        elif not test_code:
            test_code = _fallback_test(function_name)
        # Keep generated modules self-contained; generated tests must import the candidate module.
        if "from candidate import" not in test_code and "import candidate" not in test_code:
            test_code = f"import candidate\n\n" + test_code
        timeout = int(os.getenv("AGENT_TIMEOUT_SECONDS", "15"))
        test_result = run_pytest(state["source_code"], test_code, timeout_seconds=timeout, collect_coverage=True)
        repair_log.append({"attempt": attempt + 1, "status": test_result["status"]})
        if test_result["passed"] or attempt == max_repairs:
            break
        last_output = test_result.get("output", "")
    previous_revision = int(state.get("revision_count", 0))
    updates = {
        "generated_tests": test_code,
        "pytest_result": test_result,
        "coverage_result": test_result.get("coverage", {}),
        "critic_review": {},
        "mutation_result": {},
        "mutation_analysis": {},
        "needs_regeneration": False,
        "revision_count": previous_revision + (1 if state.get("generated_tests") else 0),
    }
    return traced(state, "test_writer", "tests_generated_and_executed",
                  {"pytest_status": test_result["status"], "pytest_passed": test_result["passed"],
                   "repair_attempts": len(repair_log), "llm_used": llm_used, "test_characters": len(test_code)}, updates)
