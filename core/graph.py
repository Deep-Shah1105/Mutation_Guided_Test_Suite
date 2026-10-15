"""LangGraph supervisor-worker graph with critic and mutation-guided feedback loops."""
from __future__ import annotations
from langgraph.graph import END, START, StateGraph
from core.state import GeneratorState
from agents.supervisor import supervisor
from agents.code_analyst import code_analyst
from agents.adversary import adversary
from agents.test_writer import test_writer
from agents.test_critic import test_critic
from agents.mutation_tool_node import run_mutations
from agents.mutation_analyst import mutation_analyst
from agents.reporter import reporter


def _route(state: GeneratorState) -> str:
    action = state.get("next_action", "reporter")
    if action not in {"code_analyst", "adversary", "test_writer", "test_critic",
                      "run_mutations", "mutation_analyst", "reporter"}:
        return "reporter"
    return action


def build_graph():
    graph = StateGraph(GeneratorState)
    graph.add_node("supervisor", supervisor)
    graph.add_node("code_analyst", code_analyst)
    graph.add_node("adversary", adversary)
    graph.add_node("test_writer", test_writer)
    graph.add_node("test_critic", test_critic)
    graph.add_node("run_mutations", run_mutations)
    graph.add_node("mutation_analyst", mutation_analyst)
    graph.add_node("reporter", reporter)
    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges("supervisor", _route, {
        "code_analyst": "code_analyst", "adversary": "adversary",
        "test_writer": "test_writer", "test_critic": "test_critic",
        "run_mutations": "run_mutations", "mutation_analyst": "mutation_analyst",
        "reporter": "reporter",
    })
    for node in ("code_analyst", "adversary", "test_writer", "test_critic",
                 "run_mutations", "mutation_analyst"):
        graph.add_edge(node, "supervisor")
    graph.add_edge("reporter", END)
    return graph.compile()
