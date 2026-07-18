from langgraph.graph import StateGraph, START, END
from .state import ReportState
from .nodes.pipeline import (
    gather_data, generate_mt799, polish_mt799,
    generate_summary, save_reports
)


def build_report_generator_subgraph():
    """Wire and compile the agent 4 subgraph."""
    g = StateGraph(ReportState)

    g.add_node("gather_data", gather_data)
    g.add_node("generate_mt799", generate_mt799)
    g.add_node("polish_mt799", polish_mt799)
    g.add_node("generate_summary", generate_summary)
    g.add_node("save_reports", save_reports)

    g.add_edge(START, "gather_data")
    g.add_edge("gather_data", "generate_mt799")
    g.add_edge("generate_mt799", "polish_mt799")
    g.add_edge("polish_mt799", "generate_summary")
    g.add_edge("generate_summary", "save_reports")
    g.add_edge("save_reports", END)

    return g.compile()
