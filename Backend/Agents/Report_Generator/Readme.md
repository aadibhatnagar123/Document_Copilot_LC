# Report_Generator

**Role**: Generates MT799 SWIFT discrepancy notice + full run summary report as text and downloadable PDFs.

---

## How it works

Receives all issues (with severity + citations), LC terms, parsed docs, the AI recommendation, and the HITL decision. Sorts issues by severity, builds an MT799 SWIFT-formatted notice from a template, optionally polishes it via a Groq LLM call into formal banking language, then builds a full summary report. Both outputs are converted to PDF via FPDF and saved to SQLite. Runs for both approved and rejected decisions.

**Pipeline**:
```
gather_data → generate_mt799 → polish_mt799 → generate_summary → save_reports
```

---

## Inputs

- **`run_id`** — unique run identifier
- **`issues`** — all discrepancies with `severity`, `citation`, `kind`, `message`
- **`lc_terms`** — LC term sheet fields (`lc_number`, `applicant`, `beneficiary`, `amount`, etc.)
- **`parsed_docs`** — Agent 1 output (all parsed document fields)
- **`recommendation`** / **`recommendation_summary`** — Agent 3's approve/reject + reasoning
- **`hitl_decision`** — `"approved"` or `"rejected"` — the human's final call
- **Env vars** — `GROQ_API_KEY` (required), `GROQ_MODEL` (optional)

---

## Project Structure

```
Report_Generator/
├── agent.yaml             # Agent spec (v1.0, 1 optional LLM call, dependencies)
├── config.py              # GROQ_API_KEY, GROQ_MODEL, load_schema(), load_report_template()
├── tools.py               # MT799 builder, summary builder, LLM polish, PDF gen, DB save
├── state.py               # ReportState TypedDict (12 fields)
├── graph.py               # LangGraph StateGraph (5 nodes, linear — no conditional edges)
├── __init__.py            # Package marker
└── nodes/
    ├── __init__.py        # Package marker
    └── pipeline.py        # gather_data, generate_mt799, polish_mt799, generate_summary, save_reports
```

**External prompt**: `Prompts/report_generator_prompts.py` → `build_polish_prompt()` — rewrites MT799 into formal banking language

---

## Processing

| Node | What it does |
|---|---|
| `gather_data` | Sorts all issues by severity (critical → major → minor) |
| `generate_mt799` | Builds MT799 SWIFT notice from template: LC header, discrepancies by severity with citations |
| `polish_mt799` | Optional Groq LLM call (`temperature=0.3`) to refine into banking language. On failure → keeps template |
| `generate_summary` | Builds full run summary text (LC terms, issue counts, all discrepancies, AI + HITL decisions). Converts both texts to PDF via FPDF |
| `save_reports` | Writes `mt799_text`, `summary_text`, `mt799_pdf`, `summary_pdf` to `lc_runs` table in SQLite |

---

## Tools

| Group | Tools | Purpose |
|---|---|---|
| Data Prep | `sort_issues_by_severity`, `group_issues_by_severity`, `group_issues_by_doc` | Sort and group issues for report sections |
| MT799 | `build_mt799_text` | Builds SWIFT MT799 formatted text with LC reference + discrepancies |
| Summary | `build_summary_text` | Builds full run report: terms, counts, issues, recommendation, HITL decision, conclusion |
| LLM Polish | `call_polish` | Single Groq call to rewrite MT799 into formal banking prose |
| PDF | `text_to_pdf`, `_pdf_safe` | FPDF-based PDF generation with Helvetica headers + Courier body. Unicode→ASCII sanitization |
| DB | `save_reports_to_db` | Saves all 4 outputs (2 text + 2 PDF bytes) to `lc_runs` row |

---

## Output

- **`mt799_text`** — `str`, MT799 SWIFT discrepancy notice (polished or template)
- **`summary_text`** — `str`, full run summary with LC terms, all issues, decisions, and conclusion
- **`mt799_pdf`** — `bytes`, MT799 as formatted PDF
- **`summary_pdf`** — `bytes`, summary report as formatted PDF
