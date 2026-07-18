from fastapi import APIRouter, Depends, File, UploadFile, BackgroundTasks, HTTPException, Response
from typing import List, Dict, Any
import uuid
import os
import datetime
import json
import re
import db
from Agents.Orchestrator import graph as orchestrator
from Agents.Semantic_Comparator.tools import apply_default_severity
from api.auth import require_api_key

try:
    from rag.retriever import query as rag_query
except ImportError:
    rag_query = None


router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB per file
MAX_SUPPORTING_DOCS = 7


def safe_filename(filename: str) -> str:
    """Strip directory components and any character that isn't safe in a path
    segment, so a crafted filename (e.g. '../../x') can't escape the run's
    upload directory."""
    name = os.path.basename(filename or "")
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return name or "file.pdf"


async def read_validated_pdf(upload: UploadFile) -> bytes:
    """Read an uploaded file fully, enforcing a size limit and checking the
    PDF magic bytes so the content type can't just be spoofed client-side."""
    content = await upload.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"{upload.filename} exceeds the {MAX_FILE_SIZE // (1024 * 1024)}MB size limit",
        )
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail=f"{upload.filename} is not a valid PDF file")
    return content


def doc_type_from_filename(filename: str) -> str:
    name = os.path.splitext(filename)[0].lower()
    name = re.sub(r"^document_\d+_", "", name)
    name = re.sub(r"[^a-z0-9_]", "_", name)
    # clean up multiple underscores
    name = re.sub(r"_+", "_", name).strip("_")
    
    # Map common naming patterns to schema expected document types
    # Expected: invoice, packing_list, bill_of_lading, certificate_of_origin, insurance_certificate, bill_of_exchange, inspection_certificate, lc_terms
    if "invoice" in name:
        return "invoice"
    if "packing" in name:
        return "packing_list"
    if "lading" in name or "b_l" in name or "bol" in name:
        return "bill_of_lading"
    if "origin" in name or "coo" in name:
        return "certificate_of_origin"
    if "insurance" in name or "policy" in name:
        return "insurance_certificate"
    if "exchange" in name or "boe" in name:
        return "bill_of_exchange"
    if "inspection" in name or "certificate" in name:
        return "inspection_certificate"
    if "term" in name or "sheet" in name or "lc" in name:
        return "lc_terms"
    return name


@router.post("/upload")
async def upload_files(
    background_tasks: BackgroundTasks,
    term_sheet: UploadFile = File(...),
    documents: List[UploadFile] = File(...),
    _auth: None = Depends(require_api_key)
):
    if len(documents) == 0:
        raise HTTPException(status_code=400, detail="At least one supporting document is required")
    if len(documents) > MAX_SUPPORTING_DOCS:
        raise HTTPException(status_code=400, detail=f"At most {MAX_SUPPORTING_DOCS} supporting documents are allowed")

    db.create_tables()  # Ensure tables exist

    run_id = str(uuid.uuid4())
    run_dir = os.path.join(UPLOAD_DIR, run_id)
    os.makedirs(run_dir, exist_ok=True)

    # Save term sheet
    term_sheet_bytes = await read_validated_pdf(term_sheet)
    term_sheet_path = os.path.join(run_dir, "term_sheet_" + safe_filename(term_sheet.filename))
    with open(term_sheet_path, "wb") as buffer:
        buffer.write(term_sheet_bytes)

    # Save supporting documents
    saved_docs = []
    for i, doc in enumerate(documents, start=1):
        doc_bytes = await read_validated_pdf(doc)
        doc_path = os.path.join(run_dir, f"doc_{i}_" + safe_filename(doc.filename))
        with open(doc_path, "wb") as buffer:
            buffer.write(doc_bytes)
        saved_docs.append((doc.filename, doc_path))

    # Seed Database
    conn = db.get_conn()
    cur = conn.cursor()
    
    cur.execute(
        "INSERT INTO lc_runs (run_id, schema_name, status, created_at) VALUES (?, ?, ?, ?)",
        (run_id, "lc", "parser", datetime.datetime.now(datetime.UTC).isoformat())
    )
    
    # 2. Insert Term Sheet in raw_documents
    ts_doc_id = "doc_term_sheet"
    cur.execute(
        "INSERT INTO raw_documents (run_id, doc_id, doc_type, file_path, raw_text) VALUES (?, ?, ?, ?, ?)",
        (run_id, ts_doc_id, "lc_terms", term_sheet_path, "")
    )
    
    # 3. Insert Supporting Documents
    for i, (filename, file_path) in enumerate(saved_docs, start=1):
        doc_id = f"doc_{i}"
        doc_type = doc_type_from_filename(filename)
        cur.execute(
            "INSERT INTO raw_documents (run_id, doc_id, doc_type, file_path, raw_text) VALUES (?, ?, ?, ?, ?)",
            (run_id, doc_id, doc_type, file_path, "")
        )
        
    conn.commit()
    conn.close()
    
    # Start Orchestrator Graph asynchronously
    background_tasks.add_task(orchestrator.run_pipeline, run_id)
    
    return {"run_id": run_id}


@router.get("/runs/{run_id}")
async def get_run_status(run_id: str, _auth: None = Depends(require_api_key)):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Convert sqlite Row to dict
    run_dict = dict(run)
    
    # Get raw documents to count them
    raw_docs = db.get_raw_documents(run_id)
    doc_count = len(raw_docs)
    
    # Get parsed documents
    parsed_docs = db.get_parsed_documents(run_id)
    
    # Compile issues/validation errors
    issues = []
    
    # Load checker issues from DB
    if run_dict.get("issues_json"):
        try:
            issues = json.loads(run_dict["issues_json"])
        except Exception as e:
            print(f"Error loading issues_json for run {run_id}: {e}")

    # Merge in missing values warnings if they aren't already reported
    existing_messages = {iss["message"] for iss in issues if "message" in iss}
    for doc in parsed_docs:
        doc_id = doc["doc_id"]
        doc_type = doc["doc_type"]
        try:
            fields = json.loads(doc["fields_json"])
        except Exception as e:
            print(f"Error loading fields_json for document {doc_id}: {e}")
            fields = {}
        
        for field_name, value in fields.items():
            if value is None:
                msg = f"Field '{field_name}' in {doc_type} is missing or could not be parsed."
                if msg not in existing_messages:
                    citation = doc_type.replace("_", " ").title()
                    if rag_query:
                        corpus = None
                        if doc_type in ["invoice", "bill_of_lading", "insurance_certificate"]:
                            corpus = "ucp"
                        elif doc_type in ["packing_list", "certificate_of_origin", "inspection_certificate"]:
                            corpus = "isbp"
                        
                        query_text = f"{doc_type} {field_name} missing_field"
                        try:
                            results = rag_query(query_text, k=1, corpus=corpus)
                            if results and len(results) > 0:
                                citation = results[0].get("ref")
                        except Exception:
                            pass
                    
                    issues.append({
                        "message": msg,
                        "citation": citation,
                        "kind": "warning"
                    })

    # Format citations for issues (fallback for any other missing doc_type citation)
    for issue in issues:
        if not issue.get("citation") and issue.get("doc_type"):
            citation = issue["doc_type"].replace("_", " ").title()
            if rag_query:
                corpus = None
                if issue["doc_type"] in ["invoice", "bill_of_lading", "insurance_certificate"]:
                    corpus = "ucp"
                elif issue["doc_type"] in ["packing_list", "certificate_of_origin", "inspection_certificate"]:
                    corpus = "isbp"
                
                query_text = f"{issue['doc_type']} {issue.get('field', '')} {issue.get('kind', '')}"
                try:
                    results = rag_query(query_text, k=1, corpus=corpus)
                    if results and len(results) > 0:
                        citation = results[0].get("ref")
                except Exception:
                    pass
            issue["citation"] = citation

    # Ensure every issue carries a severity so the UI can colour it. Agent 3
    # classifies most issues, but API-appended missing-value warnings (and any
    # run where the severity pass fell back without stamping) can arrive with
    # severity=None. This maps kind -> severity deterministically, matching the
    # same logic the report generator uses.
    apply_default_severity(issues)


    # Load the real generated report (written by the Report_Generator agent)
    # once the run is done.
    report = None
    if run_dict.get("summary_report"):
        report = {"content": run_dict["summary_report"]}

    return {
        "run_id": run_id,
        "status": run_dict["status"],
        "doc_count": doc_count,
        "issues": issues,
        "recommendation": run_dict.get("recommendation"),
        "recommendation_summary": run_dict.get("recommendation_summary"),
        "hitl_decision": run_dict.get("hitl_decision"),
        "report": report
    }


@router.post("/runs/{run_id}/decision")
async def submit_decision(
    run_id: str,
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks,
    _auth: None = Depends(require_api_key)
):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    decision = payload.get("decision")
    if decision not in ["approved", "rejected", "retry"]:
        raise HTTPException(status_code=400, detail="Invalid decision value")

    retry_from = payload.get("retry_from")
    if decision == "retry" and retry_from not in ["agent1", "agent2", "agent3"]:
        raise HTTPException(status_code=400, detail="Invalid retry_from value")

    # The real report (MT799 + summary, as text and PDF) is generated by the
    # Report_Generator agent once the orchestrator resumes past this point —
    # nothing to fabricate here.
    db.update_run_decision_and_report(run_id, decision, None)

    # Resume orchestrator pipeline in the background
    resume_payload = {"action": decision}
    if decision == "retry":
        resume_payload["retry_from"] = retry_from
    background_tasks.add_task(orchestrator.resume_pipeline, run_id, resume_payload)

    return {"status": "success"}


@router.get("/runs/{run_id}/report/mt799")
async def download_mt799(run_id: str):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run_dict = dict(run)
    pdf_bytes = run_dict.get("mt799_pdf")
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail="MT799 report PDF not found or not yet generated")
        
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=mt799_{run_id[:8]}.pdf"}
    )


@router.get("/runs/{run_id}/report/summary")
async def download_summary(run_id: str):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    run_dict = dict(run)
    pdf_bytes = run_dict.get("summary_pdf")
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail="Summary report PDF not found or not yet generated")
        
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=summary_{run_id[:8]}.pdf"}
    )
