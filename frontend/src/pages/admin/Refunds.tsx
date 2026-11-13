import { useState } from "react";
import { api, fmtDate, money } from "../../api";
import { Badge, Empty, ErrorBox, Spinner, useAsync, useToast } from "../../components";
import { PageHead, ReasonSheet, Tabs } from "../../components/adminui";

export default function Refunds() {
  const toast = useToast();
  const [tab, setTab] = useState("requested");
  const { data, loading, error, reload } = useAsync(() => api<any[]>("/admin/refunds" + (tab === "all" ? "" : `?status=${tab}`)), [tab]);
  const [rej, setRej] = useState<any>(null);
  const [note, setNote] = useState("");

  const decide = async (id: number, decision: string, reason?: string) => {
    setNote("");
    try {
      await api(`/admin/refunds/${id}/decision`, { body: { decision, reason } });
      toast(decision === "approve" ? "Refund processed" : "Refund rejected"); setRej(null); reload();
    } catch (e: any) {
      if (e.status === 502) { setNote(e.message); toast("Provider unavailable — refund stays approved; retry later", "err"); reload(); }
      else toast(e.message, "err");
    }
  };

  return (
    <div className="stack">
      <PageHead title="Refunds" />
      <Tabs value={tab} onChange={setTab} options={["requested", "approved", "processed", "rejected", "all"]} />
      {note && <div className="alert warn"><b>Payment provider unavailable.</b> {note}</div>}
      {loading ? <Spinner /> : error ? <ErrorBox error={error} retry={reload} /> : !data?.length ? <Empty icon="↩️">No {tab} refunds</Empty> :
        <div className="table-wrap"><table className="table">
          <thead><tr><th>#</th><th>Customer</th><th>Deal</th><th>Amount</th><th>Reason</th><th>Requested</th><th>Status</th><th /></tr></thead>
          <tbody>{data.map((r) => (
            <tr key={r.id}>
              <td>{r.id}</td><td>{r.consumer_name}</td>
              <td>{r.deal_title}<div className="small muted">{r.merchant_name}</div></td>
              <td>{money(r.amount)}</td>
              <td className="small">{r.reason || "—"}{r.decision_reason && <div className="muted">Decision: {r.decision_reason}</div>}</td>
              <td className="small">{fmtDate(r.created_at)}</td>
              <td><Badge s={r.status} /></td>
              <td>{(r.status === "requested" || r.status === "approved") && (
                <div className="row">
                  <button className="btn sm" onClick={() => decide(r.id, "approve")}>{r.status === "approved" ? "Retry refund" : "Approve"}</button>
                  {r.status === "requested" && <button className="btn sm danger" onClick={() => setRej(r)}>Reject</button>}
                </div>)}</td>
            </tr>))}</tbody>
        </table></div>}
      {rej && <ReasonSheet title={`Reject refund #${rej.id}`} onClose={() => setRej(null)} onSubmit={(r) => decide(rej.id, "reject", r)} />}
    </div>
  );
}
