import { Ic } from "../../icons";
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import { api, fmtDate, fmtDay, money } from "../../api";
import { Badge, ErrorBox, Sheet, Spinner, useToast } from "../../components";
import PayOrder from "./PayOrder";

export default function VoucherDetail() {
  const { id } = useParams();
  const toast = useToast();
  const [v, setV] = useState<any>(null);
  const [err, setErr] = useState("");
  const [slots, setSlots] = useState<any[]>([]);
  const [slotId, setSlotId] = useState<number | null>(null);
  const [refundOpen, setRefundOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const [tip, setTip] = useState("");
  const [tipOrder, setTipOrder] = useState<any>(null);

  const load = useCallback(async () => {
    try { setV(await api(`/vouchers/${id}`)); setErr(""); } catch (e: any) { setErr(e.message); }
  }, [id]);
  useEffect(() => { load(); const t = setInterval(load, 4000); return () => clearInterval(t); }, [load]); // live flip to "Redeemed"

  const needSlots = v && v.deal_type === "service" && v.status === "active" && !v.booking;
  useEffect(() => { if (needSlots) api<any[]>(`/deals/${v.deal_id}/slots`).then(setSlots).catch(() => {}); }, [needSlots, v?.deal_id]);

  const act = async (fn: () => Promise<any>, ok: string) => {
    setBusy(true);
    try { await fn(); toast(ok); await load(); } catch (e: any) { toast(e.message, "err"); }
    setBusy(false);
  };

  if (err && !v) return <div className="stack"><ErrorBox error={err} retry={load} /><Link to="/wallet"><Ic n="back" size={14} /> Wallet</Link></div>;
  if (!v) return <Spinner />;

  const submitReview = async () => {
    setBusy(true);
    try {
      const r = await api("/reviews", { body: { voucher_id: v.id, rating, comment, tip: tip ? parseFloat(tip) : 0 } });
      toast("Thanks for your review!");
      if (r.tip_order) setTipOrder(r.tip_order);
      await load();
    } catch (e: any) { toast(e.message, "err"); }
    setBusy(false);
  };

  return (
    <div className="stack">
      <Link to="/wallet" className="small"><Ic n="back" size={14} /> Wallet</Link>
      <div className="card stack-s">
        <div className="row between"><h2 style={{ margin: 0 }}>{v.deal_title}</h2><Badge s={v.status} /></div>
        <div className="small muted">{v.merchant_name} · {v.merchant_address}</div>
        <a className="small" href={`https://www.google.com/maps?q=${v.merchant_lat},${v.merchant_lng}`} target="_blank" rel="noreferrer"><Ic n="pin" size={14} /> Open in Maps</a>
      </div>

      {v.status === "active" && (
        <div className="card stack">
          <div className="qrbox"><QRCodeSVG value={v.qr} size={210} level="M" /></div>
          <div className="voucher-code">{v.code}</div>
          <div className="small muted center">Show this to the merchant. Works once · valid until {fmtDay(v.valid_until)}</div>
        </div>
      )}
      {v.status === "refund_pending" && <div className="alert warn"><Ic n="hourglass" size={14} /> Refund requested — this voucher is on hold while an admin reviews it.</div>}
      {v.status === "refunded" && <div className="alert info"><Ic n="payout" size={14} /> This voucher was refunded to your account.</div>}
      {v.status === "expired" && <div className="alert warn">This voucher has expired.</div>}
      {v.status === "redeemed" && <div className="alert ok"><Ic n="check" size={14} /> Redeemed {v.redeemed_at ? fmtDate(v.redeemed_at) : ""}. Points have been added to your account.</div>}

      {v.booking && (
        <div className="card stack-s">
          <b><Ic n="calendar" size={14} /> Appointment</b><div>{fmtDate(v.booking.starts_at)} <Badge s={v.booking.status} /></div>
          {v.booking.status === "confirmed" && v.status === "active" &&
            <button className="btn sm ghost" disabled={busy} onClick={() => act(() => api(`/bookings/${v.booking.id}/cancel`, { method: "POST", body: {} }), "Booking cancelled")}>Cancel booking</button>}
        </div>
      )}

      {needSlots && (
        <div className="card stack-s">
          <b><Ic n="calendar" size={14} /> Book your appointment</b>
          {slots.length === 0 ? <div className="small muted">No slots available right now.</div> :
            <div className="chips" style={{ flexWrap: "wrap" }}>{slots.map((s) => {
              const full = s.booked_count >= s.capacity;
              return <span key={s.id} className={"chip " + (slotId === s.id ? "on" : "")} style={{ opacity: full ? .4 : 1 }} onClick={() => !full && setSlotId(s.id)}>{fmtDate(s.starts_at)}{full ? " · full" : ""}</span>;
            })}</div>}
          <button className="btn block" disabled={!slotId || busy} onClick={() => act(() => api("/bookings", { body: { voucher_id: v.id, slot_id: slotId } }), "Appointment confirmed")}>Confirm slot</button>
        </div>
      )}

      {v.status === "redeemed" && !v.reviewed && !tipOrder && (
        <div className="card stack">
          <h3>How was it?</h3>
          <div className="row" style={{ fontSize: "2rem", justifyContent: "center", gap: 4 }}>
            {[1, 2, 3, 4, 5].map((n) => <span key={n} role="button" aria-label={`${n} stars`} style={{ cursor: "pointer", opacity: n <= rating ? 1 : .25 }} onClick={() => setRating(n)}><Ic n="star" size={30} fill="currentColor" className="amber" /></span>)}
          </div>
          <textarea className="input" placeholder="Tell others about your visit (optional)" value={comment} onChange={(e) => setComment(e.target.value)} />
          <div className="field"><label>Add a tip (optional, ₹)</label><input className="input" inputMode="numeric" value={tip} onChange={(e) => setTip(e.target.value.replace(/[^\d.]/g, ""))} placeholder="0" /></div>
          <button className="btn block" disabled={busy} onClick={submitReview}>Submit review</button>
        </div>
      )}
      {tipOrder && tipOrder.status === "pending" && (
        <div className="stack"><div className="alert info">Review saved. Complete your {money(tipOrder.amount)} tip:</div>
          <PayOrder order={tipOrder} onUpdate={(o) => { setTipOrder(o.status === "pending" ? o : null); if (o.status === "paid") toast("Tip sent. Thank you!"); }} /></div>
      )}
      {v.reviewed && !tipOrder && <div className="alert ok"><Ic n="check" size={14} /> Thanks for reviewing!</div>}

      {v.status === "active" && (
        <button className="btn ghost block" onClick={() => setRefundOpen(true)}>Request refund</button>
      )}
      {refundOpen && (
        <Sheet onClose={() => setRefundOpen(false)}>
          <div className="stack"><h2>Request a refund</h2>
            <div className="small muted">The voucher is put on hold while an admin decides. If approved you get your money back.</div>
            <textarea className="input" placeholder="Reason" value={reason} onChange={(e) => setReason(e.target.value)} />
            <button className="btn danger block" disabled={busy} onClick={async () => { await act(() => api("/refunds", { body: { voucher_id: v.id, reason } }), "Refund requested"); setRefundOpen(false); }}>Submit request</button>
            <button className="btn light block" onClick={() => setRefundOpen(false)}>Cancel</button></div>
        </Sheet>
      )}
    </div>
  );
}
