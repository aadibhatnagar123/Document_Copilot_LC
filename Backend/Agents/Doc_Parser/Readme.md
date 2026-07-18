# Doc_Parser

**Role**: Extracts and normalizes structured fields from a single trade finance PDF using a 3-layer text extraction chain + Groq LLM.

---

## How it works

Receives one raw document and a schema config. Extracts plain text via three fallback layers (pdfplumber → PyMuPDF → Tesseract OCR), then calls Groq to extract schema-defined fields as JSON. Validates required fields and retries once on failure with errors injected into the prompt. Finally normalizes all values to correct Python types.

**Pipeline**:
```
load_text → filter_fields → extract → validate → (retry once) → normalize
```

---

## Inputs

- **`doc`** — raw document row (`doc_id`, `doc_type`, `file_path`, `raw_text`)
- **`schema`** — loaded `schema.json` with field definitions, types, and `appears_in` lists
- **Env vars** — `GROQ_API_KEY` (required), `GROQ_MODEL` (optional, defaults to `llama-3.3-70b-versatile`)

---

## Project Structure

```
Doc_Parser/
├── agent.yaml             # Agent spec (v0.1, model, extraction layers)
├── config.py              # Reads GROQ_API_KEY + GROQ_MODEL from .env
├── tools.py               # 3-layer PDF extraction, Groq LLM call, normalization
├── state.py               # ParseState TypedDict (11 fields)
├── graph.py               # LangGraph StateGraph (5 nodes, 2 conditional edges)
├── __init__.py            # Package marker
└── nodes/
    └── pipeline.py        # load_text, filter_fields, extract, validate, normalize
```

**External prompt**: `Prompts/extract_fields_prompts.py` → `build_extraction_prompt()` — structured extraction prompt with OCR hints and retry feedback

---

## Processing

| Node | What it does |
|---|---|
| `load_text` | Tries pdfplumber → PyMuPDF → OCR (300 DPI). Sets `parse_failed=True` if all fail → graph ends |
| `filter_fields` | Filters schema fields to those matching this `doc_type` via `appears_in` |
| `extract` | Groq LLM call (`temperature=0`, `json_object` mode). On retry, injects `validation_errors` into prompt |
| `validate` | Checks required fields for null/type issues. If fails and `retry_count < 1` → loops back to `extract` |
| `normalize` | Converts values: numbers → `float`, dates → `YYYY-MM-DD`, strings → trimmed. Unparseable → `None` |

---

## Tools

| Group | Tools | Purpose |
|---|---|---|
| Text Extraction | `get_raw_text`, `_try_pdfplumber`, `_try_pymupdf`, `_try_ocr` | 3-layer fallback chain for PDF text extraction |
| LLM Extraction | `call_llm_extract` | Single Groq call to extract fields as JSON |
| Normalization | `normalize_value` | Type-safe conversion per field (`float`, date string, trimmed string) |

---

## Output

- **`fields`** — `dict[str, float | str | None]` of normalized field values keyed by schema field name
- **`parse_failed`** — `bool`, `True` if all extraction layers failed

```json
{
  "lc_number": "LC-2024-00123",
  "issue_date": "2024-03-15",
  "amount": 125000.0,
  "beneficiary": "Global Traders Ltd"
}
```
