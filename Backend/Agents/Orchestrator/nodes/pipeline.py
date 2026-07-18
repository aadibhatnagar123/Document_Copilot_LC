from langgraph.types import interrupt

from .. import config
from .. import tools

from Agents.Doc_Parser.graph import build_doc_parser_subgraph
from Agents.Internal_Checker.graph import build_internal_checker_subgraph
from Agents.Semantic_Comparator.graph import build_semantic_comparator_subgraph
from Agents.Report_Generator.graph import build_report_generator_subgraph


# compile each agent subgraph once at module level
_parser = build_doc_parser_subgraph()
_checker = build_internal_checker_subgraph()
_semantic = build_semantic_comparator_subgraph()
_reporter = build_report_generator_subgraph()


# ── node 1: load run ──

def load_run(state):
    """Read run data from DB and load schema config."""
    run_id = state["run_id"]

    run = tools.read_run(run_id)
    if not run:
        return {"status": "error"}

    schema_name = run.get("schema_name", "lc")
    try:
        schema = config.load_schema(schema_name)
    except FileNotFoundError:
        return {"status": "error"}

    raw_docs = tools.read_raw_documents(run_id)
    if not raw_docs:
        return {"status": "error"}

    tools.update_status(run_id, "parsing")

    defaults = tools.empty_state()
    defaults.update({
        "schema": schema,
        "raw_docs": raw_docs,
        "status": "parsing",
    })
    return defaults


# ── node 2: parse documents (Agent 1) ──

def parse_documents(state):
    """Run Agent 1 on each doc. Skip failed docs, don't crash the run."""
    parsed = {}
    failed_count = 0

    for doc in state["raw_docs"]:
        try:
            result = _parser.invoke({
                "doc": doc,
                "schema": state["schema"],
                "raw_text": "",
                "ocr_used": False,
                "target_fields": [],
                "raw_values": {},
                "validation_errors": [],
                "fields": {},
                "retry_count": 0,
                "valid": False,
                "parse_failed": False,
            })

            if result.get("parse_failed"):
                parsed[doc["doc_type"]] = {"parse_failed": True}
                failed_count += 1
            else:
                parsed[doc["doc_type"]] = result["fields"]

            tools.save_parsed_doc(
                state["run_id"], doc["doc_id"],
                doc["doc_type"], result.get("fields", {})
            )

        except Exception as e:
            parsed[doc["doc_type"]] = {"parse_failed": True}
            failed_count += 1
            tools.log_error(state["run_id"], "parse", doc["doc_type"], str(e))

    # if every doc failed, stop
    if failed_count == len(state["raw_docs"]):
        tools.update_status(state["run_id"], "error")
        return {"parsed_docs": parsed, "status": "error"}

    tools.update_status(state["run_id"], "checker")
    return {"parsed_docs": parsed, "status": "checker"}


# ── node 3: check documents (Agent 2) ──

def check_documents(state):
    """Run Agent 2. Retry once on crash."""
    for attempt in range(2):
        try:
            result = _checker.invoke({
                "run_id": state["run_id"],
                "parsed_docs": state["parsed_docs"],
                "schema": state["schema"],
                "issues": [],
                "lc_ok": True,
                "ambiguous_pairs": [],
                "blocked": False,
                "lc_terms": {},
            })

            for issue in result.get("issues", []):
                tools.save_discrepancy(state["run_id"], issue)

            status = "blocked" if result.get("blocked") else "semantic"
            tools.update_status(state["run_id"], status)

            return {
                "issues": result.get("issues", []),
                "lc_terms": result.get("lc_terms", {}),
                "ambiguous_pairs": result.get("ambiguous_pairs", []),
                "blocked": result.get("blocked", False),
                "lc_ok": result.get("lc_ok", True),
                "status": status,
            }

        except Exception as e:
            if attempt == 0:
                tools.log_error(state["run_id"], "checker", "retry", str(e))
                continue
            tools.log_error(state["run_id"], "checker", "failed", str(e))
            tools.update_status(state["run_id"], "error")
            return {"status": "error"}


# ── node 4: semantic compare (Agent 3) ──

def semantic_compare(state):
    """Run Agent 3. If it crashes, apply defaults and continue to HITL."""
    try:
        result = _semantic.invoke({
            "ambiguous_pairs": state["ambiguous_pairs"],
            "issues": state["issues"],
            "schema": state["schema"],
            "resolved_issues": [],
            "resolve_failed": False,
            "severity_failed": False,
            "recommendation_failed": False,
            "rule_contexts": [],
            "recommendation": "",
            "recommendation_summary": "",
        })

        issues = result.get("issues", state["issues"])
        rec = result.get("recommendation", "")
        rec_summary = result.get("recommendation_summary", "")

        # save severity updates + new issues
        for issue in issues:
            tools.update_discrepancy_severity(state["run_id"], issue)
            if issue.get("kind") in ("semantic_mismatch", "needs_manual_review"):
                tools.save_discrepancy(state["run_id"], issue)

        tools.save_recommendation(state["run_id"], rec, rec_summary)
        tools.update_status(state["run_id"], "hitl")

        return {
            "issues": issues,
            "recommendation": rec,
            "recommendation_summary": rec_summary,
            "ambiguous_pairs": result.get("ambiguous_pairs", []),
            "status": "hitl",
        }

    except Exception as e:
        # crashed — apply defaults so HITL still works
        tools.log_error(state["run_id"], "semantic", "crashed", str(e))

        from Agents.Semantic_Comparator.tools import (
            apply_default_severity, default_recommendation
        )
        apply_default_severity(state["issues"])
        rec = default_recommendation(state["issues"])

        for issue in state["issues"]:
            tools.update_discrepancy_severity(state["run_id"], issue)

        tools.save_recommendation(
            state["run_id"], rec["recommendation"], rec["summary"]
        )
        tools.update_status(state["run_id"], "hitl")

        return {
            "issues": state["issues"],
            "recommendation": rec["recommendation"],
            "recommendation_summary": rec["summary"],
            "ambiguous_pairs": [],
            "status": "hitl",
        }


# ── node 5: hitl checkpoint ──

def hitl_checkpoint(state):
    """Pause for human review. Graph stops here until resumed."""
    decision = interrupt({
        "issues": state["issues"],
        "recommendation": state["recommendation"],
        "recommendation_summary": state["recommendation_summary"],
        "message": "Review issues and choose: approve, reject, or retry.",
    })

    action = decision.get("action", "rejected")
    retry_from = decision.get("retry_from", "")

    tools.save_hitl_decision(state["run_id"], action)

    return {
        "hitl_decision": action,
        "retry_from": retry_from,
    }


# ── node 6: generate reports (Agent 4) ──

def generate_reports(state):
    """Run Agent 4 regardless of approve/reject — a rejected run still gets
    an MT799 refusal notice and summary. Retry once on crash."""
    tools.update_status(state["run_id"], "report")
    final_status = "done" if state["hitl_decision"] == "approved" else "rejected"

    for attempt in range(2):
        try:
            result = _reporter.invoke({
                "run_id": state["run_id"],
                "issues": state["issues"],
                "parsed_docs": state["parsed_docs"],
                "lc_terms": state["lc_terms"],
                "schema": state["schema"],
                "recommendation": state["recommendation"],
                "recommendation_summary": state["recommendation_summary"],
                "hitl_decision": state["hitl_decision"],
                "mt799_text": "",
                "summary_text": "",
                "mt799_pdf": b"",
                "summary_pdf": b"",
                "polish_failed": False,
            })

            tools.update_status(state["run_id"], final_status)

            return {
                "mt799_text": result.get("mt799_text", ""),
                "summary_text": result.get("summary_text", ""),
                "mt799_pdf": result.get("mt799_pdf", b""),
                "summary_pdf": result.get("summary_pdf", b""),
                "status": final_status,
            }

        except Exception as e:
            if attempt == 0:
                tools.log_error(state["run_id"], "report", "retry", str(e))
                continue
            tools.log_error(state["run_id"], "report", "failed", str(e))
            tools.update_status(state["run_id"], "error")
            return {"status": "error"}


# ── terminal nodes ──

def mark_rejected(state):
    """Mark run as rejected in DB."""
    tools.update_status(state["run_id"], "rejected")
    return {"status": "rejected"}


def mark_error(state):
    """Mark run as error in DB."""
    tools.update_status(state["run_id"], "error")
    return {"status": "error"}