from typing import TypedDict


class SemanticState(TypedDict):
    ambiguous_pairs: list        # from Agent 2, fuzzy 40-92 band
    issues: list                 # all issues so far, severity=null initially
    schema: dict                 # loaded schema config
    resolved_issues: list        # new issues from job 1
    resolve_failed: bool         # True if LLM call 1 crashed
    severity_failed: bool        # True if LLM call 2 crashed
    recommendation_failed: bool  # True if LLM call 3 crashed
    rule_contexts: list          # RAG results per ambiguous pair
    recommendation: str          # "approve" or "reject"
    recommendation_summary: str  # 3-5 sentence explanation
