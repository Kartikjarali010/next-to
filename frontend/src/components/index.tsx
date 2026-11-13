import { Ic } from "../icons";
import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";

/* ---------- toast ---------- */
const T = createContext<(msg: string, kind?: "ok" | "err") => void>(() => {});
export const useToast = () => useContext(T);
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<{ id: number; msg: string; kind: string }[]>([]);
  const push = useCallback((msg: string, kind: "ok" | "err" = "ok") => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, msg, kind }]);
    setTimeout(() => setItems((x) => x.filter((i) => i.id !== id)), 3200);
  }, []);
  return (
    <T.Provider value={push}>
      {children}
      <div className="toast-wrap">{items.map((i) => <div key={i.id} className={"toast " + i.kind}>{i.msg}</div>)}</div>
    </T.Provider>
  );
}

/* ---------- small pieces ---------- */
export const Spinner = () => <div className="spinner" aria-label="Loading" />;
export const Empty = ({ icon = "inbox", children }: { icon?: string; children: ReactNode }) => (
  <div className="empty"><div className="empty-ic"><Ic n={icon} size={40} /></div>{children}</div>
);
export const ErrorBox = ({ error, retry }: { error: string; retry?: () => void }) => (
  <div className="alert err">{error} {retry && <button className="btn sm light" onClick={retry}>Retry</button>}</div>
);

const TONE: Record<string, string> = {
  active: "ok", approved: "ok", paid: "ok", redeemed: "info", processed: "ok", released: "ok", confirmed: "ok", completed: "info",
  pending: "warn", refund_pending: "warn", requested: "warn", draft: "", expired: "", ended: "", refunded: "info",
  rejected: "err", failed: "err", refund_required: "err", cancelled: "err", merchant_applicant: "warn",
};
export const Badge = ({ s }: { s: string }) => <span className={"badge " + (TONE[s] ?? "")}>{s.replace(/_/g, " ")}</span>;

export function Sheet({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  return (
    <div className="sheet-bg" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>{children}</div>
    </div>
  );
}

/* ---------- data hook ---------- */
export function useAsync<T>(fn: () => Promise<T>, deps: any[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);
  const run = useCallback(() => {
    const my = ++seq.current;
    setLoading(true); setError(null);
    fn().then((d) => { if (my === seq.current) { setData(d); setLoading(false); } })
        .catch((e) => { if (my === seq.current) { setError(e.message || "Something went wrong"); setLoading(false); } });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => { run(); }, [run]);
  return { data, error, loading, reload: run, setData };
}

export const CATEGORY_ICON: Record<string, string> = { food: "food", cafe: "cafe", bakery: "bakery", salon: "salon", spa: "spa", fitness: "fitness", retail: "retail", entertainment: "entertainment", services: "services" };
export const CATEGORY_BG: Record<string, string> = { food: "#fde68a", cafe: "#fed7aa", bakery: "#fbcfe8", salon: "#ddd6fe", spa: "#bae6fd", fitness: "#bbf7d0", retail: "#fecaca", entertainment: "#c7d2fe", services: "#e2e8f0" };
