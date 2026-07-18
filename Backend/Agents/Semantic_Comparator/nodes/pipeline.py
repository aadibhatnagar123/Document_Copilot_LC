from .. import config
from .. import tools

# try loading rag — if not built yet citations stay None
try:
    from rag.retriever import query as rag_query
except ImportError:
    rag_query = None


def rag_lookup(state):
    """Pull UCP/ISBP rules for each ambiguous pair from ChromaDB."""
    pairs = state["ambiguous_pairs"]
    if not pairs or rag_query is None:
        return {"rule_contexts": []}

    contexts = []
    for pair in pairs:
        query = f"{pair['field']} {pair['doc_a']} {pair['doc_b']}"
        try:
            results = rag_query(query, k=1)
            contexts.append(results[0] if results else None)
        except Exception:
            contexts.append(None)
    return {"rule_contexts": contexts}


def resolve_pairs(state):
    """LLM call 1: judge each ambiguous pair as match or mismatch."""
    if not state["ambiguous_pairs"]:
        return {"resolved_issues": [], "resolve_failed": False}
    try:
        verdicts = tools.call_semantic_compare(
            state["ambiguous_pairs"], state.get("rule_contexts", []),
            config.MODEL, config.GROQ_API_KEY
        )
        issues = tools.resolve_verdicts(state["ambiguous_pairs"], verdicts)
        return {"resolved_issues": issues, "resolve_failed": False}
    except Exception:
        return {"resolved_issues": [], "resolve_failed": True}


def deterministic_fallback(state):
    """Fallback if LLM call 1 failed. Tighter rapidfuzz at 75."""
    issues = tools.fallback_resolve(state["ambiguous_pairs"])
    return {"resolved_issues": issues, "resolve_failed": True}


def merge_issues(state):
    """Combine Agent 2's issues with newly resolved semantic issues.

    Citations are stamped on the NEW issues here, before severity
    classification (call 2) and the recommendation (call 3), so those
    LLM prompts actually see the UCP/ISBP reference they claim to weigh.
    Agent 2's issues already carry citations, so this only queries RAG
    for the freshly-created semantic issues.
    """
    new_issues = state["resolved_issues"]
    if rag_query and new_issues:
        tools.attach_citations(new_issues, query_fn=rag_query)
    return {"issues": state["issues"] + new_issues}


def classify_severity(state):
    """LLM call 2: classify every issue as critical/major/minor."""
    if not state["issues"]:
        return {"severity_failed": False}
    try:
        severities = tools.call_severity_classify(
            state["issues"], config.MODEL, config.GROQ_API_KEY
        )
        tools.apply_severity(state["issues"], severities)
        return {"severity_failed": False}
    except Exception:
        return {"severity_failed": True}


def default_severity(state):
    """Fallback if LLM call 2 failed. Kind to severity mapping."""
    tools.apply_default_severity(state["issues"])
    return {"severity_failed": True}


def generate_recommendation(state):
    """LLM call 3: approve or reject with reasoning summary."""
    try:
        result = tools.call_recommendation(
            state["issues"], config.MODEL, config.GROQ_API_KEY
        )
        # anything that isn't a clean "approve" becomes reject (conservative)
        rec = str(result.get("recommendation", "reject")).strip().lower()
        if rec != "approve":
            rec = "reject"
        return {
            "recommendation": rec,
            "recommendation_summary": str(result.get("summary", "")),
            "recommendation_failed": False,
        }
    except Exception:
        return {"recommendation_failed": True}


def apply_default_recommendation(state):
    """Fallback if LLM call 3 failed. Severity counts decide."""
    result = tools.default_recommendation(state["issues"])
    return {
        "recommendation": result["recommendation"],
        "recommendation_summary": result["summary"],
        "recommendation_failed": True,
    }


def apply_final(state):
    """Clear ambiguous_pairs now that they've been resolved.

    Citations were already stamped in merge_issues (before the severity
    and recommendation calls), so nothing left to do but close out the
    ambiguous band.
    """
    return {"ambiguous_pairs": []}
