from langgraph.graph import StateGraph, START, END
from .state import CheckState
from .nodes.pipeline import gate, pass_a, pass_b


def _after_gate(state):
    """Route after gate: skip passes if LC is bad."""
    if state["lc_ok"]:
        return "pass_a"
    return "end"


def build_internal_checker_subgraph():
    """Wire and compile the agent 2 subgraph."""
    g = StateGraph(CheckState)

    g.add_node("gate", gate)
    g.add_node("pass_a", pass_a)
    g.add_node("pass_b", pass_b)

    g.add_edge(START, "gate")
    g.add_conditional_edges("gate", _after_gate, {
        "pass_a": "pass_a",
        "end": END,
    })
    g.add_edge("pass_a", "pass_b")
    g.add_edge("pass_b", END)

    return g.compile()