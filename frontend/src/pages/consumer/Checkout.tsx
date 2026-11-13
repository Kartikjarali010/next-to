import { Ic } from "../../icons";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, money, newKey } from "../../api";
import { useAuth } from "../../auth";
import { Badge, ErrorBox, Spinner, useAsync, useToast } from "../../components";
import PayOrder from "./PayOrder";

export default function Checkout() {
  const { id } = useParams();
  const [sp] = useSearchParams();
  const nav = useNavigate();
  const toast = useToast();
  const { reload } = useAuth();
  const key = useRef(newKey()); // ONE idempotency key per checkout screen: retries / double taps reuse the same order
  const resumeId = sp.get("order");
  const [order, setOrder] = useState<any>(null);
  const [points, setPoints] = useState(0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const deal = useAsync(() => api<any>(`/deals/${id}`), [id]);
  const rewards = useAsync(() => api<any>("/rewards"), []);
  useEffect(() => { if (resumeId) api(`/orders/${resumeId}`).then(setOrder).catch((e) => setErr(e.message)); }, [resumeId]);
  useEffect(() => { if (order?.status === "paid") reload(); }, [order?.status, reload]);

  if (deal.loading || rewards.loading) return <Spinner />;
  if (deal.error) return <ErrorBox error={deal.error} retry={deal.reload} />;
  const d = deal.data;
  const balance = rewards.data?.balance ?? 0;
  const maxPts = Math.max(0, Math.min(Math.floor(d.price * 0.5), balance));
  const payable = d.price - points;

  const place = async () => {
    if (busy) return;
    setBusy(true); setErr("");
    try { setOrder(await api("/orders", { body: { deal_id: d.id, use_points: points }, headers: { "Idempotency-Key": key.current } })); }
    catch (e: any) {
      setErr(e.message);
      if (e.code === "deal_unavailable") toast("This deal just sold out", "err");
    }
    setBusy(false);
  };

  // ---- success
  if (order?.status === "paid") return (
    <div className="stack center">
      <div className="hero"><div style={{ display: "flex", justifyContent: "center" }}><Ic n="party" size={48} /></div><h1 style={{ color: "#fff" }}>Payment confirmed</h1><div>{order.deal_title}</div></div>
      <div className="card stack-s"><div className="muted small">Your voucher is ready</div>
        <div className="voucher-code">{order.voucher?.code}</div>
        {order.voucher && <button className="btn block" onClick={() => nav(`/voucher/${order.voucher.id}`)}>Open voucher &amp; QR</button>}
        <Link to="/wallet" className="small">Go to wallet</Link></div>
    </div>
  );

  // ---- pending
  if (order?.status === "pending") return (
    <div className="stack"><h1>Complete payment</h1>
      <div className="small muted">{d.title} · {d.merchant_name}</div>
      <PayOrder order={order} onUpdate={setOrder} />
    </div>
  );

  // ---- terminal states
  if (order && order.status !== "pending") return (
    <div className="stack center">
      <div className="card stack-s"><div style={{ fontSize: "2.4rem" }}>{order.status === "failed" ? <Ic n="cross" size={36} /> : <Ic n="info" size={36} />}</div>
        <h2>Order {order.status.replace(/_/g, " ")}</h2><Badge s={order.status} />
        <div className="small muted">{order.status === "refund_required" ? "Your money will be refunded automatically." : "Nothing was charged. The reserved deal was released."}</div>
        <button className="btn block" onClick={() => { key.current = newKey(); setOrder(null); }}>Try again</button>
        <Link to="/">Back to deals</Link></div>
    </div>
  );

  if (err && resumeId) return <div className="stack"><ErrorBox error={err} /><Link to="/wallet"><Ic n="back" size={14} /> Wallet</Link></div>;

  // ---- review & pay
  return (
    <div className="stack">
      <Link to={`/deal/${d.id}`} className="small"><Ic n="back" size={14} /> Back</Link>
      <h1>Checkout</h1>
      <div className="card stack-s">
        <b>{d.title}</b><div className="small muted">{d.merchant_name}</div>
        <div className="row between"><span>Deal price</span><span>{money(d.price)}</span></div>
        {maxPts > 0 && <>
          <div className="divider" />
          <div className="row between"><div><b>Use reward points</b><div className="small muted">1 point = ₹1 · you have {balance}</div></div>
            <div className="row">
              <button className="btn sm light" onClick={() => setPoints(Math.max(0, points - 5))} disabled={points <= 0}>−</button>
              <b style={{ minWidth: 28, textAlign: "center" }}>{points}</b>
              <button className="btn sm light" onClick={() => setPoints(Math.min(maxPts, points + 5))} disabled={points >= maxPts}>+</button>
            </div></div>
          <div className="small muted">Up to {maxPts} points (max 50% off).</div>
          {points > 0 && <div className="row between"><span>Points discount</span><span style={{ color: "var(--ok)" }}>− {money(points)}</span></div>}
        </>}
        <div className="divider" />
        <div className="row between"><b>To pay</b><span className="price">{money(payable)}</span></div>
      </div>
      <div className="small muted">Stock is reserved for 10 minutes when you place the order. Payment is confirmed only by a verified bank callback.</div>
      {err && <div className="alert err">{err}{err.includes("Retry") ? " Tap again to retry safely." : ""}</div>}
      <button className="btn block" disabled={busy} onClick={place}>{busy ? "Placing order…" : `Pay ${money(payable)} with UPI`}</button>
    </div>
  );
}
