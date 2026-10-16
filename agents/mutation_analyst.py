from __future__ import annotations
from core.llm import ask_json
from agents.util import traced, error_update


def _coverage_gap_strings(coverage: dict) -> list[str]:
    if not isinstance(coverage, dict) or coverage.get("status") != "collected":
        return []
    gaps = [f"uncovered source line {line}" for line in coverage.get("missing_lines", [])]
    gaps.extend(f"uncovered branch {branch}" for branch in coverage.get("missing_branches", []))
    return gaps


def mutation_analyst(state: dict) -> dict:
    mutation = state.get("mutation_result") or {}
    prompt = f"""Interpret this mutation-testing result. Do not claim equivalence without evidence.
Classify each surviving mutant as a likely genuine test gap, likely equivalent mutant, or uncertain.
Also convert measured missing lines and branches into coverage_gaps (list of concise strings). Recommend concrete tests targeting them.
Return JSON keys: genuine_gaps (list), likely_equivalent (list), uncertain (list), coverage_gaps (list), recommendations (list), summary (string).
Function:
```python
{state.get('source_code', '')}
```
Tests:
```python
{state.get('generated_tests', '')}
```
Mutation result: {mutation}
AST analysis: {state.get('analysis', {})}
Measured coverage: {(state.get('pytest_result') or {}).get('coverage', {})}
"""
    response = ask_json("You are the Mutation Analyst agent. Critically distinguish real test gaps from equivalent mutants.", prompt)
    llm_used = response is not None and not response.get("_llm_error")
    if response and response.get("_llm_error"):
        return {**error_update(state, "mutation_analyst", response["_llm_error"]),
                **traced(state, "mutation_analyst", "classification_fallback", {"reason": "LLM request failed"},
                         {"mutation_analysis": {"genuine_gaps": [], "likely_equivalent": [],
                                                "uncertain": (mutation.get("survived") or []),
                                                "coverage_gaps": _coverage_gap_strings((state.get("pytest_result") or {}).get("coverage", {})),
                                                "recommendations": ["Configure the API key and rerun classification."],
                                                "summary": "Survivors remain unclassified; no semantic claims made."}})}
    if response is None:
        coverage_gaps = _coverage_gap_strings((state.get("pytest_result") or {}).get("coverage", {}))
        response = {"genuine_gaps": [], "likely_equivalent": [], "uncertain": mutation.get("survived", []),
                    "coverage_gaps": coverage_gaps,
                    "recommendations": ([f"Add tests targeting {gap}." for gap in coverage_gaps] +
                                        ["Inspect surviving mutant(s) manually or configure the LLM critic."]),
                    "summary": "Offline fallback cannot reliably classify equivalent mutants; measured coverage gaps are listed separately."}
    # Normalize the expected schema so the supervisor can route safely.
    for key in ("genuine_gaps", "likely_equivalent", "uncertain", "coverage_gaps", "recommendations"):
        if not isinstance(response.get(key), list):
            response[key] = []
    measured_gaps = _coverage_gap_strings((state.get("pytest_result") or {}).get("coverage", {}))
    response["coverage_gaps"] = list(dict.fromkeys(response["coverage_gaps"] + measured_gaps))
    return traced(state, "mutation_analyst", "survivors_classified",
                  {"genuine_gap_count": len(response["genuine_gaps"]),
                   "equivalent_count": len(response["likely_equivalent"]),
                   "uncertain_count": len(response["uncertain"]),
                   "coverage_gap_count": len(response["coverage_gaps"]), "llm_used": llm_used},
                  {"mutation_analysis": response})
