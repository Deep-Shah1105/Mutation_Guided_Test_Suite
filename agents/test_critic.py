from __future__ import annotations
import re
from core.llm import ask_json
from agents.util import traced, error_update

WEAK_PATTERNS = [r"is not None", r"assert\s+True\b", r"assert\s+callable\(", r"assert\s+isinstance\("]


def test_critic(state: dict) -> dict:
    tests = state.get("generated_tests", "")
    prompt = f"""Critically assess whether these pytest tests would catch realistic incorrect implementations.
Reject tests that only check existence, type, callability, non-None, or that merely execute without failure.
Judge assertion specificity, branch coverage inferred from tests, boundary coverage, exception behavior, and unsupported assumptions.
Return JSON keys: approved (boolean), score (0-10), weaknesses (list), revision_instructions (list), rationale (string).
Source:
```python
{state.get('source_code', '')}
```
Tests:
```python
{tests}
```
Pytest result: {(state.get('pytest_result') or {}).get('status')}
Edge cases: {state.get('edge_cases', [])}
"""
    review = ask_json("You are the Test Critic agent. Be skeptical and request specific revisions.", prompt)
    llm_used = review is not None and not review.get("_llm_error")
    if review and review.get("_llm_error"):
        return {**error_update(state, "test_critic", review["_llm_error"]),
                **traced(state, "test_critic", "critic_fallback", {"reason": "LLM request failed"},
                         {"critic_review": {"approved": False, "score": 0, "weaknesses": ["Could not contact LLM critic"],
                                             "revision_instructions": ["Configure OPENAI_API_KEY and request a real review."],
                                             "rationale": "Fail closed when the critic is unavailable."}})}
    if review is None:
        weak = [pattern for pattern in WEAK_PATTERNS if re.search(pattern, tests)]
        has_assert = "assert" in tests
        review = {"approved": bool(has_assert and not weak and (state.get("pytest_result") or {}).get("passed")),
                  "score": 2 if weak else (5 if has_assert else 0),
                  "weaknesses": [f"Weak assertion pattern detected: {p}" for p in weak] or ["Offline fallback cannot judge semantic strength."],
                  "revision_instructions": ["Configure OPENAI_API_KEY for a semantic critic review."] if weak or not has_assert else [],
                  "rationale": "Heuristic offline review only; not equivalent to an LLM critic."}
    approved = bool(review.get("approved", False)) and bool((state.get("pytest_result") or {}).get("passed"))
    review["approved"] = approved
    return traced(state, "test_critic", "tests_reviewed",
                  {"approved": approved, "score": review.get("score"), "weakness_count": len(review.get("weaknesses", [])),
                   "llm_used": llm_used},
                  {"critic_review": review})
