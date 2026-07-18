import re
import json
import pdfplumber
import fitz
import pytesseract
from pdf2image import convert_from_path
from groq import Groq
from dateutil import parser as date_parser

from Prompts.extract_fields_prompts import build_extraction_prompt


# ── text extraction ──────────────────────────────────────────────────────────

def get_raw_text(doc):
    """Extract text from a document using a 3-layer fallback chain.
    Returns (text, ocr_used). ocr_used is True only if OCR was needed."""
    raw_text = doc["raw_text"]
    if raw_text:
        return raw_text, False

    file_path = doc["file_path"]

    text = _try_pdfplumber(file_path)
    if text:
        return text, False

    text = _try_pymupdf(file_path)
    if text:
        return text, False

    text = _try_ocr(file_path)
    if text:
        return text, True

    return None, False


def _try_pdfplumber(file_path):
    """Layer 1: extract text using pdfplumber. Returns None on failure."""
    try:
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text.strip() or None
    except Exception:
        return None


def _try_pymupdf(file_path):
    """Layer 2: extract text using pymupdf (fitz). Returns None on failure."""
    try:
        doc = fitz.open(file_path)
        pages = []
        for page in doc:
            page_text = page.get_text()
            if page_text:
                pages.append(page_text)
        doc.close()
        return "\n".join(pages).strip() or None
    except Exception:
        return None


def _try_ocr(file_path):
    """Layer 3: OCR fallback using pytesseract at 300 DPI. Returns None on failure."""
    try:
        images = convert_from_path(file_path, dpi=300)
        results = []
        for image in images:
            page_text = pytesseract.image_to_string(image)
            if page_text:
                results.append(page_text)
        return "\n".join(results).strip() or None
    except Exception:
        return None


# ── llm extraction ───────────────────────────────────────────────────────────

def call_llm_extract(raw_text, target_fields, ocr_used, model, api_key, validation_errors=None):
    """Make one Groq LLM call to extract target fields from the document text.
    Returns a dict of {field_name: raw_value}. Returns {} if JSON parsing fails."""
    prompt = build_extraction_prompt(raw_text, target_fields, ocr_used, validation_errors)

    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0
    )

    try:
        return json.loads(resp.choices[0].message.content)
    except json.JSONDecodeError:
        return {}


# ── normalization ────────────────────────────────────────────────────────────

def normalize_value(value, field_type):
    """Clean one raw value based on its schema type.
    Numbers → float, dates → ISO YYYY-MM-DD, strings → trimmed. Returns None if unparseable."""
    if value is None or value == "":
        return None

    if field_type == "number":
        cleaned = re.sub(r"[^\d.\-]", "", str(value))
        if cleaned == "":
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    if field_type == "date":
        try:
            parsed = date_parser.parse(str(value), dayfirst=True)
            return parsed.strftime("%Y-%m-%d")
        except (ValueError, OverflowError):
            return None

    if field_type == "string":
        stripped = str(value).strip()
        return stripped if stripped else None

    return value