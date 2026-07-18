import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileText, Files, ListChecks, GitCompare, FileCheck, X } from "lucide-react";
import FileDrop from "../components/FileDrop";
import { API_BASE, apiHeaders } from "../lib/api";

const steps = [
  { icon: FileText, title: "Parse", desc: "Extract fields from every document" },
  { icon: ListChecks, title: "Check", desc: "Completeness and dates" },
  { icon: GitCompare, title: "Compare", desc: "Cross-check against the LC terms" },
  { icon: FileCheck, title: "Report", desc: "Discrepancy notice after your approval" },
];

function UploadPage() {
  const navigate = useNavigate();
  const [termSheet, setTermSheet] = useState(null);
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(false);

  function addDocs(files) {
    const room = 7 - docs.length;
    setDocs([...docs, ...files.slice(0, room)]);
  }

  function removeDoc(i) {
    const copy = [...docs];
    copy.splice(i, 1);
    setDocs(copy);
  }

  async function runCheck() {
    if (!termSheet || docs.length === 0) {
      alert("Please add the term sheet and at least one document");
      return;
    }
    setLoading(true);

    const form = new FormData();
    form.append("term_sheet", termSheet);
    docs.forEach((d) => form.append("documents", d));

    try {
      const res = await fetch(`${API_BASE}/upload`, {
        method: "POST",
        headers: apiHeaders(),
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Upload failed (${res.status})`);
      }
      const data = await res.json();
      navigate("/run/" + data.run_id);
    } catch (err) {
      console.log(err);
      alert(err.message || "Something went wrong, try again");
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col lg:flex-row">

      <div className="lg:w-[30%] bg-blue-600 px-7 py-8 flex flex-col">
        <div className="flex items-center gap-2.5 mb-10">
          <div className="w-8 h-8 rounded-lg bg-white flex items-center justify-center text-blue-600 text-sm font-medium">
            DC
          </div>
          <span className="text-lg font-medium text-white">Document Copilot</span>
        </div>

        <h1 className="text-2xl font-medium text-white mb-3 leading-snug">
          Check Letter of Credit documents in minutes
        </h1>
        <p className="text-sm text-blue-200 mb-9 leading-relaxed">
          Upload your term sheet and supporting documents. Each one is parsed,
          checked, and compared against the LC before a report is written.
        </p>

        <div className="flex flex-col gap-5">
          {steps.map((s) => (
            <div key={s.title} className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-blue-700 flex items-center justify-center shrink-0">
                <s.icon size={17} className="text-white" />
              </div>
              <div>
                <p className="text-sm text-white">{s.title}</p>
                <p className="text-xs text-blue-200 mt-0.5">{s.desc}</p>
              </div>
            </div>
          ))}
        </div>

        <p className="text-xs text-blue-200 mt-auto pt-8">
          PDF documents only · up to 8 files per check
        </p>
      </div>

      <div className="flex-1 bg-white px-7 py-8 flex flex-col">
        <h2 className="text-lg font-medium text-slate-700 mb-1">Upload documents</h2>
        <p className="text-sm text-slate-500 mb-6">
          Start with the term sheet, then add the supporting files.
        </p>

        <div className="mb-6">
          {termSheet ? (
            <div>
              <p className="text-sm font-medium text-slate-700 mb-2">LC term sheet</p>
              <div className="flex items-center justify-between border border-slate-200 rounded-xl px-3 py-3">
                <div className="flex items-center gap-2">
                  <FileText size={16} className="text-blue-600" />
                  <span className="text-sm text-slate-700">{termSheet.name}</span>
                </div>
                <button onClick={() => setTermSheet(null)}>
                  <X size={15} className="text-slate-500" />
                </button>
              </div>
            </div>
          ) : (
            <FileDrop
              label="LC term sheet"
              hint="One file · PDF only"
              multiple={false}
              Icon={FileText}
              onAdd={(files) => setTermSheet(files[0])}
            />
          )}
        </div>

        <div>
          <FileDrop
            label="Supporting documents"
            hint="Invoice, B/L, packing list and others · PDF only"
            multiple={true}
            Icon={Files}
            onAdd={addDocs}
          />
          {docs.map((d, i) => (
            <div key={i} className="flex items-center justify-between border border-slate-200 rounded-xl px-3 py-3 mt-2">
              <div className="flex items-center gap-2">
                <FileText size={16} className="text-blue-600" />
                <span className="text-sm text-slate-700">{d.name}</span>
              </div>
              <button onClick={() => removeDoc(i)}>
                <X size={15} className="text-slate-500" />
              </button>
            </div>
          ))}
        </div>

        <div className="flex items-center justify-between mt-auto pt-6">
          <span className="text-sm text-slate-500">{docs.length} of 7 documents added</span>
          <button
            onClick={runCheck}
            disabled={loading}
            className="bg-blue-600 text-white rounded-xl px-6 py-3 text-sm font-medium"
          >
            {loading ? "Uploading..." : "Run check"}
          </button>
        </div>
      </div>

    </div>
  );
}

export default UploadPage;