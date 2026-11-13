import { useState } from "react";
import { api, fmtDate } from "../../api";
import { ErrorBox, Spinner, useAsync } from "../../components";
import { PageHead } from "../../components/adminui";

const ENTITIES = ["", "order", "voucher", "refund", "deal", "merchant", "payout", "booking", "review", "user", "payment"];

function Json({ v }: { v: string | null }) {
  const [open, setOpen] = useState(false);
  if (!v) return <span className="muted">—</span>;
  let pretty = v;
  try { pretty = JSON.stringify(JSON.parse(v), null, open ? 2 : 0); } catch { /* keep raw */ }
  const long = pretty.length > 60;
  return (
    <span className="small" style={{ fontFamily: "ui-monospace,Menlo,monospace", cursor: long ? "pointer" : undefined }} onClick={() => long && setOpen(!open)}>
      <span style={{ whiteSpace: open ? "pre-wrap" : "nowrap" }}>{open || !long ? pretty : pretty.slice(0, 60) + "… ▸"}</span>
    </span>
  );
}

export default function Audit() {
  const [entity, setEntity] = useState("");
  const { data, loading, error, reload } = useAsync(() => api<any[]>(`/admin/audit?limit=200${entity ? `&entity=${entity}` : ""}`), [entity]);
  return (
    <div className="stack">
      <PageHead title="Audit log">
        <select className="input" style={{ width: "auto" }} value={entity} onChange={(e) => setEntity(e.target.value)}>
          {ENTITIES.map((e) => <option key={e} value={e}>{e || "all entities"}</option>)}
        </select>
        <button className="btn sm light" onClick={reload}>↻</button>
      </PageHead>
      <div className="small muted">Append-only record of every administrative and financial state change. Click a long value to expand.</div>
      {loading ? <Spinner /> : error ? <ErrorBox error={error} retry={reload} /> :
        <div className="table-wrap"><table className="table">
          <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Entity</th><th>Before</th><th>After</th></tr></thead>
          <tbody>{data?.map((a) => (
            <tr key={a.id}>
              <td className="small" style={{ whiteSpace: "nowrap" }}>{fmtDate(a.created_at)}</td>
              <td>{a.actor}</td><td><b>{a.action}</b></td><td>{a.entity}{a.entity_id ? ` #${a.entity_id}` : ""}</td>
              <td><Json v={a.before} /></td><td><Json v={a.after} /></td>
            </tr>))}
            {!data?.length && <tr><td colSpan={6} className="muted center">No entries</td></tr>}</tbody>
        </table></div>}
    </div>
  );
}
