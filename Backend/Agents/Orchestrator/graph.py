from langgraph.graph import StateGraph, START, END
from .state import RunState
from .checkpoint import get_checkpointer
from .nodes.pipeline import (
    load_run, parse_documents, check_documents,
    semantic_compare, hitl_checkpoint, generate_reports,
    mark_rejected, mark_error
)


# ── routing functions ──

def _after_parse(state):
    """All docs failed → error, else continue."""
    if state.get("status") == "error":
        return "error"
    return "check"


def _after_check(state):
    """Blocked → rejected, crashed → error, else continue."""
    if state.get("status") == "error":
        return "error"
    if state.get("blocked"):
        return "blocked"
    return "semantic"


def _after_hitl(state):
    """Three-way: approve/reject → reports (final status set there based
    on the decision), retry → loop back."""
    action = state.get("hitl_decision")

    if action == "retry":
        target = state.get("retry_from", "check")
        if target == "agent1":
            return "parse"
        if target == "agent2":
            return "check"
        if target == "agent3":
            return "semantic"
        return "check"
    return "reports"


def _after_reports(state):
    """Done or error."""
    if state.get("status") == "error":
        return "error"
    return "done"


# ── build the graph ──

def build_orchestrator():
    """Wire the main orchestrator graph."""
    g = StateGraph(RunState)

    # nodes
    g.add_node("load_run", load_run)
    g.add_node("parse", parse_documents)
    g.add_node("check", check_documents)
    g.add_node("semantic", semantic_compare)
    g.add_node("hitl", hitl_checkpoint)
    g.add_node("reports", generate_reports)
    g.add_node("rejected", mark_rejected)
    g.add_node("error", mark_error)

    # edges
    g.add_edge(START, "load_run")
    g.add_edge("load_run", "parse")

    g.add_conditional_edges("parse", _after_parse, {
        "check": "check",
        "error": "error",
    })

    g.add_conditional_edges("check", _after_check, {
        "semantic": "semantic",
        "blocked": "rejected",
        "error": "error",
    })

    g.add_edge("semantic", "hitl")

    g.add_conditional_edges("hitl", _after_hitl, {
        "reports": "reports",
        "parse": "parse",
        "check": "check",
        "semantic": "semantic",
    })

    g.add_conditional_edges("reports", _after_reports, {
        "done": END,
        "error": "error",
    })

    g.add_edge("rejected", END)
    g.add_edge("error", END)

    checkpointer = get_checkpointer()
    return g.compile(checkpointer=checkpointer)


# ── entry points ──

def run_pipeline(run_id):
    """Start the orchestrator for a given run_id."""
    graph = build_orchestrator()
    return graph.invoke(
        {"run_id": run_id},
        config={"configurable": {"thread_id": run_id}}
    )


def resume_pipeline(run_id, decision):
    """Resume the orchestrator after HITL with the human's decision."""
    from langgraph.types import Command
    graph = build_orchestrator()
    return graph.invoke(
        Command(resume=decision),
        config={"configurable": {"thread_id": run_id}}
    )