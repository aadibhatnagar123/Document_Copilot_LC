import uuid
import json
import datetime
import os
import re

import db


def doc_type_from_filename(filename):
    """Derive doc type from filename automatically.
    e.g. 'document_1_letter_of_credit.pdf' → 'letter_of_credit'
    """
    name = os.path.splitext(filename)[0]          # strip .pdf
    name = re.sub(r"^document_\d+_", "", name)    # strip 'document_N_' prefix
    if name == "letter_of_credit":
        return "lc_terms"
    if name == "commercial_invoice":
        return "invoice"
    return name


def seed_from_test_data():
    db.create_tables()

    run_id = str(uuid.uuid4())
    conn = db.get_conn()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO lc_runs (run_id, schema_name, status, created_at) VALUES (?, ?, ?, ?)",
        (run_id, "none", "pending", datetime.datetime.now(datetime.UTC).isoformat())
    )

    test_data_dir = os.path.join(os.path.dirname(__file__), "test_data")
    pdf_files = sorted(f for f in os.listdir(test_data_dir) if f.endswith(".pdf"))

    for i, filename in enumerate(pdf_files, start=1):
        file_path = os.path.join(test_data_dir, filename)
        doc_id = f"doc_{i}"
        doc_type = doc_type_from_filename(filename)
        cur.execute(
            "INSERT INTO raw_documents (run_id, doc_id, doc_type, file_path, raw_text) VALUES (?, ?, ?, ?, ?)",
            (run_id, doc_id, doc_type, file_path, "")
        )
        print(f"  Registered: {doc_id} ({doc_type}) -> {filename}")

    conn.commit()
    conn.close()
    return run_id


if __name__ == "__main__":
    from Agents.Orchestrator import orchestrator

    print("Seeding test_data PDFs into DB...")
    run_id = seed_from_test_data()
    print(f"seeded run_id: {run_id}\n")

    print("Running orchestrator graph...")
    final_state = orchestrator.run_graph(run_id)
    print("\n=== Parsed Results ===")
    print(json.dumps(final_state["parsed_results"], indent=2))
