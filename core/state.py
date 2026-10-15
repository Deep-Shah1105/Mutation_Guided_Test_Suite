"""Typed shared blackboard for all agent nodes."""
from __future__ import annotations
from operator import add
from typing import Annotated, Any, TypedDict


class GeneratorState(TypedDict, total=False):
    run_id: str
    trace_path: str
    source_code: str
    function_name: str | None
    request_notes: str
    analysis: dict[str, Any]
    edge_cases: list[dict[str, Any]]
    generated_tests: str
    pytest_result: dict[str, Any]
    critic_review: dict[str, Any]
    mutation_result: dict[str, Any]
    mutation_analysis: dict[str, Any]
    report: dict[str, Any]
    next_action: str
    decision_reason: str
    allowed_actions: list[str]
    round_index: int
    max_rounds: int
    revision_count: int
    mutation_attempts: int
    mutmut_failed: bool
    needs_regeneration: bool
    trace_events: Annotated[list[dict[str, Any]], add]
    errors: Annotated[list[dict[str, Any]], add]
