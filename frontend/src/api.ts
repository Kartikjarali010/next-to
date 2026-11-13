export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}
const KEY = "nextto_token";
export const getToken = () => { try { return localStorage.getItem(KEY); } catch { return null; } };
export const setToken = (t: string | null) => { try { t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY); } catch {} };

export async function api<T = any>(path: string, opts: { method?: string; body?: any; headers?: Record<string, string> } = {}): Promise<T> {
  const h: Record<string, string> = { ...(opts.headers || {}) };
  const t = getToken();
  if (t) h["Authorization"] = "Bearer " + t;
  if (opts.body !== undefined) h["Content-Type"] = "application/json";
  let res: Response;
  try {
    res = await fetch("/api" + path, { method: opts.method || (opts.body !== undefined ? "POST" : "GET"), headers: h, body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined });
  } catch {
    throw new ApiError(0, "network", "Cannot reach the server. Is the backend running?");
  }
  const text = await res.text();
  let data: any = null;
  try { data = text ? JSON.parse(text) : null; } catch { /* non-json */ }
  if (!res.ok) throw new ApiError(res.status, data?.error?.code || "error", data?.error?.message || data?.detail || res.statusText);
  return data as T;
}

/** random idempotency key (one per purchase attempt) */
export const newKey = () => "k-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);

export const money = (n: number) => "₹" + (Math.round(n * 100) / 100).toLocaleString("en-IN", { maximumFractionDigits: 2 });
export const fmtDate = (iso: string) => new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
export const fmtDay = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
export const km = (m: number) => (m < 1000 ? `${m} m` : `${(m / 1000).toFixed(1)} km`);
export function timeLeft(iso: string) {
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return "ended";
  const h = Math.floor(ms / 3600000), d = Math.floor(h / 24);
  return d >= 1 ? `${d}d ${h % 24}h left` : h >= 1 ? `${h}h ${Math.floor((ms % 3600000) / 60000)}m left` : `${Math.max(1, Math.floor(ms / 60000))}m left`;
}
