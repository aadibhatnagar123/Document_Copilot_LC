import json
from groq import Groq
from rapidfuzz import fuzz

from Prompts.semantic_comparator_prompts import (
    build_recommendation_prompt,
    build_semantic_prompt,
    build_severity_prompt,
)


def call_semantic_compare(pairs, rule_contexts, model, api_key):
    """One Groq call to resolve all ambiguous pairs. Returns dict of verdicts."""
    prompt = build_semantic_prompt(pairs, rule_contexts)
    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(resp.choices[0].message.content)


def resolve_verdicts(pairs, verdicts):
    """Turn LLM verdicts into semantic_mismatch issues for mismatches."""
    issues = []
    for i, pair in enumerate(pairs):
        verdict = str(verdicts.get(str(i), "mismatch")).strip().lower()
        if verdict != "match":
            issues.append({
                "doc_type": pair["doc_b"],
                "field": pair["field"],
                "kind": "semantic_mismatch",
                "message": f"{pair['field']} differs: '{pair['val_a']}' "
                           f"({pair['doc_a']}) vs '{pair['val_b']}' ({pair['doc_b']})",
                "citation": None,
                "severity": None,
            })
    return issues


def fallback_resolve(pairs):
    """Deterministic fallback if LLM call 1 failed. Tighter rapidfuzz at 75."""
    issues = []
    for pair in pairs:
        score = fuzz.token_sort_ratio(str(pair["val_a"]), str(pair["val_b"]))
        if score < 75:
            issues.append({
                "doc_type": pair["doc_b"],
                "field": pair["field"],
                "kind": "fuzzy_mismatch",
                "message": f"{pair['field']} fuzzy mismatch ({score:.1f}): "
                           f"'{pair['val_a']}' ({pair['doc_a']}) vs "
                           f"'{pair['val_b']}' ({pair['doc_b']})",
                "citation": None,
                "severity": "major",
            })
        else:
            issues.append({
                "doc_type": pair["doc_b"],
                "field": pair["field"],
                "kind": "needs_manual_review",
                "message": f"{pair['field']} could not be verified by LLM, "
                           f"needs human review: '{pair['val_a']}' "
                           f"({pair['doc_a']}) vs '{pair['val_b']}' ({pair['doc_b']})",
                "citation": None,
                "severity": "major",
            })
    return issues


def call_severity_classify(issues, model, api_key):
    """One Groq call to classify severity on all issues. Returns dict."""
    prompt = build_severity_prompt(issues)
    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(resp.choices[0].message.content)


def apply_severity(issues, severities):
    """Stamp LLM severity onto each issue. Modifies issues in place."""
    for i, issue in enumerate(issues):
        sev = str(severities.get(str(i), "major")).strip().lower()
        if sev not in ("critical", "major", "minor"):
            sev = "major"
        issue["severity"] = sev


def apply_default_severity(issues):
    """Fallback: map issue kind to severity deterministically."""
    critical = {"missing_doc", "lc_terms_incomplete", "lc_expired", "unreadable"}
    minor = {"missing_field", "date_invalid"}
    for issue in issues:
        if issue.get("severity"):
            continue
        kind = issue.get("kind")
        if kind in critical:
            issue["severity"] = "critical"
        elif kind in minor:
            issue["severity"] = "minor"
        else:
            issue["severity"] = "major"


def call_recommendation(issues, model, api_key):
    """One Groq call to get approve/reject with summary. Returns dict."""
    prompt = build_recommendation_prompt(issues)
    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(resp.choices[0].message.content)


def default_recommendation(issues):
    """Fallback recommendation based on severity counts."""
    criticals = sum(1 for i in issues if i.get("severity") == "critical")
    majors = sum(1 for i in issues if i.get("severity") == "major")
    minors = sum(1 for i in issues if i.get("severity") == "minor")

    if criticals:
        return {
            "recommendation": "reject",
            "summary": f"Reject - {criticals} critical discrepancies found that are "
                       f"non-waivable under UCP 600. {majors} major and {minors} "
                       f"minor discrepancies also found.",
        }
    if majors:
        return {
            "recommendation": "reject",
            "summary": f"Reject - {majors} major discrepancies found that are likely "
                       f"grounds for refusal. They may be waivable by the applicant. "
                       f"{minors} minor discrepancies also found.",
        }
    if issues:
        return {
            "recommendation": "approve",
            "summary": f"Approve - {minors} minor discrepancies found. All are cosmetic "
                       f"or formatting differences typically overlooked by banks.",
        }
    return {
        "recommendation": "approve",
        "summary": "Approve - no discrepancies found. Clean presentation.",
    }


def attach_citations(issues, query_fn=None):
    """Stamp UCP/ISBP article ref onto issues via RAG retrieval."""
    if query_fn is None:
        return issues

    for issue in issues:
        if issue.get("citation"):
            continue
        parts = []
        if issue.get("doc_type"):
            parts.append(issue["doc_type"])
        if issue.get("field"):
            parts.append(issue["field"])
        parts.append(issue.get("kind", ""))
        query_text = " ".join(parts)

        try:
            results = query_fn(query_text, k=1)
            if results:
                issue["citation"] = results[0].get("ref")
        except Exception:
            pass

    return issues
