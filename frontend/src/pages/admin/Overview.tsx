import { useState } from "react";
import { Link } from "react-router-dom";
import { api, money } from "../../api";
import { ErrorBox, Spinner, useAsync, useToast } from "../../components";
import { PageHead } from "../../components/adminui";

export default function Overview() {
  const toast = useToast();
  const { data: s, loading, error, reload } = useAsync(() => api<any>("/admin/stats"));
  const [out, setOut] = useState<string>("");
  const [busy, setBusy] = useState(false);

  const job = async (name: "expire" | "reconcile") => {
    setBusy(true);
    try {
      const r = await api<any>(`/admin/jobs/${name}`, { method: "POST", body: name === "reconcile" ? { older_than_minutes: 0 } : {} });
      setOut(`${name}: ${JSON.stringify(r)}`); toast(`${name} job finished`); reload();
    } catch (e: any) { toast(e.message, "err"); }
    setBusy(false);
  };

  if (loading) return <Spinner />;
  if (error || !s) return <ErrorBox error={error || "Failed"} retry={reload} />;
  const tiles: [string, string | number][] = [
    ["Consumers", s.users], ["Approved merchants", s.merchants], ["Active deals", s.active_deals], ["Vouchers sold", s.vouchers_sold],
    ["GMV", money(s.gmv)], ["Redemption rate", Math.round(s.redemption_rate * 100) + "%"], ["Platform fee earned", money(s.platform_fee_earned)],
  ];
  const queues: [string, number, string][] = [
    ["Merchants pending", s.pending_merchants, "/admin/merchants"], ["Deals pending", s.pending_deals, "/admin/deals"],
    ["Refunds open", s.pending_refunds, "/admin/refunds"], ["Payouts pending", s.pending_payouts, "/admin/payouts"],
  ];
  return (
    <div className="stack">
      <PageHead title="Overview"><button className="btn sm light" onClick={reload}>↻ Refresh</button></PageHead>
      <div className="stats">{tiles.map(([l, v]) => <div key={l} className="stat"><b>{v}</b><span>{l}</span></div>)}</div>
      <h2>Needs attention</h2>
      <div className="stats">{queues.map(([l, n, to]) => (
        <Link key={l} to={to} className="stat" style={n > 0 ? { borderLeft: "4px solid var(--accent)" } : undefined}><b>{n}</b><span>{l}</span></Link>))}</div>
      <div className="card stack">
        <h2>Scheduled jobs</h2>
        <div className="small muted">These also run automatically in the background. <b>Expire</b> releases unpaid reservations and ends stale deals/vouchers. <b>Reconcile</b> asks the payment provider about pending orders, recovering payments whose webhook was lost.</div>
        <div className="row wrap">
          <button className="btn light" disabled={busy} onClick={() => job("expire")}>Run expiry</button>
          <button className="btn" disabled={busy} onClick={() => job("reconcile")}>Reconcile payments now</button>
        </div>
        {out && <pre className="alert info small" style={{ margin: 0, whiteSpace: "pre-wrap" }}>{out}</pre>}
      </div>
    </div>
  );
}
