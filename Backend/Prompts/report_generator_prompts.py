def build_polish_prompt(mt799_text):
    """Build prompt to polish MT799 into proper banking language."""
    instruction = (
        "You are a senior trade finance officer. Rewrite the following "
        "MT799 discrepancy notice into professional banking language. "
        "Keep all facts, amounts, dates, and citations exactly as they are. "
        "Only improve the wording to sound like a formal bank communication. "
        "Do NOT add or remove any discrepancies. "
        "Do NOT change any numbers, dates, or article references. "
        "Return ONLY the rewritten text, no JSON, no explanation."
    )
    return f"{instruction}\n\n{mt799_text}"
