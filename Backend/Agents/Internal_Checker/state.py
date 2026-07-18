from typing import TypedDict


class CheckState(TypedDict):
    """Internal state for the checker subgraph."""
    run_id: str
    parsed_docs: dict
    lc_terms: dict
    schema: dict
    issues: list
    lc_ok: bool
    ambiguous_pairs: list
    blocked: bool