import { useState } from "react";
import { api, fmtDay } from "../../api";
import { Badge, Empty, ErrorBox, Spinner, useAsync, useToast } from "../../components";
import { PageHead, ReasonSheet, Tabs } from "../../components/adminui";

export default function Merchants() {
  const toast = useToast();
  const [tab, setTab] = useState("pending");
  const { data, loading, error, reload } = useAsync(() => api<any[]>("/admin/merchants" + (tab === "all" ? "" : `?status=${tab}`)), [tab]);
  const [rej, setRej] = useState<any>(null);

  const decide = async (id: number, decision: string, reason?: string) => {
    try { await api(`/admin/merchants/${id}/decision`, { body: { decision, reason } }); toast(decision === "approve" ? "Merchant approved" : "Merchant rejected"); setRej(null); reload(); }
    catch (e: any) { toast(e.message, "err"); }
  };

  return (
    <div className="stack">
      <PageHead title="Merchants" />
      <Tabs value={tab} onChange={setTab} options={["pending", "approved", "rejected", "all"]} />
      {loading ? <Spinner /> : error ? <ErrorBox error={error} retry={reload} /> : !data?.length ? <Empty icon="🏪">No {tab} merchants</Empty> :
        <div className="stats" style={{ gridTemplateColumns: "repeat(auto-fill,minmax(300px,1fr))" }}>{data.map((m) => (
          <div key={m.id} className="card stack-s">
            <div className="row between"><h3 style={{ margin: 0 }}>{m.name}</h3><Badge s={m.verification_status} /></div>
            <div className="small">{m.category} · {m.address}</div>
            <div className="small muted">Owner: {m.owner_name} ({m.owner_email}) · applied {fmtDay(m.created_at)}</div>
            {m.description && <div className="small">{m.description}</div>}
            <div className="small"><b>Documents:</b> {m.doc_note || "—"}</div>
            {m.reject_reason && <div className="alert err small">Rejected: {m.reject_reason}</div>}
            {m.verification_status !== "approved" && (
              <div className="row">
                <button className="btn sm" onClick={() => decide(m.id, "approve")}>Approve</button>
                {m.verification_status === "pending" && <button className="btn sm danger" onClick={() => setRej(m)}>Reject</button>}
              </div>)}
          </div>))}</div>}
      {rej && <ReasonSheet title={`Reject ${rej.name}`} onClose={() => setRej(null)} onSubmit={(r) => decide(rej.id, "reject", r)} />}
    </div>
  );
}
