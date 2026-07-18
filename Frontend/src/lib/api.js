export const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const API_KEY = import.meta.env.VITE_API_KEY;

// Merge in the shared-secret header the backend expects (api/auth.py) when
// one is configured. Not used for the report download links, which the
// backend intentionally leaves unauthenticated (an <a href> can't set custom
// headers) and instead relies on the run_id being an unguessable UUID.
export function apiHeaders(extra = {}) {
  return API_KEY ? { ...extra, "X-API-Key": API_KEY } : extra;
}
