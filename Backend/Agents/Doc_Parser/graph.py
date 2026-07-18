from langgraph.graph import StateGraph, START, END
from .state import ParseState
from .nodes.pipeline import load_text, filter_fields, extract, validate, normalize


def after_load(state):
    return "end" if state["parse_failed"] else "filter_fields"


def after_validate(state):
    if state["valid"] or state["retry_count"] >= 1:
        return "normalize"
    return "extract"


def build_doc_parser_subgraph():
    g = StateGraph(ParseState)

    g.add_node("load_text", load_text)
    g.add_node("filter_fields", filter_fields)
    g.add_node("extract", extract)
    g.add_node("validate", validate)
    g.add_node("normalize", normalize)

    g.add_edge(START, "load_text")

    g.add_conditional_edges("load_text", after_load, {
        "end": END,
        "filter_fields": "filter_fields"
    })

    g.add_edge("filter_fields", "extract")
    g.add_edge("extract", "validate")

    g.add_conditional_edges("validate", after_validate, {
        "normalize": "normalize",
        "extract": "extract"
    })

    g.add_edge("normalize", END)

    return g.compile()