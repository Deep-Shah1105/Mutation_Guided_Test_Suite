"""Common entry point shared by CLI and HTTP API."""
from __future__ import annotations
import os
import uuid
from pathlib import Path
from typing import Any
from core.graph import build_graph

_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


def run_generation(source_code: str, function_name: str | None = None,
                   request_notes: str = "", max_rounds: int | None = None,
                   trace_path: str | None = None) -> dict[str, Any]:
    resolved_trace = trace_path or os.getenv("TRACE_PATH", "trace.jsonl")
    Path(resolved_trace).parent.mkdir(parents=True, exist_ok=True)
    state = {
        "run_id": str(uuid.uuid4()),
        "trace_path": resolved_trace,
        "source_code": source_code,
        "function_name": function_name,
        "request_notes": request_notes,
        "max_rounds": max(1, min(int(max_rounds or os.getenv("MAX_AGENT_ROUNDS", "3")), 5)),
        "round_index": 0,
        "revision_count": 0,
        "mutation_attempts": 0,
        "edge_cases": [],
        "trace_events": [],
        "errors": [],
    }
    return get_graph().invoke(state, config={"recursion_limit": 100})
