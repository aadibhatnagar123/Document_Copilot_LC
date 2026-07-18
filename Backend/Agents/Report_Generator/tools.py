import sqlite3
from datetime import date
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from groq import Groq

from Prompts.report_generator_prompts import build_polish_prompt


# ── data preparation ──

def sort_issues_by_severity(issues):
    """Sort issues: critical first, then major, then minor."""
    order = {"critical": 0, "major": 1, "minor": 2}
    return sorted(issues, key=lambda i: order.get(i.get("severity", "major"), 1))


def group_issues_by_severity(issues):
    """Group issues into three lists by severity."""
    groups = {"critical": [], "major": [], "minor": []}
    for issue in issues:
        sev = issue.get("severity", "major")
        if sev in groups:
            groups[sev].append(issue)
        else:
            groups["major"].append(issue)
    return groups


def group_issues_by_doc(issues):
    """Group issues by doc_type."""
    groups = {}
    for issue in issues:
        doc = issue.get("doc_type", "unknown")
        if doc not in groups:
            groups[doc] = []
        groups[doc].append(issue)
    return groups


# ── MT799 generation ──

def build_mt799_text(lc_terms, issues, run_id):
    """Build the MT799 SWIFT notice as plain text."""
    lines = []
    lines.append("MT799 DISCREPANCY NOTICE")
    lines.append("=" * 40)
    lines.append(f"Reference: {run_id[:8]}")
    lines.append(f"Date: {date.today().isoformat()}")
    lines.append("")
    lines.append(f"Documentary Credit No. {lc_terms.get('lc_number', 'N/A')}")
    lines.append(f"Date of Issue: {lc_terms.get('issue_date', 'N/A')}")
    lines.append(f"Applicant: {lc_terms.get('applicant', 'N/A')}")
    lines.append(f"Beneficiary: {lc_terms.get('beneficiary', 'N/A')}")
    lines.append(f"Amount: {lc_terms.get('currency', '')} {lc_terms.get('amount', 'N/A')}")
    lines.append("")
    lines.append("We have examined the documents presented under the above")
    lines.append("referenced credit and found the following discrepancies:")
    lines.append("")

    if not issues:
        lines.append("No discrepancies found. Documents are in order.")
        lines.append("")
    else:
        groups = group_issues_by_severity(issues)
        counter = 1
        for severity in ("critical", "major", "minor"):
            group = groups[severity]
            if not group:
                continue
            lines.append(f"{severity.upper()}:")
            for issue in group:
                lines.append(f"{counter}. {issue.get('message', '')}")
                lines.append(f"   ({issue.get('citation') or 'No citation'})")
                counter += 1
            lines.append("")

    lines.append("Documents are held at your disposal pending your instructions.")
    return "\n".join(lines)


def build_summary_text(
    lc_terms,
    parsed_docs,
    issues,
    run_id,
    recommendation,
    recommendation_summary,
    hitl_decision
):
    """Build the summary report as plain text."""
    lines = []
    lines.append("DOCUMENT COPILOT - RUN REPORT")
    lines.append("=" * 40)
    lines.append(f"Run ID: {run_id}")
    lines.append(f"Date: {date.today().isoformat()}")
    lines.append(f"Documents checked: {len(parsed_docs)}")
    lines.append("")

    lines.append("LC TERMS SUMMARY")
    lines.append("-" * 40)
    lines.append(f"LC Number: {lc_terms.get('lc_number', 'N/A')}")
    lines.append(f"Amount: {lc_terms.get('currency', '')} {lc_terms.get('amount', 'N/A')}")
    lines.append(f"Expiry: {lc_terms.get('expiry_date', 'N/A')}")
    lines.append(f"Beneficiary: {lc_terms.get('beneficiary', 'N/A')}")
    lines.append(f"Applicant: {lc_terms.get('applicant', 'N/A')}")
    lines.append(f"Port of Loading: {lc_terms.get('port_of_loading', 'N/A')}")
    lines.append(f"Port of Discharge: {lc_terms.get('port_of_discharge', 'N/A')}")
    lines.append("")

    groups = group_issues_by_severity(issues)
    lines.append(f"DISCREPANCIES FOUND: {len(issues)}")
    lines.append(f"  Critical: {len(groups['critical'])}")
    lines.append(f"  Major: {len(groups['major'])}")
    lines.append(f"  Minor: {len(groups['minor'])}")
    lines.append("")

    for issue in sort_issues_by_severity(issues):
        lines.append(
            f"[{issue.get('severity', 'major')}] "
            f"{issue.get('doc_type', 'unknown')} - {issue.get('field') or 'N/A'}"
        )
        lines.append(f"  {issue.get('message', '')}")
        lines.append(f"  Citation: {issue.get('citation') or 'N/A'}")
        lines.append("")

    lines.append(f"AI RECOMMENDATION: {recommendation}")
    lines.append(recommendation_summary or "")
    lines.append("")

    lines.append(f"HUMAN DECISION: {hitl_decision}")
    lines.append("")

    lines.append("CONCLUSION:")
    if hitl_decision == "approved" and issues:
        lines.append("Presentation accepted with noted discrepancies.")
    elif hitl_decision == "approved":
        lines.append("Presentation accepted. Documents are in order.")
    else:
        lines.append("Presentation refused. Documents held pending applicant instructions.")

    return "\n".join(lines)


# ── optional LLM polish ──

def call_polish(mt799_text, model, api_key):
    """One Groq call to polish MT799 into banking language."""
    prompt = build_polish_prompt(mt799_text)
    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return resp.choices[0].message.content.strip()


# ── PDF generation ──

def _pdf_safe(text):
    """Replace characters the core PDF fonts cannot encode."""
    replacements = {
        "—": "-",
        "–": "-",
        "═": "=",
        "─": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "•": "-",
    }

    text = str(text)
    for old, new in replacements.items():
        text = text.replace(old, new)

    return text.encode("latin-1", "replace").decode("latin-1")


def text_to_pdf(text, title):
    """Convert a text string into a formatted PDF. Returns bytes."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(
        0,
        10,
        _pdf_safe(title),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align="C"
    )

    pdf.set_font("Helvetica", "", 9)
    pdf.cell(
        0,
        6,
        f"Generated: {date.today().isoformat()}",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align="R"
    )

    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    for line in text.split("\n"):
        stripped = line.strip()

        if stripped.startswith("=") or stripped.startswith("-"):
            continue

        if stripped == "":
            pdf.ln(5)
            continue

        if (
            stripped.startswith("CRITICAL:")
            or stripped.startswith("MAJOR:")
            or stripped.startswith("MINOR:")
        ):
            pdf.set_font("Helvetica", "B", 11)
        else:
            pdf.set_font("Courier", "", 9)

        pdf.multi_cell(
            0,
            5,
            _pdf_safe(line),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT
        )

    return pdf.output()


def save_reports_to_db(run_id, mt799_text, summary_text, mt799_pdf, summary_pdf, db_path):
    """Save both reports text and PDF bytes to the lc_runs table.

    Does not touch status. The orchestrator sets the final status based on
    the HITL decision after this returns.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE lc_runs
        SET mt799_report = ?, summary_report = ?,
            mt799_pdf = ?, summary_pdf = ?
        WHERE run_id = ?
    """, (mt799_text, summary_text, mt799_pdf, summary_pdf, run_id))
    conn.commit()
    conn.close()
