import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { FileText, Hand, FileCheck, X, Check } from "lucide-react";
import StepRow from "../components/StepRow";
import { API_BASE, apiHeaders } from "../lib/api";

const STEPS = [
  { key: "parser",   label: "Agent 1 — Parser",     pendingMsg: "Waiting to start",                  runningMsg: "Extracting text from documents…",      doneMsg: "Text extraction completed" },
  { key: "checker",  label: "Agent 2 — Checker",    pendingMsg: "Waiting for Agent 1",               runningMsg: "Running gate and completeness checks…", doneMsg: "Gate passed" },
  { key: "semantic", label: "Agent 3 — Semantic",   pendingMsg: "Waiting for Agent 2",               runningMsg: "Comparing ambiguous fields…",           doneMsg: "Semantic comparison completed" },
  { key: "hitl",     label: "HITL checkpoint",      pendingMsg: "Waiting for Agent 3",               runningMsg: "Waiting for your review",               doneMsg: "Approved" },
  { key: "report",   label: "Agent 4 — Report",     pendingMsg: "Waiting for approval",              runningMsg: "Writing MT799 notice…",                 doneMsg: "Report ready" },
];

const STEP_ORDER = ["parser", "checker", "semantic", "hitl", "report"];

function normalizeStatus(runStatus) {
  if (runStatus === "parsing") return "parser";
  return runStatus;
}

// "rejected" is ambiguous on its own: it's used both when the LC terms gate
// blocks the run right after the checker step (no report), and when a human
// rejects at HITL — which now still runs Agent 4, so a report exists. Use
// hasReport to tell the two apart instead of guessing from the status alone.
function getStepStatus(stepKey, runStatus, hasReport) {
  const stepIndex = STEP_ORDER.indexOf(stepKey);

  if (runStatus === "done" || (runStatus === "rejected" && hasReport)) {
    return "done";
  }

  if (runStatus === "blocked" || (runStatus === "rejected" && !hasReport)) {
    return stepIndex <= STEP_ORDER.indexOf("checker") ? "done" : "pending";
  }

  const currentIndex = STEP_ORDER.indexOf(normalizeStatus(runStatus));
  if (currentIndex === -1) return "pending"; // unknown/error status
  if (stepIndex < currentIndex) return "done";
  if (stepIndex === currentIndex) return "running";
  return "pending";
}

function getStepMessage(step, status, runData) {
  if (status === "done") {
    if (step.key === "checker" && runData?.issues?.length > 0) {
      return `Gate passed · ${runData.issues.length} issue${runData.issues.length > 1 ? "s" : ""} found`;
    }
    if (step.key === "hitl") {
      return runData?.hitl_decision === "approved" ? "Approved" : "Rejected";
    }
    return step.doneMsg;
  }
  if (status === "running") return step.runningMsg;
  return step.pendingMsg;
}

// Colour treatment per severity. Kept in sync with the backend's
// apply_default_severity map so the UI never shows a severity the report can't.
const SEVERITY_STYLES = {
  critical: { label: "Critical", dot: "bg-red-500",    badge: "bg-red-50 text-red-700 border-red-200" },
  major:    { label: "Major",    dot: "bg-orange-500", badge: "bg-orange-50 text-orange-700 border-orange-200" },
  minor:    { label: "Minor",    dot: "bg-green-500",  badge: "bg-green-50 text-green-700 border-green-200" },
};

// Fallback for issues that reach the UI without a severity, mirroring the
// backend's kind -> severity mapping.
function resolveSeverity(issue) {
  if (issue.severity && SEVERITY_STYLES[issue.severity]) return issue.severity;
  const critical = ["missing_doc", "lc_terms_incomplete", "lc_expired", "unreadable"];
  const minor = ["missing_field", "date_invalid"];
  if (critical.includes(issue.kind)) return "critical";
  if (minor.includes(issue.kind)) return "minor";
  return "major";
}

// Order issues critical -> major -> minor. Stable: keeps original order
// within a severity band.
const SEVERITY_RANK = { critical: 0, major: 1, minor: 2 };
function sortBySeverity(issues) {
  return [...issues].sort(
    (a, b) => SEVERITY_RANK[resolveSeverity(a)] - SEVERITY_RANK[resolveSeverity(b)]
  );
}

function IssueRow({ issue }) {
  const severity = resolveSeverity(issue);
  const style = SEVERITY_STYLES[severity];
  return (
    <div className="flex gap-2.5 items-start px-3.5 py-3 border-b border-slate-100 last:border-0">
      <div className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${style.dot}`} />
      <div className="min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded border ${style.badge}`}>
            {style.label}
          </span>
          <p className="text-sm text-slate-700">{issue.message}</p>
        </div>
        <p className="text-xs text-slate-400 mt-0.5">
          {issue.citation && <span>{issue.citation} · </span>}
          {issue.kind}
        </p>
      </div>
    </div>
  );
}

function RecommendationBanner({ recommendation, summary }) {
  if (!recommendation) return null;
  const isApprove = recommendation.toLowerCase() === "approve";
  const style = isApprove
    ? "bg-green-50 border-green-200 text-green-800"
    : "bg-red-50 border-red-200 text-red-800";
  const Icon = isApprove ? Check : X;
  return (
    <div className={`rounded-lg border px-3.5 py-3 mb-3 ${style}`}>
      <div className="flex items-center gap-1.5 mb-1">
        <Icon size={14} />
        <span className="text-xs font-semibold uppercase tracking-wide">
          AI recommendation · {isApprove ? "Approve" : "Reject"}
        </span>
      </div>
      {summary && <p className="text-sm leading-relaxed opacity-90">{summary}</p>}
    </div>
  );
}

const RETRY_TARGETS = [
  { key: "agent1", label: "Redo parsing" },
  { key: "agent2", label: "Redo checking" },
  { key: "agent3", label: "Redo semantic compare" },
];

function HitlPanel({ issues, runId, recommendation, recommendationSummary, onDecision }) {
  const [loading, setLoading] = useState(false);
  const [showRetry, setShowRetry] = useState(false);

  async function submitDecision(decision, retryFrom) {
    setLoading(true);
    try {
      await fetch(`${API_BASE}/runs/${runId}/decision`, {
        method: "POST",
        headers: apiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ decision, retry_from: retryFrom }),
      });
      onDecision(decision);
    } catch (err) {
      console.log(err);
      alert("Something went wrong submitting your decision");
      setLoading(false);
    }
  }

  return (
    <div className="border-2 border-blue-600 rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-blue-100 bg-blue-50">
        <Hand size={16} className="text-blue-600" />
        <p className="text-sm font-medium text-slate-700">Review required</p>
      </div>
      <div className="px-4 py-3">
        <p className="text-sm text-slate-500 mb-3">
          Review the {issues.length} issue{issues.length > 1 ? "s" : ""} found before the report is written.
        </p>
        <RecommendationBanner recommendation={recommendation} summary={recommendationSummary} />
        {issues.map((issue, i) => (
          <IssueRow key={i} issue={issue} />
        ))}
      </div>

      {showRetry ? (
        <div className="flex flex-wrap gap-2 px-4 py-3 border-t border-slate-100">
          {RETRY_TARGETS.map((t) => (
            <button
              key={t.key}
              onClick={() => submitDecision("retry", t.key)}
              disabled={loading}
              className="border border-slate-300 text-slate-700 rounded-lg px-3 py-2 text-sm font-medium"
            >
              {t.label}
            </button>
          ))}
          <button
            onClick={() => setShowRetry(false)}
            disabled={loading}
            className="text-sm text-slate-500 px-3 py-2"
          >
            Cancel
          </button>
        </div>
      ) : (
        <div className="flex gap-2 px-4 py-3 border-t border-slate-100">
          <button
            onClick={() => submitDecision("approved")}
            disabled={loading}
            className="flex items-center gap-1.5 bg-blue-600 text-white rounded-lg px-4 py-2 text-sm font-medium"
          >
            <Check size={14} />
            Approve
          </button>
          <button
            onClick={() => submitDecision("rejected")}
            disabled={loading}
            className="flex items-center gap-1.5 border border-slate-300 text-slate-700 rounded-lg px-4 py-2 text-sm font-medium"
          >
            <X size={14} />
            Reject
          </button>
          <button
            onClick={() => setShowRetry(true)}
            disabled={loading}
            className="text-sm text-slate-500 px-3 py-2"
          >
            Retry a stage…
          </button>
        </div>
      )}
    </div>
  );
}

function ReportPanel({ report, runId }) {
  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 bg-slate-50">
        <p className="text-sm font-medium text-slate-700">Final report</p>
        <div className="flex gap-3">
          <a
            href={`${API_BASE}/runs/${runId}/report/summary`}
            download
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-600 font-medium hover:underline"
          >
            Download summary
          </a>
          <a
            href={`${API_BASE}/runs/${runId}/report/mt799`}
            download
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-600 font-medium hover:underline"
          >
            Download MT799
          </a>
        </div>
      </div>
      <div className="px-4 py-3">
        <pre className="text-xs text-slate-600 whitespace-pre-wrap font-mono leading-relaxed">
          {report?.content || "Report content unavailable"}
        </pre>
      </div>
    </div>
  );
}

function RunPage() {
  const { runId } = useParams();
  const [runData, setRunData] = useState(null);
  const [hitlDone, setHitlDone] = useState(false);

  useEffect(() => {
    if (!runId) return;

    const poll = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/runs/${runId}`, { headers: apiHeaders() });
        const data = await res.json();
        setRunData(data);

        // stop polling once the run reaches a terminal state
        if (data.status === "done" || data.status === "rejected" || data.status === "blocked" || data.status === "error") {
          clearInterval(poll);
        }
      } catch (err) {
        console.log(err);
      }
    }, 2000);

    return () => clearInterval(poll);
  }, [runId]);

  const runStatus = runData?.status || "parser";
  const issues = sortBySeverity(runData?.issues || []);
  const showHitl = runStatus === "hitl" && !hitlDone;
  const showReport = (runStatus === "done" || runStatus === "rejected") && !!runData?.report;

  return (
    <div className="min-h-screen flex flex-col lg:flex-row">

      <div className="lg:w-[30%] bg-blue-600 px-5 py-8 flex flex-col">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-7 h-7 rounded-lg bg-white flex items-center justify-center text-blue-600 text-xs font-medium">
            DC
          </div>
          <span className="text-base font-medium text-white">Document Copilot</span>
        </div>
        <p className="text-xs text-blue-200 mb-7">
          Run #{runId?.slice(0, 6) || "—"} · {runData?.doc_count || 8} documents
        </p>

        <div className="flex flex-col gap-0.5">
          {STEPS.map((step, i) => {
            const status = getStepStatus(step.key, runStatus, !!runData?.report);
            const message = getStepMessage(step, status, runData);
            return (
              <div key={step.key}>
                <StepRow step={step} status={status} message={message} />
                {i < STEPS.length - 1 && (
                  <div
                    className="w-px h-2 ml-5"
                    style={{ background: status === "pending" ? "rgba(147,197,253,0.3)" : "#3B82F6" }}
                  />
                )}
              </div>
            );
          })}
        </div>

        <p className="text-xs text-blue-200 mt-auto pt-6">
          PDF documents only · up to 8 files per check
        </p>
      </div>

      <div className="flex-1 bg-white px-6 py-8 flex flex-col gap-4 overflow-y-auto">
        <div>
          <h2 className="text-base font-medium text-slate-700 mb-0.5">Run status</h2>
          <p className="text-sm text-slate-500">
            {runStatus === "hitl"
              ? "Review the issues found before the report is written."
              : runStatus === "done"
              ? "Run complete. Download the report below."
              : runStatus === "rejected"
              ? (runData?.report
                  ? "Run rejected at the checkpoint. Refusal notice ready below."
                  : "Run rejected at the checkpoint.")
              : runStatus === "blocked"
              ? "Run stopped — LC terms sheet incomplete."
              : runStatus === "error"
              ? "Something went wrong processing this run. Check the audit log or try uploading again."
              : "Results appear below as each agent completes."}
          </p>
        </div>

        {issues.length > 0 && (
          <div className="border border-slate-200 rounded-xl overflow-hidden">
            <div className="px-4 py-2.5 border-b border-slate-100 bg-slate-50">
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
                Issues found — {issues.length}
              </p>
            </div>
            {issues.map((issue, i) => (
              <IssueRow key={i} issue={issue} />
            ))}
          </div>
        )}

        {showHitl && (
          <HitlPanel
            issues={issues}
            runId={runId}
            recommendation={runData?.recommendation}
            recommendationSummary={runData?.recommendation_summary}
            onDecision={(d) => {
              // Only close the panel for a final decision. A "retry" sends the
              // run back into the pipeline, so leave it open to reappear once
              // the run reaches "hitl" again.
              if (d === "approved" || d === "rejected") {
                setHitlDone(true);
              }
              setRunData((prev) => ({ ...prev, hitl_decision: d }));
            }}
          />
        )}

        {!showHitl && !showReport && runStatus !== "done" && (
          <div className="border border-dashed border-slate-200 rounded-xl p-5 text-center opacity-60">
            <FileCheck size={22} className="text-slate-400 mx-auto mb-2" />
            <p className="text-sm text-slate-600">HITL checkpoint</p>
            <p className="text-xs text-slate-400 mt-0.5">Review panel appears once Agent 3 completes</p>
          </div>
        )}

        {!showReport && (
          <div className="border border-dashed border-slate-200 rounded-xl p-5 text-center opacity-50">
            <FileCheck size={22} className="text-slate-400 mx-auto mb-2" />
            <p className="text-sm text-slate-600">Final report</p>
            <p className="text-xs text-slate-400 mt-0.5">Appears here once you approve the checkpoint</p>
          </div>
        )}

        {showReport && <ReportPanel report={runData.report} runId={runId} />}
      </div>

    </div>
  );
}

export default RunPage;