"""Core transactional business logic: orders, payments, vouchers, refunds, bookings, jobs.

Each public function that changes money / stock / voucher state runs in ONE transaction
(`tx`), mirroring the design's rule that these are single atomic database operations.
"""
import json

from .core import AppError, bad, conflict, forbidden, new_voucher_code, not_found, qr_payload, qr_parse
from .db import audit, cfg, iso, notify, now, now_iso, one, parse, plus, points_balance, rows, tx
from .providers import ProviderError, get_provider, get_risk


# ------------------------------------------------------------------ helpers
def order_view(conn, o: dict) -> dict:
    o = dict(o)
    o["checkout"] = json.loads(o["checkout"]) if o.get("checkout") else None
    v = one(conn.execute("SELECT id,code,status,valid_until FROM vouchers WHERE order_id=?", (o["id"],)))
    o["voucher"] = v
    d = one(conn.execute("SELECT title FROM deals WHERE id=?", (o["deal_id"],))) if o.get("deal_id") else None
    o["deal_title"] = d["title"] if d else None
    return o


def deal_is_live(deal: dict | None) -> bool:
    if not deal or deal["status"] != "active":
        return False
    n = now()
    return parse(deal["starts_at"]) <= n <= parse(deal["ends_at"])


def _issue_voucher(conn, order: dict, deal: dict) -> dict:
    code = new_voucher_code()
    cur = conn.execute(
        "INSERT INTO vouchers(order_id,consumer_id,deal_id,merchant_id,code,status,valid_until,issued_at) VALUES(?,?,?,?,?,'active',?,?)",
        (order["id"], order["consumer_id"], deal["id"], deal["merchant_id"], code,
         plus(days=deal["redeem_window_days"]), now_iso()))
    return {"id": cur.lastrowid, "code": code}


def _release_hold(conn, order: dict, new_status: str, reason: str):
    """Give back reserved stock and any points spent when an unpaid order dies."""
    if order["stock_held"]:
        conn.execute("UPDATE deals SET stock_remaining=MIN(stock_total,stock_remaining+1) WHERE id=?", (order["deal_id"],))
    if order["points_used"]:
        conn.execute("INSERT INTO reward_ledger(user_id,delta,reason,ref,created_at) VALUES(?,?,?,?,?)",
                     (order["consumer_id"], order["points_used"], "restore", f"order:{order['id']}", now_iso()))
    conn.execute("UPDATE orders SET status=?, stock_held=0 WHERE id=?", (new_status, order["id"]))
    audit(conn, "system", f"order.{new_status}", "order", order["id"], {"status": order["status"]}, {"status": new_status, "reason": reason})


# ------------------------------------------------------------------ create-order
def _resume(conn, order: dict) -> dict:
    """Return the saved order; if the provider was down earlier, ask it again now."""
    if order["status"] == "pending" and not order["gateway_order_id"]:
        try:
            g = get_provider().create_order(order["amount"], order["id"])
        except ProviderError:
            raise AppError(502, "provider_unavailable", "Payment provider unavailable. Retry with the same Idempotency-Key.")
        conn.execute("UPDATE orders SET gateway_order_id=?, checkout=? WHERE id=?",
                     (g["gateway_order_id"], json.dumps(g["checkout"]), order["id"]))
        order = one(conn.execute("SELECT * FROM orders WHERE id=?", (order["id"],)))
    return order_view(conn, order)


def create_order(conn, user: dict, deal_id: int, key: str, use_points: int = 0) -> dict:
    if not isinstance(key, str) or not (8 <= len(key) <= 128):
        raise bad("Idempotency-Key must be 8 to 128 characters")
    if use_points < 0:
        raise bad("use_points must be >= 0")
    q = "SELECT * FROM orders WHERE consumer_id=? AND idempotency_key=?"
    first = one(conn.execute(q, (user["id"], key)))
    if first:
        return _resume(conn, first)
    deal0 = one(conn.execute("SELECT * FROM deals WHERE id=?", (deal_id,)))
    if not deal_is_live(deal0) or deal0["stock_remaining"] <= 0:
        raise conflict("Deal is not available", "deal_unavailable")
    verdict = get_risk().score({"consumer_id": user["id"], "deal_id": deal_id, "amount": deal0["price"]})
    if verdict["decision"] == "block":
        raise forbidden("This purchase cannot be completed")

    with tx(conn):
        raced = one(conn.execute(q, (user["id"], key)))
        if raced:
            order = raced
        else:
            deal = one(conn.execute("SELECT * FROM deals WHERE id=?", (deal_id,)))
            if not deal_is_live(deal):
                raise conflict("Deal is not available", "deal_unavailable")
            # stock is RESERVED here, in the same transaction that creates the order
            cur = conn.execute("UPDATE deals SET stock_remaining=stock_remaining-1 WHERE id=? AND stock_remaining>0", (deal_id,))
            if cur.rowcount != 1:
                raise conflict("Deal is sold out", "deal_unavailable")
            max_pts = int(deal["price"] * cfg(conn, "max_points_discount_pct") / 100 / cfg(conn, "point_value_rupees"))
            if use_points > min(max_pts, points_balance(conn, user["id"])):
                raise bad(f"You can use at most {min(max_pts, points_balance(conn, user['id']))} points on this deal", "bad_points")
            amount = round(deal["price"] - use_points * cfg(conn, "point_value_rupees"), 2)
            if use_points:
                conn.execute("INSERT INTO reward_ledger(user_id,delta,reason,ref,created_at) VALUES(?,?,?,?,?)",
                             (user["id"], -use_points, "redeem", f"deal:{deal_id}", now_iso()))
            cur = conn.execute(
                "INSERT INTO orders(consumer_id,deal_id,merchant_id,kind,amount,points_used,status,idempotency_key,stock_held,expires_at,created_at) "
                "VALUES(?,?,?,'deal',?,?,'pending',?,1,?,?)",
                (user["id"], deal_id, deal["merchant_id"], amount, use_points, key,
                 plus(minutes=cfg(conn, "reservation_minutes")), now_iso()))
            audit(conn, user["id"], "order.created", "order", cur.lastrowid, None, {"status": "pending", "amount": amount})
            order = one(conn.execute("SELECT * FROM orders WHERE id=?", (cur.lastrowid,)))
    return _resume(conn, order)


# ------------------------------------------------------------------ payment-webhook
def handle_webhook(conn, raw: bytes, signature: str | None) -> dict:
    prov = get_provider()
    if not prov.verify_webhook(raw, signature):
        audit(conn, "provider", "webhook.rejected", "payment", None, None, {"reason": "bad signature"})
        raise AppError(401, "bad_signature", "Invalid webhook signature")
    try:
        ev = json.loads(raw)
        event_id, gid, amount, status = str(ev["event_id"]), ev["gateway_order_id"], float(ev["amount"]), ev["status"]
    except Exception:
        raise bad("Malformed event", "bad_event")
    result = settle_payment(conn, gid, event_id, amount, status, raw.decode("utf-8", "replace"))
    _post_commit_refunds(conn)
    return result


def settle_payment(conn, gateway_order_id: str, event_id: str, amount: float, status: str, raw: str = "") -> dict:
    with tx(conn):
        if conn.execute("SELECT 1 FROM payments WHERE event_id=?", (event_id,)).fetchone():
            return {"status": "duplicate"}
        order = one(conn.execute("SELECT * FROM orders WHERE gateway_order_id=?", (gateway_order_id,)))
        if not order:
            audit(conn, "provider", "webhook.unknown_order", "payment", gateway_order_id, None, {"event_id": event_id})
            return {"status": "unknown_order"}
        conn.execute("INSERT INTO payments(order_id,event_id,status,amount,raw,created_at) VALUES(?,?,?,?,?,?)",
                     (order["id"], event_id, status, amount, raw, now_iso()))
        # ---- failure notification
        if status != "success":
            if order["status"] == "pending":
                _release_hold(conn, order, "failed", "payment failed")
                notify(conn, order["consumer_id"], "payment_failed", "Your payment failed. The reserved deal was released.", {"order_id": order["id"]})
                return {"status": "processed", "order_status": "failed"}
            audit(conn, "provider", "webhook.late_failure_ignored", "order", order["id"], {"status": order["status"]}, None)
            return {"status": "ignored", "order_status": order["status"]}
        # ---- success notification
        if order["status"] in ("paid", "refunded", "refund_required"):
            audit(conn, "provider", "webhook.late_event_ignored", "order", order["id"], {"status": order["status"]}, {"event": event_id})
            return {"status": "ignored", "order_status": order["status"]}
        if abs(amount - order["amount"]) > 0.005:
            _release_hold(conn, order, "refund_required", f"amount mismatch {amount} != {order['amount']}")
            return {"status": "processed", "order_status": "refund_required"}
        if order["kind"] == "tip":
            conn.execute("UPDATE orders SET status='paid', paid_at=? WHERE id=?", (now_iso(), order["id"]))
            audit(conn, "provider", "order.paid", "order", order["id"], {"status": order["status"]}, {"status": "paid", "kind": "tip"})
            m = one(conn.execute("SELECT owner_id FROM merchants WHERE id=?", (order["merchant_id"],)))
            if m:
                notify(conn, m["owner_id"], "tip_received", f"You received a tip of Rs {order['amount']:.0f}")
            return {"status": "processed", "order_status": "paid"}
        deal = one(conn.execute("SELECT * FROM deals WHERE id=?", (order["deal_id"],)))
        if order["status"] in ("expired", "failed"):
            # late payment: try to take a unit again
            cur = conn.execute("UPDATE deals SET stock_remaining=stock_remaining-1 WHERE id=? AND stock_remaining>0 AND status='active'", (deal["id"],))
            if cur.rowcount != 1:
                conn.execute("UPDATE orders SET status='refund_required' WHERE id=?", (order["id"],))
                audit(conn, "provider", "order.refund_required", "order", order["id"], {"status": order["status"]}, {"reason": "late payment, no stock"})
                notify(conn, order["consumer_id"], "refund_started", "Your late payment could not be fulfilled; a refund has been started.")
                return {"status": "processed", "order_status": "refund_required"}
        conn.execute("UPDATE orders SET status='paid', stock_held=0, paid_at=? WHERE id=?", (now_iso(), order["id"]))
        voucher = _issue_voucher(conn, order, deal)
        audit(conn, "provider", "order.paid", "order", order["id"], {"status": order["status"]}, {"status": "paid"})
        audit(conn, "provider", "voucher.issued", "voucher", voucher["id"], None, {"status": "active", "order_id": order["id"]})
        notify(conn, order["consumer_id"], "order_confirmed", f"Payment confirmed. Your voucher for “{deal['title']}” is ready.", {"voucher_id": voucher["id"]})
        mo = one(conn.execute("SELECT owner_id FROM merchants WHERE id=?", (deal["merchant_id"],)))
        if mo:
            notify(conn, mo["owner_id"], "new_sale", f"New sale: {deal['title']}")
        return {"status": "processed", "order_status": "paid", "voucher_id": voucher["id"]}


def _post_commit_refunds(conn):
    """Auto-refund payments that cannot be fulfilled (late with no stock, amount mismatch)."""
    for o in rows(conn.execute("SELECT * FROM orders WHERE status='refund_required' AND kind IN('deal','tip')")):
        try:
            get_provider().refund(o["gateway_order_id"], o["amount"])
        except ProviderError:
            continue  # retried by the reconciliation job
        with tx(conn):
            conn.execute("UPDATE orders SET status='refunded' WHERE id=? AND status='refund_required'", (o["id"],))
            if o["points_used"]:
                conn.execute("INSERT INTO reward_ledger(user_id,delta,reason,ref,created_at) VALUES(?,?,?,?,?)",
                             (o["consumer_id"], o["points_used"], "restore", f"order:{o['id']}", now_iso()))
            audit(conn, "system", "order.auto_refunded", "order", o["id"], {"status": "refund_required"}, {"status": "refunded"})
            notify(conn, o["consumer_id"], "refunded", f"Rs {o['amount']:.0f} refunded to your account.")


# ------------------------------------------------------------------ scheduled jobs
def expire_pending(conn) -> dict:
    """Expire unpaid reservations, end stale deals, expire old vouchers."""
    out = {"orders": 0, "deals": 0, "vouchers": 0}
    n = now_iso()
    with tx(conn):
        for o in rows(conn.execute("SELECT * FROM orders WHERE status='pending' AND expires_at IS NOT NULL AND expires_at<?", (n,))):
            _release_hold(conn, o, "expired", "reservation timed out")
            out["orders"] += 1
        out["deals"] = conn.execute("UPDATE deals SET status='ended' WHERE status='active' AND ends_at<?", (n,)).rowcount
        out["vouchers"] = conn.execute("UPDATE vouchers SET status='expired' WHERE status='active' AND valid_until<?", (n,)).rowcount
    return out


def reconcile(conn, older_than_minutes: float | None = None) -> dict:
    """Ask the provider about orders still pending, so a lost webhook cannot leave a payer with no voucher."""
    mins = cfg(conn, "reconcile_after_minutes") if older_than_minutes is None else older_than_minutes
    cutoff = plus(minutes=-mins)
    res = {"checked": 0, "paid": 0, "failed": 0, "unreachable": 0}
    for o in rows(conn.execute("SELECT * FROM orders WHERE status IN('pending','expired') AND created_at<=?", (cutoff,))):
        res["checked"] += 1
        if not o["gateway_order_id"]:
            if o["status"] == "pending":
                with tx(conn):
                    _release_hold(conn, o, "failed", "never reached provider")
                res["failed"] += 1
            continue
        try:
            st = get_provider().get_status(o["gateway_order_id"])
        except ProviderError:
            res["unreachable"] += 1
            continue
        if st == "paid":
            settle_payment(conn, o["gateway_order_id"], f"recon_{o['id']}", o["amount"], "success", "reconciled")
            res["paid"] += 1
        elif st == "failed" and o["status"] == "pending":
            with tx(conn):
                _release_hold(conn, o, "failed", "provider reports failed")
            res["failed"] += 1
    _post_commit_refunds(conn)
    return res


# ------------------------------------------------------------------ vouchers
def voucher_view(conn, v: dict) -> dict:
    v = dict(v)
    v["qr"] = qr_payload(v["code"])
    d = one(conn.execute("SELECT title,type,category FROM deals WHERE id=?", (v["deal_id"],))) or {}
    m = one(conn.execute("SELECT name,address,lat,lng FROM merchants WHERE id=?", (v["merchant_id"],))) or {}
    v.update(deal_title=d.get("title"), deal_type=d.get("type"), merchant_name=m.get("name"),
             merchant_address=m.get("address"), merchant_lat=m.get("lat"), merchant_lng=m.get("lng"))
    b = one(conn.execute("SELECT b.id,b.status,b.slot_id,s.starts_at FROM bookings b JOIN slots s ON s.id=b.slot_id WHERE b.voucher_id=? AND b.status!='cancelled'", (v["id"],)))
    v["booking"] = b
    v["reviewed"] = bool(conn.execute("SELECT 1 FROM reviews WHERE voucher_id=?", (v["id"],)).fetchone())
    return v


def redeem_voucher(conn, merchant: dict, raw_code: str) -> dict:
    code = qr_parse(raw_code)
    with tx(conn):
        t = now_iso()
        # check + state change in ONE conditional statement: two simultaneous scans cannot both win
        cur = conn.execute(
            "UPDATE vouchers SET status='redeemed', redeemed_at=? WHERE code=? AND status='active' AND valid_until>? AND merchant_id=?",
            (t, code, t, merchant["id"]))
        if cur.rowcount != 1:
            v = one(conn.execute("SELECT * FROM vouchers WHERE code=?", (code,)))
            if not v:
                raise not_found("Voucher not found")
            if v["merchant_id"] != merchant["id"]:
                raise AppError(409, "wrong_merchant", "This voucher belongs to a different merchant")
            if v["status"] == "redeemed":
                raise AppError(409, "already_redeemed", f"Already redeemed at {v['redeemed_at']}")
            if v["status"] in ("expired",) or (v["status"] == "active" and v["valid_until"] <= t):
                raise AppError(409, "expired", "Voucher has expired")
            raise AppError(409, "not_redeemable", f"Voucher is {v['status']}")
        v = one(conn.execute("SELECT * FROM vouchers WHERE code=?", (code,)))
        order = one(conn.execute("SELECT * FROM orders WHERE id=?", (v["order_id"],)))
        pts = int(order["amount"] // cfg(conn, "point_earn_per_rupees"))
        if pts > 0:  # points are credited at redemption, not at purchase
            conn.execute("INSERT INTO reward_ledger(user_id,delta,reason,ref,created_at) VALUES(?,?,?,?,?)",
                         (v["consumer_id"], pts, "earn", f"voucher:{v['id']}", t))
        conn.execute("UPDATE bookings SET status='completed' WHERE voucher_id=? AND status='confirmed'", (v["id"],))
        audit(conn, merchant["owner_id"], "voucher.redeemed", "voucher", v["id"], {"status": "active"}, {"status": "redeemed", "merchant_id": merchant["id"]})
        notify(conn, v["consumer_id"], "voucher_redeemed", f"Voucher redeemed at {merchant['name']}. You earned {pts} points. Leave a review!", {"voucher_id": v["id"]})
    d = one(conn.execute("SELECT title,type FROM deals WHERE id=?", (v["deal_id"],)))
    return {"result": "redeemed", "voucher_id": v["id"], "code": code, "deal_title": d["title"], "deal_type": d["type"],
            "amount": order["amount"], "points_awarded": pts}


# ------------------------------------------------------------------ refunds
def request_refund(conn, user: dict, voucher_id: int, reason: str) -> dict:
    with tx(conn):
        # check + state change in one statement so it cannot race a redemption
        cur = conn.execute("UPDATE vouchers SET status='refund_pending' WHERE id=? AND consumer_id=? AND status='active'", (voucher_id, user["id"]))
        if cur.rowcount != 1:
            v = one(conn.execute("SELECT status,consumer_id FROM vouchers WHERE id=?", (voucher_id,)))
            if not v or v["consumer_id"] != user["id"]:
                raise not_found("Voucher not found")
            raise conflict(f"A refund can only be requested while a voucher is active (it is {v['status']})", "not_refundable")
        v = one(conn.execute("SELECT * FROM vouchers WHERE id=?", (voucher_id,)))
        cur = conn.execute("INSERT INTO refunds(order_id,voucher_id,reason,status,created_at) VALUES(?,?, ?,'requested',?)",
                           (v["order_id"], voucher_id, (reason or "")[:500], now_iso()))
        audit(conn, user["id"], "refund.requested", "refund", cur.lastrowid, {"voucher": "active"}, {"voucher": "refund_pending"})
        for a in rows(conn.execute("SELECT id FROM users WHERE role='admin'")):
            notify(conn, a["id"], "refund_request", "New refund request awaiting decision")
        return {"refund_id": cur.lastrowid, "status": "requested"}


def decide_refund(conn, admin: dict, refund_id: int, decision: str, reason: str | None) -> dict:
    if decision not in ("approve", "reject"):
        raise bad("decision must be approve or reject")
    r = one(conn.execute("SELECT * FROM refunds WHERE id=?", (refund_id,)))
    if not r:
        raise not_found("Refund not found")
    if r["status"] in ("processed", "rejected"):
        raise conflict(f"Refund already {r['status']}", "already_decided")
    if decision == "reject":
        if r["status"] != "requested":
            raise conflict("Approved refunds can only be retried, not rejected", "invalid_state")
        if not reason or not reason.strip():
            raise bad("A rejection needs a reason")
        with tx(conn):
            conn.execute("UPDATE refunds SET status='rejected', decided_by=?, decided_at=?, decision_reason=? WHERE id=?", (admin["id"], now_iso(), reason, refund_id))
            conn.execute("UPDATE vouchers SET status='active' WHERE id=? AND status='refund_pending'", (r["voucher_id"],))
            audit(conn, admin["id"], "refund.rejected", "refund", refund_id, {"status": "requested"}, {"status": "rejected", "reason": reason})
            o = one(conn.execute("SELECT consumer_id FROM orders WHERE id=?", (r["order_id"],)))
            notify(conn, o["consumer_id"], "refund_rejected", f"Your refund request was declined: {reason}")
        return {"status": "rejected"}
    # approve: record the decision, call the provider OUTSIDE any transaction, then finish
    order = one(conn.execute("SELECT * FROM orders WHERE id=?", (r["order_id"],)))
    with tx(conn):
        conn.execute("UPDATE refunds SET status='approved', decided_by=?, decided_at=?, decision_reason=? WHERE id=?", (admin["id"], now_iso(), reason, refund_id))
        audit(conn, admin["id"], "refund.approved", "refund", refund_id, {"status": r["status"]}, {"status": "approved"})
    try:
        get_provider().refund(order["gateway_order_id"], order["amount"])
    except ProviderError:
        raise AppError(502, "provider_unavailable", "Refund approved but the provider call failed. Approve again to retry.")
    with tx(conn):
        conn.execute("UPDATE refunds SET status='processed' WHERE id=?", (refund_id,))
        conn.execute("UPDATE orders SET status='refunded' WHERE id=?", (order["id"],))
        conn.execute("UPDATE vouchers SET status='refunded' WHERE id=?", (r["voucher_id"],))
        deal = one(conn.execute("SELECT * FROM deals WHERE id=?", (order["deal_id"],)))
        if deal_is_live(deal):  # restore stock only while the sale window is still open
            conn.execute("UPDATE deals SET stock_remaining=MIN(stock_total,stock_remaining+1) WHERE id=?", (deal["id"],))
        if order["points_used"]:
            conn.execute("INSERT INTO reward_ledger(user_id,delta,reason,ref,created_at) VALUES(?,?,?,?,?)",
                         (order["consumer_id"], order["points_used"], "restore", f"order:{order['id']}", now_iso()))
        b = one(conn.execute("SELECT * FROM bookings WHERE voucher_id=? AND status='confirmed'", (r["voucher_id"],)))
        if b:
            conn.execute("UPDATE bookings SET status='cancelled' WHERE id=?", (b["id"],))
            conn.execute("UPDATE slots SET booked_count=MAX(0,booked_count-1) WHERE id=?", (b["slot_id"],))
        audit(conn, admin["id"], "refund.processed", "refund", refund_id, {"order": "paid"}, {"order": "refunded", "voucher": "refunded"})
        notify(conn, order["consumer_id"], "refunded", f"Rs {order['amount']:.0f} refunded to your account.")
    return {"status": "processed"}


# ------------------------------------------------------------------ bookings
def create_booking(conn, user: dict, voucher_id: int, slot_id: int) -> dict:
    v = one(conn.execute("SELECT * FROM vouchers WHERE id=? AND consumer_id=?", (voucher_id, user["id"])))
    if not v:
        raise not_found("Voucher not found")
    if v["status"] != "active":
        raise conflict(f"Voucher is {v['status']}", "not_bookable")
    slot = one(conn.execute("SELECT * FROM slots WHERE id=? AND deal_id=?", (slot_id, v["deal_id"])))
    if not slot:
        raise not_found("Slot not found for this deal")
    if slot["starts_at"] <= now_iso():
        raise conflict("Slot is in the past", "slot_past")
    with tx(conn):
        ex = one(conn.execute("SELECT * FROM bookings WHERE voucher_id=?", (voucher_id,)))
        if ex and ex["status"] != "cancelled":
            raise conflict("This voucher already has a booking; cancel it first", "already_booked")
        # guarded update: capacity can never be exceeded
        cur = conn.execute("UPDATE slots SET booked_count=booked_count+1 WHERE id=? AND booked_count<capacity", (slot_id,))
        if cur.rowcount != 1:
            raise conflict("Slot is full", "slot_full")
        if ex:
            conn.execute("UPDATE bookings SET slot_id=?, status='confirmed', created_at=? WHERE id=?", (slot_id, now_iso(), ex["id"]))
            bid = ex["id"]
        else:
            bid = conn.execute("INSERT INTO bookings(voucher_id,slot_id,status,created_at) VALUES(?,?, 'confirmed',?)", (voucher_id, slot_id, now_iso())).lastrowid
        audit(conn, user["id"], "booking.created", "booking", bid, None, {"slot_id": slot_id})
        mo = one(conn.execute("SELECT owner_id FROM merchants WHERE id=?", (v["merchant_id"],)))
        notify(conn, user["id"], "booking_confirmed", f"Appointment confirmed for {slot['starts_at']}")
        if mo:
            notify(conn, mo["owner_id"], "new_booking", f"New booking for {slot['starts_at']}")
    return {"booking_id": bid, "status": "confirmed", "slot_id": slot_id, "starts_at": slot["starts_at"]}


def cancel_booking(conn, user: dict, booking_id: int) -> dict:
    b = one(conn.execute("SELECT b.*, v.consumer_id, s.starts_at FROM bookings b JOIN vouchers v ON v.id=b.voucher_id JOIN slots s ON s.id=b.slot_id WHERE b.id=?", (booking_id,)))
    if not b or b["consumer_id"] != user["id"]:
        raise not_found("Booking not found")
    if b["status"] != "confirmed":
        raise conflict(f"Booking is {b['status']}", "not_cancellable")
    if parse(b["starts_at"]) - now() < __import__("datetime").timedelta(hours=2):
        raise conflict("Bookings can only be cancelled up to 2 hours before the slot", "too_late")
    with tx(conn):
        conn.execute("UPDATE bookings SET status='cancelled' WHERE id=? AND status='confirmed'", (booking_id,))
        conn.execute("UPDATE slots SET booked_count=MAX(0,booked_count-1) WHERE id=?", (b["slot_id"],))
        audit(conn, user["id"], "booking.cancelled", "booking", booking_id, {"status": "confirmed"}, {"status": "cancelled"})
    return {"status": "cancelled"}
