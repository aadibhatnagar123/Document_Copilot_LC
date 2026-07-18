import json
import sqlite3

from . import config


# ── db reads ──

def read_run(run_id):
    """Read one run row from the DB."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM lc_runs WHERE run_id = ?", (run_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def read_raw_documents(run_id):
    """Read all raw document rows for a run."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM raw_documents WHERE run_id = ?", (run_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── db writes ──

def update_status(run_id, status):
    """Write status to DB so frontend can poll it."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("UPDATE lc_runs SET status = ? WHERE run_id = ?", (status, run_id))
    conn.commit()
    conn.close()


def save_parsed_doc(run_id, doc_id, doc_type, fields):
    """Write one parsed document to DB."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO parsed_documents "
        "(run_id, doc_id, doc_type, fields_json, created_at) "
        "VALUES (?, ?, ?, ?, datetime('now'))",
        (run_id, doc_id, doc_type, json.dumps(fields))
    )
    conn.commit()
    conn.close()


def save_discrepancy(run_id, issue):
    """Write one discrepancy row to DB."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(
        "INSERT INTO discrepancies "
        "(run_id, doc_type, field, kind, message, citation, severity) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (run_id, issue.get("doc_type"), issue.get("field"),
         issue.get("kind"), issue.get("message"),
         issue.get("citation"), issue.get("severity"))
    )
    conn.commit()
    conn.close()


def update_discrepancy_severity(run_id, issue):
    """Update severity on an existing discrepancy row."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(
        "UPDATE discrepancies SET severity = ? "
        "WHERE run_id = ? AND doc_type = ? AND field = ? AND kind = ?",
        (issue.get("severity"), run_id, issue.get("doc_type"),
         issue.get("field"), issue.get("kind"))
    )
    conn.commit()
    conn.close()


def save_recommendation(run_id, recommendation, summary):
    """Save Agent 3's recommendation to the run row."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(
        "UPDATE lc_runs SET recommendation = ?, recommendation_summary = ? "
        "WHERE run_id = ?",
        (recommendation, summary, run_id)
    )
    conn.commit()
    conn.close()


def save_hitl_decision(run_id, decision):
    """Record the human's HITL decision."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(
        "INSERT INTO hitl_decisions (run_id, decision, decided_at) "
        "VALUES (?, ?, datetime('now'))",
        (run_id, decision)
    )
    conn.commit()
    conn.close()


def log_error(run_id, agent, context, error):
    """Write an error to the audit log."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(
        "INSERT INTO audit_log (run_id, event, details, timestamp) "
        "VALUES (?, ?, ?, datetime('now'))",
        (run_id, f"{agent}_error", f"{context}: {error}")
    )
    conn.commit()
    conn.close()


# ── state helpers ──

def empty_state():
    """Return default values for all state keys except run_id."""
    return {
        "schema": {},
        "raw_docs": [],
        "parsed_docs": {},
        "lc_terms": {},
        "issues": [],
        "ambiguous_pairs": [],
        "blocked": False,
        "lc_ok": True,
        "recommendation": "",
        "recommendation_summary": "",
        "hitl_decision": "",
        "retry_from": "",
        "mt799_text": "",
        "summary_text": "",
        "mt799_pdf": b"",
        "summary_pdf": b"",
        "status": "",
    }