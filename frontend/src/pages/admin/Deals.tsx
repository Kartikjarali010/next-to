import { useState } from "react";
import { api, fmtDate, money } from "../../api";
import { Badge, Empty, ErrorBox, Spinner, useAsync, useToast } from "../../components";
import { PageHead, ReasonSheet, Tabs } from "../../components/adminui";

export default function Deals() {
  const toast = useToast();
  const [tab, setTab] = useState("pending");
  const { data, loading, error, reload } = useAsync(() => api<any[]>("/admin/deals" + (tab === "all" ? "" : `?status=${tab}`)), [tab]);
  const [rej, setRej] = useState<any>(null);

  const decide = async (id: number, decision: string, reason?: string) => {
    try { await api(`/admin/deals/${id}/decision`, { body: { decision, reason } }); toast(decision === "approve" ? "Deal is now live" : "Deal rejected"); setRej(null); reload(); }
    catch (e: any) { toast(e.message, "err"); }
  };

  return (
    <div className="stack">
      <PageHead title="Deals" />
      <Tabs value={tab} onChange={setTab} options={["pending", "active", "rejected", "ended", "draft", "all"]} />
      {loading ? <Spinner /> : error ? <ErrorBox error={error} retry={reload} /> : !data?.length ? <Empty icon="🏷️">No {tab} deals</Empty> :
        <div className="table-wrap"><table className="table">
          <thead><tr><th>Deal</th><th>Merchant</th><th>Price</th><th>Stock</th><th>Sale window</th><th>Status</th><th /></tr></thead>
          <tbody>{data.map((d) => (
            <tr key={d.id}>
              <td><b>{d.title}</b><div className="small muted">{d.type} · {d.category}</div><div className="small">{d.description}</div>
                {d.reject_reason && <div className="small" style={{ color: "var(--err)" }}>Rejected: {d.reject_reason}</div>}</td>
              <td>{d.merchant_name}</td>
              <td>{money(d.price)} <div className="small strike">{money(d.original_price)}</div></td>
              <td>{d.stock_remaining}/{d.stock_total}</td>
              <td className="small">{fmtDate(d.starts_at)}<br />→ {fmtDate(d.ends_at)}</td>
              <td><Badge s={d.status} /></td>
              <td>{d.status === "pending" && <div className="row"><button className="btn sm" onClick={() => decide(d.id, "approve")}>Approve</button><button className="btn sm danger" onClick={() => setRej(d)}>Reject</button></div>}</td>
            </tr>))}</tbody>
        </table></div>}
      {rej && <ReasonSheet title={`Reject “${rej.title}”`} onClose={() => setRej(null)} onSubmit={(r) => decide(rej.id, "reject", r)} />}
    </div>
  );
}
