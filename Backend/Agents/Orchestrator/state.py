from typing import TypedDict


class RunState(TypedDict):
    """Shared state bus. Every agent reads from and writes to this."""
    run_id: str
    schema: dict
    raw_docs: list
    parsed_docs: dict
    lc_terms: dict
    issues: list
    ambiguous_pairs: list
    blocked: bool
    lc_ok: bool
    recommendation: str
    recommendation_summary: str
    hitl_decision: str
    retry_from: str
    mt799_text: str
    summary_text: str
    mt799_pdf: bytes
    summary_pdf: bytes
    status: str