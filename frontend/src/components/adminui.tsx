import { ReactNode, useState } from "react";
import { Sheet } from "./index";

export function Tabs({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: string[] }) {
  return <div className="chips">{options.map((o) => <button key={o} className={"chip " + (value === o ? "on" : "")} onClick={() => onChange(o)}>{o}</button>)}</div>;
}

/** Sheet asking for a mandatory reason before a rejection. */
export function ReasonSheet({ title, onClose, onSubmit }: { title: string; onClose: () => void; onSubmit: (reason: string) => Promise<void> }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <Sheet onClose={onClose}>
      <div className="stack">
        <h2>{title}</h2>
        <div className="field"><label>Reason (required)</label><textarea className="input" value={reason} onChange={(e) => setReason(e.target.value)} autoFocus /></div>
        <div className="row">
          <button className="btn light grow" onClick={onClose}>Cancel</button>
          <button className="btn danger grow" disabled={busy || !reason.trim()} onClick={async () => { setBusy(true); await onSubmit(reason.trim()); setBusy(false); }}>Reject</button>
        </div>
      </div>
    </Sheet>
  );
}

export const PageHead = ({ title, children }: { title: string; children?: ReactNode }) => (
  <div className="row between wrap" style={{ marginBottom: 12 }}><h1 style={{ margin: 0 }}>{title}</h1><div className="row wrap">{children}</div></div>
);
