import re

from .. import config
from ..tools import get_raw_text, call_llm_extract, normalize_value


def load_text(state):
    text, ocr_used = get_raw_text(state["doc"])
    if text is None or text.strip() == "":
        return {"parse_failed": True, "raw_text": "", "ocr_used": False}
    return {"parse_failed": False, "raw_text": text, "ocr_used": ocr_used}


def filter_fields(state):
    doc_type = state["doc"]["doc_type"]
    all_fields = state["schema"].get("fields", [])
    relevant = [f for f in all_fields if doc_type in f.get("appears_in", [])]
    return {"target_fields": relevant}


def extract(state):
    result = call_llm_extract(
        state["raw_text"],
        state["target_fields"],
        state["ocr_used"],
        config.MODEL,
        config.GROQ_API_KEY,
        state.get("validation_errors")
    )
    return {"raw_values": result}


def validate(state):
    errors = []
    for field in state["target_fields"]:
        if not field.get("required"):
            continue
        name = field["field"]
        val = state["raw_values"].get(name)
        if val is None:
            errors.append(f"{name} is null")
            continue
        if field["type"] == "number":
            cleaned = re.sub(r"[^\d.\-]", "", str(val))
            if cleaned == "":
                errors.append(f"{name} is not a number")
        if field["type"] == "date":
            if not any(c.isdigit() for c in str(val)):
                errors.append(f"{name} does not look like a date")

    if errors:
        return {
            "valid": False,
            "validation_errors": errors,
            "retry_count": state["retry_count"] + 1
        }
    return {"valid": True, "validation_errors": []}


def normalize(state):
    result = {}
    field_types = {f["field"]: f["type"] for f in state["target_fields"]}
    for name, val in state["raw_values"].items():
        field_type = field_types.get(name, "string")
        result[name] = normalize_value(val, field_type)
    return {"fields": result}