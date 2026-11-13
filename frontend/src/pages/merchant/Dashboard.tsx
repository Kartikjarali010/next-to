import { Ic, Stars } from "../../icons";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtDay, money } from "../../api";
import { useAuth } from "../../auth";
import { Badge, Empty, ErrorBox, Spinner, useAsync, useToast } from "../../components";

function Verification() {
  const { user, refreshToken, reload } = useAuth();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const m = user?.merchant;
  const check = async () => {
    setBusy(true);
    const u = await refreshToken();
    await reload();
    setBusy(false);
    if (u?.role === "merchant") toast("Approved! You can now create deals.", "ok");
    else toast("Still under review.", "ok");
  };
  return (
    <div className="stack">
      <div className="card stack">
        <h2>{m?.name || "Your business"}</h2>
        <div className="row"><span className="muted">Verification</span><Badge s={m?.verification_status || "pending"} /></div>
        {m?.verification_status === "rejected"
          ? <div className="alert err"><b>Application rejected.</b><br />{m.reject_reason || "No reason given."}</div>
          : <div className="alert info"><Ic n="hourglass" size={14} /> Under review by NextTo admin. You can publish deals once approved.</div>}
        <button className="btn" onClick={check} disabled={busy}>{busy ? "Checking…" : "Check status"}</button>
      </div>
    </div>
  );
}

function Stats() {
  const s = useAsync(() => api<any>("/merchant/stats"));
  const r = useAsync(() => api<any[]>("/merchant/reviews"));
  if (s.loading) return <Spinner />;
  if (s.error || !s.data) return <ErrorBox error={s.error || "Failed"} retry={s.reload} />;
  const d = s.data;
  const max = Math.max(1, ...d.daily.map((x: any) => x.sales));
  return (
    <div className="stack">
      <div className="grid2">
        <div className="stat"><b>{d.vouchers_sold}</b><span>Vouchers sold</span></div>
        <div className="stat"><b>{money(d.revenue)}</b><span>Revenue</span></div>
        <div className="stat"><b>{d.redeemed}</b><span>Redeemed</span></div>
        <div className="stat"><b>{Math.round(d.redemption_rate * 100)}%</b><span>Redemption rate</span></div>
        <div className="stat"><b>{money(d.tips)}</b><span>Tips</span></div>
        <div className="stat"><b>{d.avg_rating ?? "–"} <Ic n="star" size={16} fill="currentColor" className="amber" /></b><span>{d.review_count} reviews</span></div>
      </div>
      <div className="card">
        <h3>Sales — last 7 days</h3>
        <div className="bars">{d.daily.map((x: any) => (
          <div key={x.day} style={{ height: `${(x.sales / max) * 100}%` }} title={`${x.sales} sales · ${money(x.revenue)}`}>
            <span>{x.day.slice(8)}</span>
          </div>))}</div>
      </div>
      <div className="grid2">
        <Link to="/merchant/deals" className="stat"><b>{d.active_deals}</b><span>Active deals</span></Link>
        <Link to="/merchant/deals" className="stat"><b>{d.pending_deals}</b><span>Awaiting approval</span></Link>
      </div>
      <div className="card stack-s">
        <h3>Recent reviews</h3>
        {r.loading ? <Spinner /> : !r.data?.length ? <Empty icon="star">No reviews yet</Empty> :
          r.data.slice(0, 4).map((x, i) => (
            <div key={i}><div className="row between"><b>{x.name}</b><span><Stars n={x.rating} /></span></div>
              <div className="small">{x.comment}</div><div className="small muted">{fmtDay(x.created_at)}</div></div>))}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  if (!user) return null;
  return user.role === "merchant" ? <Stats /> : <Verification />;
}
