from .. import config
from .. import tools


def gather_data(state):
    """Sort issues by severity and prepare data for report generation."""
    sorted_issues = tools.sort_issues_by_severity(state["issues"])
    return {"issues": sorted_issues}


def generate_mt799(state):
    """Generate the MT799 SWIFT notice as text."""
    text = tools.build_mt799_text(
        state["lc_terms"], state["issues"], state["run_id"]
    )
    return {"mt799_text": text, "polish_failed": False}


def polish_mt799(state):
    """Optional LLM call to polish MT799 into banking language."""
    try:
        polished = tools.call_polish(
            state["mt799_text"], config.MODEL, config.GROQ_API_KEY
        )
        return {"mt799_text": polished, "polish_failed": False}
    except Exception:
        # keep the template version, it's fine
        return {"polish_failed": True}


def generate_summary(state):
    """Generate the summary report as text and convert both to PDF."""
    summary = tools.build_summary_text(
        state["lc_terms"], state["parsed_docs"], state["issues"], state["run_id"],
        state["recommendation"], state["recommendation_summary"],
        state["hitl_decision"]
    )

    mt799_pdf = tools.text_to_pdf(state["mt799_text"], "MT799 Discrepancy Notice")
    summary_pdf = tools.text_to_pdf(summary, "Document Copilot — Run Report")

    return {
        "summary_text": summary,
        "mt799_pdf": mt799_pdf,
        "summary_pdf": summary_pdf
    }


from db import DB_PATH

def save_reports(state):
    """Save reports to the database and mark run as done."""
    tools.save_reports_to_db(
        state["run_id"],
        state["mt799_text"],
        state["summary_text"],
        state["mt799_pdf"],
        state["summary_pdf"],
        DB_PATH
    )
    return {}
