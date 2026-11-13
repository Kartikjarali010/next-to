import { Ic, Stars } from "../../icons";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, fmtDate, fmtDay, money } from "../../api";
import { useAuth } from "../../auth";
import { Badge, Empty, ErrorBox, Spinner, useAsync, useToast } from "../../components";
import { PhotoPicker } from "../../images";

type Tab = "menu" | "profile" | "payouts" | "reviews" | "notifications";

function Section({ title, back, children }: { title: string; back: () => void; children: any }) {
  return <div className="stack"><div className="row"><button className="btn sm light" onClick={back}><Ic n="back" size={14} /> Back</button><h2 style={{ margin: 0 }}>{title}</h2></div>{children}</div>;
}

function Profile() {
  const { data, loading, error, reload } = useAsync(() => api<any>("/merchant/me"));
  const toast = useToast();
  const [f, setF] = useState<{ description: string; hours: string; image_url: string } | null>(null);
  const [busy, setBusy] = useState(false);
  if (loading) return <Spinner />;
  if (error || !data) return <ErrorBox error={error || "Failed"} retry={reload} />;
  const form = f ?? { description: data.description || "", hours: data.hours || "", image_url: data.image_url || "" };
  const approved = data.verification_status === "approved";
  const save = async () => {
    setBusy(true);
    try { await api("/merchant/profile", { method: "PUT", body: { ...form, image_url: form.image_url || null } }); toast("Shop profile saved"); reload(); }
    catch (e: any) { toast(e.message, "err"); }
    setBusy(false);
  };
  return (
    <div className="stack">
      <div className="card stack-s">
        <div className="row between"><h3>{data.name}</h3><Badge s={data.verification_status} /></div>
        <div className="small">{data.category} · {data.address}</div>
        <div className="small muted">{data.lat}, {data.lng}</div>
        {data.doc_note && <div className="small muted">Docs: {data.doc_note}</div>}
      </div>
      {approved && (
        <div className="card stack">
          <h3>Public shop page</h3>
          <div className="small muted">This is what shoppers see on your shop profile.</div>
          <div className="field"><label>About your shop</label><textarea className="input" maxLength={600} value={form.description} onChange={(e) => setF({ ...form, description: e.target.value })} /></div>
          <div className="field"><label>Opening hours</label><input className="input" maxLength={120} placeholder="e.g. Mon-Sun, 9:00 am - 9:00 pm" value={form.hours} onChange={(e) => setF({ ...form, hours: e.target.value })} /></div>
          <div className="field"><label>Cover photo</label><PhotoPicker value={form.image_url} category={data.category} onChange={(v) => setF({ ...form, image_url: v })} /></div>
          <div className="row wrap">
            <button className="btn" disabled={busy} onClick={save}>{busy ? "Saving…" : "Save shop page"}</button>
            <a className="btn ghost" href={`/shop/${data.id}`} target="_blank" rel="noreferrer">Preview as shopper</a>
          </div>
        </div>
      )}
    </div>
  );
}

function Payouts() {
  const { data, loading, error, reload } = useAsync(() => api<any[]>("/merchant/payouts"));
  if (loading) return <Spinner />;
  if (error) return <ErrorBox error={error} retry={reload} />;
  if (!data?.length) return <Empty icon="payout">No payouts yet</Empty>;
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
  if (!data?.length) return <Empty icon="star">No reviews yet</Empty>;
  return <>{data.map((r, i) => (
    <div key={i} className="card stack-s">
      <div className="row between"><b>{r.name}</b><span><Stars n={r.rating} /></span></div>
      <div>{r.comment}</div><div className="small muted">{fmtDay(r.created_at)}</div>
    </div>))}</>;
}

function Notifications() {
  const { data, loading, error, reload } = useAsync(async () => { const n = await api<any[]>("/notifications"); api("/notifications/read", { method: "POST", body: {} }).catch(() => {}); return n; });
  if (loading) return <Spinner />;
  if (error) return <ErrorBox error={error} retry={reload} />;
  if (!data?.length) return <Empty icon="bell">No notifications</Empty>;
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
  const items: [Tab, string, string][] = [["profile", "store", "Business profile"], ["payouts", "payout", "Payouts"], ["reviews", "star", "Reviews"], ["notifications", "bell", "Notifications"]];
  return (
    <div className="stack">
      <div className="card"><div className="bold">{user?.name}</div><div className="small muted">{user?.email}</div></div>
      {items.map(([t, ic, label]) => (
        <button key={t} className="card row" style={{ border: 0, textAlign: "left", cursor: "pointer", fontWeight: 600 }} onClick={() => setTab(t)}>
          <Ic n={ic} size={22} /><span className="grow">{label}</span><span className="muted"><Ic n="next" size={16} /></span>
        </button>))}
      <button className="btn danger block" onClick={() => { logout(); nav("/merchant/login"); }}>Sign out</button>
    </div>
  );
}
