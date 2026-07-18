from typing import TypedDict, List, Dict, Any


class ParseState(TypedDict):
    doc: dict                # raw_documents row: doc_id, doc_type, file_path, raw_text
    schema: dict              # loaded schema.json content
    raw_text: str             # output of load_text node
    ocr_used: bool            # True if OCR extracted the text
    target_fields: list       # schema fields for this doc_type
    raw_values: dict          # LLM output before normalization
    validation_errors: list   # required fields that came back null
    fields: dict              # final normalized output
    retry_count: int          # starts 0, max 1
    valid: bool               # did validate pass
    parse_failed: bool        # True if all extraction layers failed