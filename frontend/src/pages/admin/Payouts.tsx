import { useState } from "react";
import { api, fmtDate, money } from "../../api";
import { Badge, Empty, ErrorBox, Spinner, useAsync, useToast } from "../../components";
import { PageHead } from "../../components/adminui";

export default function Payouts() {
  const toast = useToast();
  const { data, loading, error, reload } = useAsync(() => api<any[]>("/admin/payouts"));
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    try { const r = await api<{ created: number[] }>("/admin/payouts/run", { body: {} }); toast(r.created.length ? `${r.created.length} payout(s) created` : "Nothing new to settle"); reload(); }
    catch (e: any) { toast(e.message, "err"); }
    setBusy(false);
  };
  const release = async (id: number) => {
    try { await api(`/admin/payouts/${id}/release`, { method: "POST", body: {} }); toast("Payout released"); reload(); }
    catch (e: any) { toast(e.message, "err"); }
  };

  return (
    <div className="stack">
      <PageHead title="Payouts"><button className="btn" disabled={busy} onClick={run}>{busy ? "Settling…" : "Run settlement"}</button></PageHead>
      <div className="alert info small">Settlement covers redeemed vouchers (refunded ones never count) plus tips, less the platform fee. Release is manual in this version.</div>
      {loading ? <Spinner /> : error ? <ErrorBox error={error} retry={reload} /> : !data?.length ? <Empty icon="💸">No payouts yet. Redeem some vouchers, then run settlement.</Empty> :
        <div className="table-wrap"><table className="table">
          <thead><tr><th>#</th><th>Merchant</th><th>Period</th><th>Gross</th><th>Fee</th><th>Net</th><th>Status</th><th /></tr></thead>
          <tbody>{data.map((p) => (
            <tr key={p.id}>
              <td>{p.id}</td><td>{p.merchant_name}</td><td>{p.period}</td>
              <td>{money(p.gross)}</td><td>{money(p.fee)}</td><td><b>{money(p.net)}</b></td>
              <td><Badge s={p.status} />{p.released_at && <div className="small muted">{fmtDate(p.released_at)}</div>}</td>
              <td>{p.status === "pending" && <button className="btn sm" onClick={() => release(p.id)}>Release</button>}</td>
            </tr>))}</tbody>
        </table></div>}
    </div>
  );
}
