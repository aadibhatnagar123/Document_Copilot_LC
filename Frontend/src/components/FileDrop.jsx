import { useRef, useState } from "react";

function FileDrop({ label, hint, multiple, Icon, onAdd }) {
  const inputRef = useRef();
  const [over, setOver] = useState(false);

  function handleFiles(fileList) {
    const files = Array.from(fileList).filter((f) => f.type === "application/pdf");
    if (files.length > 0) {
      onAdd(files);
    }
  }

  return (
    <div>
      <p className="text-sm font-medium text-slate-700 mb-2">{label}</p>
      <div
        onClick={() => inputRef.current.click()}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          handleFiles(e.dataTransfer.files);
        }}
        className={
          "border-2 border-dashed rounded-xl p-5 text-center cursor-pointer " +
          (over ? "border-blue-600 bg-blue-50" : "border-slate-300")
        }
      >
        <div className="w-10 h-10 rounded-lg bg-blue-100 inline-flex items-center justify-center mb-2.5">
          <Icon size={20} className="text-blue-600" />
        </div>
        <p className="text-sm text-slate-700 mb-2.5">
          Drop {multiple ? "up to 7 documents" : "the term sheet"} here or browse
        </p>
        <p className="text-xs text-slate-500 mb-3">{hint}</p>
        <span className="inline-block bg-blue-600 text-white rounded-lg px-4 py-2 text-sm font-medium">
          Browse files
        </span>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        multiple={multiple}
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
    </div>
  );
}

export default FileDrop;