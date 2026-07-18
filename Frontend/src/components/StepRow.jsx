function StepRow({ step, status, message }) {

  return (
    <div className={`flex gap-3 items-start px-3 py-2.5 rounded-lg ${status === "running" ? "bg-blue-700" : status === "done" ? "bg-blue-700" : ""}`}>
      <div className="mt-0.5 flex-shrink-0">
        {status === "done" && (
          <div className="w-[22px] h-[22px] rounded-full bg-white flex items-center justify-center">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M2 6l3 3 5-5" stroke="#2563EB" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
        )}
        {status === "running" && (
          <div className="w-[22px] h-[22px] rounded-full bg-blue-300 flex items-center justify-center">
            <div className="w-2 h-2 rounded-full bg-blue-600 animate-pulse" />
          </div>
        )}
        {status === "pending" && (
          <div className="w-[22px] h-[22px] rounded-full border border-blue-300 opacity-50" />
        )}
      </div>
      <div className={status === "pending" ? "opacity-50" : ""}>
        <p className="text-sm font-medium text-white">{step.label}</p>
        <p className="text-xs text-blue-200 mt-0.5">{message}</p>
      </div>
    </div>
  );
}

export default StepRow;