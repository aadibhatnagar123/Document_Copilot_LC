import time
import db
from .. import tools

# try loading rag — if not built yet citations stay None
try:
    from rag.retriever import query as rag_query
except ImportError:
    rag_query = None


def gate(state):
    """Validate LC terms sheet. Block the run if incomplete or expired."""
    # sleep for visual progression
    time.sleep(1.0)
    
    run_id = state["run_id"]
    lc_terms = state["parsed_docs"].get("lc_terms", {})
    issues, lc_ok = tools.validate_lc_terms(lc_terms, state["schema"])

    all_issues = state["issues"] + issues

    # update database
    db.update_run_issues_and_ambiguous(run_id, all_issues)
    if not lc_ok:
        db.update_run_status(run_id, "blocked")
    else:
        db.update_run_status(run_id, "checker")

    return {
        "issues": all_issues,
        "lc_ok": lc_ok,
        "lc_terms": lc_terms,
        "blocked": not lc_ok,
        "ambiguous_pairs": [],
    }


def pass_a(state):
    """Per-document checks: presence, completeness, dates."""
    # sleep for visual progression
    time.sleep(1.5)
    
    run_id = state["run_id"]
    issues = []

    issues += tools.check_required_documents(
        state["parsed_docs"], state["lc_terms"]
    )
    issues += tools.check_completeness(
        state["parsed_docs"], state["schema"]
    )
    issues += tools.check_dates(
        state["parsed_docs"], state["lc_terms"], state["schema"]
    )

    # stamp citations if rag is available
    issues = tools.attach_citations(issues, query_fn=rag_query)

    all_issues = state["issues"] + issues
    db.update_run_issues_and_ambiguous(run_id, all_issues)

    return {
        "issues": all_issues,
    }


def pass_b(state):
    """Cross-doc checks: consistency among the 7 docs, then compliance vs LC."""
    run_id = state["run_id"]
    
    # Update status to semantic at the start of cross-doc checks
    db.update_run_status(run_id, "semantic")
    
    # sleep for visual progression
    time.sleep(1.5)

    # first — do the 7 supporting docs agree with each other?
    consistency_issues, consistency_ambiguous = tools.run_consistency_checks(
        state["parsed_docs"], state["schema"]
    )

    # second — does each doc match the LC terms?
    compliance_issues, compliance_ambiguous = tools.run_compliance_checks(
        state["parsed_docs"], state["lc_terms"], state["schema"]
    )

    issues = consistency_issues + compliance_issues
    ambiguous = consistency_ambiguous + compliance_ambiguous

    # stamp citations on all cross-doc issues
    issues = tools.attach_citations(issues, query_fn=rag_query)

    all_issues = state["issues"] + issues
    all_ambiguous = state.get("ambiguous_pairs", []) + ambiguous

    # Save final checker and semantic issues and transition to hitl
    db.update_run_issues_and_ambiguous(run_id, all_issues, all_ambiguous)
    db.update_run_status(run_id, "hitl")

    return {
        "issues": all_issues,
        "ambiguous_pairs": all_ambiguous,
    }