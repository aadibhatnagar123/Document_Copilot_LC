def build_extraction_prompt(raw_text: str, target_fields: list, ocr_used: bool, validation_errors: list = None) -> str:
    fields_desc = []
    for f in target_fields:
        required_str = " (required)" if f.get("required") else ""
        fields_desc.append(f"- {f['field']} (type: {f['type']}){required_str}")
    fields_text = "\n".join(fields_desc)

    prompt = (
        "You are a trade finance document parser.\n"
        "Extract values for the target fields below from the document.\n"
        "Your output must be a flat JSON object containing ONLY the exact keys specified.\n"
        "If a field is not present or cannot be parsed, use null for its value.\n\n"
        "Target Fields to extract:\n" + fields_text + "\n\n"
        "Rules:\n"
        "- Use the exact target field keys (e.g. lc_number, expiry_date)\n"
        "- Dates must be in YYYY-MM-DD format\n"
        "- Amounts must be numeric (no currency symbols)\n"
    )

    if ocr_used:
        prompt += (
            "\nNote: this text was extracted via OCR and may contain character "
            "recognition errors, garbled numbers, or spacing issues. Do your "
            "best to interpret the intended values.\n"
        )

    if validation_errors:
        errors_text = "\n".join(f"- {e}" for e in validation_errors)
        prompt += (
            "\nThe previous extraction attempt failed validation with these "
            "problems:\n" + errors_text + "\n"
            "Look again at the document text and fix these specific fields. "
            "If a value is genuinely absent from the text, use null rather "
            "than guessing.\n"
        )

    prompt += "\nDocument Text:\n" + raw_text
    return prompt