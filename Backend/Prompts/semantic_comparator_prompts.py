def build_semantic_prompt(pairs, rule_contexts):
    """Build prompt for LLM call 1: resolve ambiguous pairs as match/mismatch."""
    lines = [
        "You are a trade finance document checker.",
        "For each pair below, determine if the two values mean the same",
        "thing despite being worded differently. Consider spelling,",
        "abbreviation, reordering, and formatting differences.",
        "Respond ONLY with a JSON object mapping each pair index to",
        "'match' or 'mismatch'.",
        "",
    ]
    for i, pair in enumerate(pairs):
        lines.append(f"Pair {i}:")
        lines.append(f"  Field: {pair['field']}")
        lines.append(f"  Value A ({pair['doc_a']}): \"{pair['val_a']}\"")
        lines.append(f"  Value B ({pair['doc_b']}): \"{pair['val_b']}\"")
        rule = rule_contexts[i] if rule_contexts and i < len(rule_contexts) else None
        if rule and rule.get("text"):
            lines.append(f"  Applicable rule: {rule['text']}")
        lines.append("")
    return "\n".join(lines)


def build_severity_prompt(issues):
    """Build prompt for LLM call 2: classify each issue as critical/major/minor."""
    lines = [
        "You are a trade finance compliance expert.",
        "For each discrepancy below, classify its severity:",
        "  critical - presentation will be refused, non-waivable",
        "  major - likely refusal, potentially waivable by applicant",
        "  minor - cosmetic difference, typically overlooked by banks",
        "Respond ONLY with a JSON object mapping each index to",
        "'critical', 'major', or 'minor'.",
        "",
    ]
    for i, issue in enumerate(issues):
        lines.append(f"Discrepancy {i}:")
        lines.append(f"  Field: {issue.get('field')}")
        lines.append(f"  Kind: {issue.get('kind')}")
        lines.append(f"  Message: {issue.get('message')}")
        if issue.get("citation"):
            lines.append(f"  Citation: {issue['citation']}")
        lines.append("")
    return "\n".join(lines)


def build_recommendation_prompt(issues):
    """Build prompt for LLM call 3: approve/reject with reasoning."""
    lines = [
        "You are a senior trade finance compliance officer reviewing",
        "a Letter of Credit document presentation.",
        "Below are all discrepancies found. Each has a severity, a UCP/ISBP",
        "citation, and a description.",
        "Based on these findings:",
        "1. Recommend 'approve' or 'reject'",
        "2. Write a summary (3-5 sentences) explaining your reasoning",
        "Guidelines:",
        "- Any critical discrepancy = reject (non-waivable)",
        "- Only major discrepancies = reject but note potentially waivable",
        "- Only minor discrepancies = approve with notes",
        "- No discrepancies = approve, clean presentation",
        "Respond ONLY with JSON:",
        "{'recommendation': 'approve' or 'reject', 'summary': 'your reasoning'}",
        "",
    ]
    if not issues:
        lines.append("No discrepancies were found.")
    else:
        for i, issue in enumerate(issues):
            lines.append(f"Discrepancy {i}:")
            lines.append(f"  Severity: {issue.get('severity')}")
            lines.append(f"  Field: {issue.get('field')}")
            lines.append(f"  Kind: {issue.get('kind')}")
            lines.append(f"  Message: {issue.get('message')}")
            if issue.get("citation"):
                lines.append(f"  Citation: {issue['citation']}")
            lines.append("")
    return "\n".join(lines)
