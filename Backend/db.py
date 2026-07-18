import sqlite3
import os
import json
import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lc_copilot.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS lc_runs (
            run_id TEXT PRIMARY KEY,
            schema_name TEXT,
            status TEXT,
            created_at TEXT,
            hitl_decision TEXT,
            report_json TEXT,
            issues_json TEXT,
            ambiguous_json TEXT,
            recommendation TEXT,
            recommendation_summary TEXT,
            mt799_report TEXT,
            summary_report TEXT,
            mt799_pdf BLOB,
            summary_pdf BLOB
        )
    """)

    # Support adding columns if the table already existed before this version
    _add_column(cur, "lc_runs", "hitl_decision", "TEXT")
    _add_column(cur, "lc_runs", "report_json", "TEXT")
    _add_column(cur, "lc_runs", "issues_json", "TEXT")
    _add_column(cur, "lc_runs", "ambiguous_json", "TEXT")
    _add_column(cur, "lc_runs", "recommendation", "TEXT")
    _add_column(cur, "lc_runs", "recommendation_summary", "TEXT")
    _add_column(cur, "lc_runs", "mt799_report", "TEXT")
    _add_column(cur, "lc_runs", "summary_report", "TEXT")
    _add_column(cur, "lc_runs", "mt799_pdf", "BLOB")
    _add_column(cur, "lc_runs", "summary_pdf", "BLOB")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS raw_documents (
            run_id TEXT,
            doc_id TEXT,
            doc_type TEXT,
            file_path TEXT,
            raw_text TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS parsed_documents (
            run_id TEXT,
            doc_id TEXT,
            doc_type TEXT,
            fields_json TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS discrepancies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            doc_type TEXT,
            field TEXT,
            kind TEXT,
            message TEXT,
            citation TEXT,
            severity TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS hitl_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            decision TEXT,
            decided_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            event TEXT,
            details TEXT,
            timestamp TEXT
        )
    """)

    conn.commit()
    conn.close()


def _add_column(cursor, table, column, col_type):
    """Safely add a column to an existing table (no-op if it already exists)."""
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    except sqlite3.OperationalError:
        pass


def get_run(run_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM lc_runs WHERE run_id = ?", (run_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_raw_documents(run_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM raw_documents WHERE run_id = ?", (run_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_parsed_documents(run_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM parsed_documents WHERE run_id = ?", (run_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def insert_parsed_document(run_id, doc_id, doc_type, fields_dict):
    conn = get_conn()
    cur = conn.cursor()
    fields_json = json.dumps(fields_dict)
    cur.execute(
        "INSERT INTO parsed_documents (run_id, doc_id, doc_type, fields_json, created_at) VALUES (?, ?, ?, ?, ?)",
        (run_id, doc_id, doc_type, fields_json, datetime.datetime.now(datetime.UTC).isoformat())
    )
    conn.commit()
    conn.close()


def update_run_status(run_id, status):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE lc_runs SET status = ? WHERE run_id = ?", (status, run_id))
    conn.commit()
    conn.close()


def update_run_decision_and_report(run_id, decision, report_dict):
    conn = get_conn()
    cur = conn.cursor()
    report_json = json.dumps(report_dict) if report_dict else None
    cur.execute(
        "UPDATE lc_runs SET hitl_decision = ?, report_json = ? WHERE run_id = ?",
        (decision, report_json, run_id)
    )
    conn.commit()
    conn.close()


def update_run_issues_and_ambiguous(run_id, issues, ambiguous=None):
    conn = get_conn()
    cur = conn.cursor()
    issues_json = json.dumps(issues) if issues is not None else None
    if ambiguous is not None:
        ambiguous_json = json.dumps(ambiguous)
        cur.execute(
            "UPDATE lc_runs SET issues_json = ?, ambiguous_json = ? WHERE run_id = ?",
            (issues_json, ambiguous_json, run_id)
        )
    else:
        cur.execute(
            "UPDATE lc_runs SET issues_json = ? WHERE run_id = ?",
            (issues_json, run_id)
        )
    conn.commit()
    conn.close()
