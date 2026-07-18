from langgraph.graph import StateGraph, START, END
from .state import SemanticState
from .nodes.pipeline import (
    rag_lookup, resolve_pairs, deterministic_fallback,
    merge_issues, classify_severity, default_severity,
    generate_recommendation, apply_default_recommendation,
    apply_final,
)


def _after_resolve(state):
    """Route after LLM call 1: fallback if failed."""
    return "deterministic_fallback" if state["resolve_failed"] else "merge_issues"


def _after_classify(state):
    """Route after LLM call 2: default severity if failed."""
    return "default_severity" if state["severity_failed"] else "generate_recommendation"


def _after_recommendation(state):
    """Route after LLM call 3: default recommendation if failed."""
    return "apply_default_recommendation" if state["recommendation_failed"] else "apply_final"


def build_semantic_comparator_subgraph():
    """Wire and compile the agent 3 subgraph."""
    g = StateGraph(SemanticState)

    g.add_node("rag_lookup", rag_lookup)
    g.add_node("resolve_pairs", resolve_pairs)
    g.add_node("deterministic_fallback", deterministic_fallback)
    g.add_node("merge_issues", merge_issues)
    g.add_node("classify_severity", classify_severity)
    g.add_node("default_severity", default_severity)
    g.add_node("generate_recommendation", generate_recommendation)
    g.add_node("apply_default_recommendation", apply_default_recommendation)
    g.add_node("apply_final", apply_final)

    g.add_edge(START, "rag_lookup")
    g.add_edge("rag_lookup", "resolve_pairs")

    g.add_conditional_edges("resolve_pairs", _after_resolve, {
        "deterministic_fallback": "deterministic_fallback",
        "merge_issues": "merge_issues",
    })
    g.add_edge("deterministic_fallback", "merge_issues")
    g.add_edge("merge_issues", "classify_severity")

    g.add_conditional_edges("classify_severity", _after_classify, {
        "default_severity": "default_severity",
        "generate_recommendation": "generate_recommendation",
    })
    g.add_edge("default_severity", "generate_recommendation")

    g.add_conditional_edges("generate_recommendation", _after_recommendation, {
        "apply_default_recommendation": "apply_default_recommendation",
        "apply_final": "apply_final",
    })
    g.add_edge("apply_default_recommendation", "apply_final")
    g.add_edge("apply_final", END)

    return g.compile()
