import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, fmtDate, fmtDay, money } from "../../api";
import { useAuth } from "../../auth";
import { Badge, Empty, ErrorBox, Spinner, useAsync } from "../../components";

type Tab = "menu" | "profile" | "payouts" | "reviews" | "notifications";

function Section({ title, back, children }: { title: string; back: () => void; children: any }) {
  return <div className="stack"><div className="row"><button className="btn sm light" onClick={back}>← Back</button><h2 style={{ margin: 0 }}>{title}</h2></div>{children}</div>;
}

function Profile() {
  const { data, loading, error, reload } = useAsync(() => api<any>("/merchant/me"));
  if (loading) return <Spinner />;
  if (error || !data) return <ErrorBox error={error || "Failed"} retry={reload} />;
  return (
    <div className="card stack-s">
      <div className="row between"><h3>{data.name}</h3><Badge s={data.verification_status} /></div>
      <div className="small">{data.category} · {data.address}</div>
      <div className="small muted">{data.lat}, {data.lng}</div>
      {data.description && <div>{data.description}</div>}
      {data.doc_note && <div className="small muted">Docs: {data.doc_note}</div>}
    </div>
  );
}

function Payouts() {
  const { data, loading, error, reload } = useAsync(() => api<any[]>("/merchant/payouts"));
  if (loading) return <Spinner />;
  if (error) return <ErrorBox error={error} retry={reload} />;
  if (!data?.length) return <Empty icon="💸">No payouts yet</Empty>;
  return <>{data.map((p) => (
    <div key={p.id} className="card stack-s">
      <div className="row between"><b>{p.period}</b><Badge s={p.status} /></div>
      <div className="small">Gross {money(p.gross)} − fee {money(p.fee)}</div>
      <div className="price">Net {money(p.net)}</div>
    </div>))}</>;
}

function Reviews() {
  const { data, loading, error, reload } = useAsync(() => api<any[]>("/merchant/reviews"));
  if (loading) return <Spinner />;
  if (error) return <ErrorBox error={error} retry={reload} />;
  if (!data?.length) return <Empty icon="⭐">No reviews yet</Empty>;
  return <>{data.map((r, i) => (
    <div key={i} className="card stack-s">
      <div className="row between"><b>{r.name}</b><span>{"★".repeat(r.rating)}</span></div>
      <div>{r.comment}</div><div className="small muted">{fmtDay(r.created_at)}</div>
    </div>))}</>;
}

function Notifications() {
  const { data, loading, error, reload } = useAsync(async () => { const n = await api<any[]>("/notifications"); api("/notifications/read", { method: "POST", body: {} }).catch(() => {}); return n; });
  if (loading) return <Spinner />;
  if (error) return <ErrorBox error={error} retry={reload} />;
  if (!data?.length) return <Empty icon="🔔">No notifications</Empty>;
  return <>{data.map((n) => (
    <div key={n.id} className="card" style={n.read ? undefined : { borderLeft: "4px solid var(--brand)" }}>
      <div>{n.message}</div><div className="small muted">{fmtDate(n.created_at)}</div>
    </div>))}</>;
}

export default function More() {
  const [tab, setTab] = useState<Tab>("menu");
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const back = () => setTab("menu");
  if (tab === "profile") return <Section title="Business profile" back={back}><Profile /></Section>;
  if (tab === "payouts") return <Section title="Payouts" back={back}><Payouts /></Section>;
  if (tab === "reviews") return <Section title="Reviews" back={back}><Reviews /></Section>;
  if (tab === "notifications") return <Section title="Notifications" back={back}><Notifications /></Section>;
  const items: [Tab, string, string][] = [["profile", "🏪", "Business profile"], ["payouts", "💸", "Payouts"], ["reviews", "⭐", "Reviews"], ["notifications", "🔔", "Notifications"]];
  return (
    <div className="stack">
      <div className="card"><div className="bold">{user?.name}</div><div className="small muted">{user?.email}</div></div>
      {items.map(([t, ic, label]) => (
        <button key={t} className="card row" style={{ border: 0, textAlign: "left", cursor: "pointer", fontWeight: 600 }} onClick={() => setTab(t)}>
          <span style={{ fontSize: "1.4rem" }}>{ic}</span><span className="grow">{label}</span><span className="muted">›</span>
        </button>))}
      <button className="btn danger block" onClick={() => { logout(); nav("/merchant/login"); }}>Sign out</button>
    </div>
  );
}
