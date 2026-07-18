from typing import TypedDict


class ReportState(TypedDict):
    """Internal state for the report generator subgraph."""
    run_id: str                  # unique run identifier
    issues: list                 # all issues with severity + citation
    parsed_docs: dict            # Agent 1 output
    lc_terms: dict                # LC term sheet fields
    schema: dict                  # loaded schema config
    recommendation: str           # Agent 3's "approve" or "reject"
    recommendation_summary: str   # Agent 3's reasoning paragraph
    hitl_decision: str             # "approved" or "rejected" — the human's call
    mt799_text: str                # generated MT799 text content
    summary_text: str              # generated summary text content
    mt799_pdf: bytes                # MT799 as PDF bytes
    summary_pdf: bytes              # summary as PDF bytes
    polish_failed: bool              # True if optional LLM polish crashed
