import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api, fmtDate, money } from "../../api";
import { useAuth } from "../../auth";
import { Badge, Empty, Spinner, useAsync } from "../../components";

export default function Profile() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const notes = useAsync(() => api<any[]>("/notifications"), []);
  const refunds = useAsync(() => api<any[]>("/refunds"), []);
  const orders = useAsync(() => api<any[]>("/orders"), []);

  useEffect(() => { // mark read once they have been displayed
    if (notes.data?.some((n) => !n.read)) { const t = setTimeout(() => api("/notifications/read", { method: "POST", body: {} }).catch(() => {}), 2500); return () => clearTimeout(t); }
  }, [notes.data]);

  return (
    <div className="stack">
      <div className="card row">
        <div style={{ fontSize: "2.4rem" }}>👤</div>
        <div className="grow"><b>{user?.name}</b><div className="small muted">{user?.email}</div></div>
        <span className="badge brand">⭐ {user?.points ?? 0}</span>
      </div>

      <h3>🔔 Notifications</h3>
      {notes.loading ? <Spinner /> : !notes.data?.length ? <Empty icon="🔔">No notifications yet.</Empty> :
        notes.data.map((n) => (
          <div key={n.id} className="card flat" style={n.read ? undefined : { borderLeft: "4px solid var(--brand)" }}>
            <div className="small">{n.message}</div><div className="small muted">{fmtDate(n.created_at)}</div></div>))}

      <h3>↩️ My refunds</h3>
      {refunds.loading ? <Spinner /> : !refunds.data?.length ? <div className="small muted">No refund requests.</div> :
        refunds.data.map((r) => (
          <div key={r.id} className="card flat stack-s"><div className="row between"><b className="small">Refund #{r.id}</b><Badge s={r.status} /></div>
            {r.reason && <div className="small muted">“{r.reason}”</div>}
            {r.decision_reason && <div className="small">Admin: {r.decision_reason}</div>}</div>))}

      <h3>🧾 Order history</h3>
      {orders.loading ? <Spinner /> : !orders.data?.length ? <div className="small muted">No orders yet.</div> :
        orders.data.map((o) => (
          <div key={o.id} className="card flat row between"
            style={o.voucher ? { cursor: "pointer" } : undefined} onClick={() => o.voucher && nav(`/voucher/${o.voucher.id}`)}>
            <div><div className="bold small">{o.kind === "tip" ? "Tip" : o.deal_title}</div><div className="small muted">{fmtDate(o.created_at)}</div></div>
            <div className="right"><div className="bold">{money(o.amount)}</div><Badge s={o.status} /></div>
          </div>))}

      <button className="btn light block" onClick={() => { logout(); nav("/login"); }}>Sign out</button>
    </div>
  );
}
