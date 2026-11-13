import { useEffect, useState } from "react";
import { api, money } from "../../api";
import { useToast } from "../../components";

/** Payment panel for a pending order. The simulated UPI app builds a SIGNED callback and sends it through
 *  the real webhook path; the client never decides that a payment succeeded - it re-reads the order. */
export default function PayOrder({ order, onUpdate }: { order: any; onUpdate: (o: any) => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [demo, setDemo] = useState(false);
  const [left, setLeft] = useState<number | null>(null);

  useEffect(() => {
    if (!order.expires_at) return;
    const t = () => setLeft(Math.max(0, Math.floor((new Date(order.expires_at).getTime() - Date.now()) / 1000)));
    t(); const i = setInterval(t, 1000); return () => clearInterval(i);
  }, [order.expires_at]);

  const pay = async (outcome: string) => {
    setBusy(true); setNote("");
    try {
      const r = await api("/dev/simulate-payment", { body: { order_id: order.id, outcome } });
      if (r.status === "callback_lost") setNote("Payment succeeded at the bank, but the confirmation never reached NextTo. Nothing is lost: an admin (or the scheduled job) runs reconciliation and your voucher will appear.");
      else if (r.order_status === "refund_required") setNote("The amount received did not match the order, so it was flagged and will be refunded automatically.");
      else if (r.order_status === "failed") setNote("Payment failed. The reserved deal was released.");
      onUpdate(await api(`/orders/${order.id}`));
    } catch (e: any) { toast(e.message, "err"); }
    setBusy(false);
  };

  const mm = left === null ? "" : `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
  return (
    <div className="stack">
      <div className="card stack-s">
        <div className="row between"><b>Order #{order.id}</b><span className="badge warn">awaiting payment</span></div>
        <div className="price">{money(order.amount)}</div>
        {left !== null && <div className={"small " + (left < 60 ? "bold" : "muted")} style={left < 60 ? { color: "var(--err)" } : undefined}>
          {left > 0 ? `⏱ Deal reserved for you · ${mm}` : "Reservation expired — a late payment is still recoverable"}</div>}
        {order.checkout?.upi_intent && <div className="small muted" style={{ wordBreak: "break-all" }}>{order.checkout.upi_intent}</div>}
      </div>
      <button className="btn block" disabled={busy} onClick={() => pay("success")}>{busy ? "Processing…" : `Pay ${money(order.amount)} with UPI (simulated)`}</button>
      {note && <div className="alert info small">{note}</div>}
      <div className="card flat stack-s">
        <div className="small bold" style={{ cursor: "pointer" }} onClick={() => setDemo(!demo)}>{demo ? "▾" : "▸"} Demo controls (test edge cases)</div>
        {demo && <div className="row wrap">
          <button className="btn sm light" disabled={busy} onClick={() => pay("failed")}>Payment fails</button>
          <button className="btn sm light" disabled={busy} onClick={() => pay("lost")}>Callback lost</button>
          <button className="btn sm light" disabled={busy} onClick={() => pay("wrong_amount")}>Wrong amount</button>
        </div>}
      </div>
    </div>
  );
}
