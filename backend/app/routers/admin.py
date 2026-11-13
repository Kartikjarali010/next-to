"""Admin API: approval queues, refunds, payouts, moderation, analytics, audit log, jobs."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .. import services as svc
from ..core import bad, conflict, not_found, require
from ..db import audit, cfg, get_db, notify, now_iso, one, rows, tx

router = APIRouter(prefix="/api/admin", tags=["admin"])
admin = require("admin")


class Decision(BaseModel):
    decision: str  # approve | reject
    reason: str | None = None


def _check(d: Decision):
    if d.decision not in ("approve", "reject"):
        raise bad("decision must be approve or reject")
    if d.decision == "reject" and not (d.reason and d.reason.strip()):
        raise bad("A rejection needs a reason")


@router.get("/merchants")
def merchants(status: str | None = None, user=Depends(admin), conn=Depends(get_db)):
    sql, args = "SELECT m.*, u.email owner_email, u.name owner_name FROM merchants m JOIN users u ON u.id=m.owner_id", []
    if status:
        sql += " WHERE m.verification_status=?"
        args.append(status)
    return rows(conn.execute(sql + " ORDER BY m.id DESC", args))


@router.post("/merchants/{mid}/decision")
def merchant_decision(mid: int, body: Decision, user=Depends(admin), conn=Depends(get_db)):
    _check(body)
    m = one(conn.execute("SELECT * FROM merchants WHERE id=?", (mid,)))
    if not m:
        raise not_found("Merchant not found")
    new = "approved" if body.decision == "approve" else "rejected"
    with tx(conn):
        conn.execute("UPDATE merchants SET verification_status=?, reject_reason=? WHERE id=?", (new, body.reason if new == "rejected" else None, mid))
        if new == "approved":  # role is granted server-side, takes effect at the next token refresh
            conn.execute("UPDATE users SET role='merchant' WHERE id=? AND role='merchant_applicant'", (m["owner_id"],))
        audit(conn, user["id"], f"merchant.{new}", "merchant", mid, {"status": m["verification_status"]}, {"status": new, "reason": body.reason})
        notify(conn, m["owner_id"], f"merchant_{new}", "Your business was approved. You can now create deals." if new == "approved" else f"Your business application was rejected: {body.reason}")
    return {"status": new}


@router.get("/deals")
def deals(status: str | None = None, user=Depends(admin), conn=Depends(get_db)):
    sql, args = "SELECT d.*, m.name merchant_name FROM deals d JOIN merchants m ON m.id=d.merchant_id", []
    if status:
        sql += " WHERE d.status=?"
        args.append(status)
    return rows(conn.execute(sql + " ORDER BY d.id DESC", args))


@router.post("/deals/{did}/decision")
def deal_decision(did: int, body: Decision, user=Depends(admin), conn=Depends(get_db)):
    _check(body)
    d = one(conn.execute("SELECT d.*, m.owner_id, m.verification_status FROM deals d JOIN merchants m ON m.id=d.merchant_id WHERE d.id=?", (did,)))
    if not d:
        raise not_found("Deal not found")
    if d["status"] != "pending":
        raise conflict(f"Only pending deals can be decided (this one is {d['status']})", "invalid_state")
    if body.decision == "approve" and d["verification_status"] != "approved":
        raise conflict("The merchant is not verified", "merchant_unverified")
    new = "active" if body.decision == "approve" else "rejected"
    with tx(conn):
        conn.execute("UPDATE deals SET status=?, reject_reason=?, published_at=COALESCE(published_at,?) WHERE id=? AND status='pending'",
                     (new, body.reason if new == "rejected" else None, now_iso() if new == "active" else None, did))
        audit(conn, user["id"], f"deal.{'approved' if new == 'active' else 'rejected'}", "deal", did, {"status": "pending"}, {"status": new, "reason": body.reason})
        notify(conn, d["owner_id"], "deal_decision", f"Your deal “{d['title']}” is now live." if new == "active" else f"Your deal “{d['title']}” was rejected: {body.reason}")
    return {"status": new}


@router.get("/refunds")
def refunds(status: str | None = None, user=Depends(admin), conn=Depends(get_db)):
    sql = ("SELECT r.*, o.amount, u.name consumer_name, d.title deal_title, m.name merchant_name FROM refunds r "
           "JOIN orders o ON o.id=r.order_id JOIN users u ON u.id=o.consumer_id JOIN deals d ON d.id=o.deal_id JOIN merchants m ON m.id=d.merchant_id")
    args = []
    if status:
        sql += " WHERE r.status=?"
        args.append(status)
    return rows(conn.execute(sql + " ORDER BY r.id DESC", args))


@router.post("/refunds/{rid}/decision")
def refund_decision(rid: int, body: Decision, user=Depends(admin), conn=Depends(get_db)):
    return svc.decide_refund(conn, user, rid, body.decision, body.reason)


class PayoutRun(BaseModel):
    period: str | None = None


@router.post("/payouts/run")
def run_payouts(body: PayoutRun, user=Depends(admin), conn=Depends(get_db)):
    """Settle redeemed vouchers (net of refunds, which never reach 'redeemed') less the platform fee."""
    fee_pct = cfg(conn, "platform_fee_pct")
    period = body.period or now_iso()[:10]
    created = []
    with tx(conn):
        for m in rows(conn.execute("SELECT id FROM merchants WHERE verification_status='approved'")):
            v = rows(conn.execute("SELECT v.id, o.amount + o.points_used gross FROM vouchers v JOIN orders o ON o.id=v.order_id WHERE v.merchant_id=? AND v.status='redeemed' AND v.payout_id IS NULL", (m["id"],)))
            tips = rows(conn.execute("SELECT id, amount FROM orders WHERE merchant_id=? AND kind='tip' AND status='paid' AND payout_id IS NULL", (m["id"],)))
            if not v and not tips:
                continue
            gross = round(sum(x["gross"] for x in v), 2)
            fee = round(gross * fee_pct / 100, 2)
            tip_total = round(sum(t["amount"] for t in tips), 2)
            net = round(gross - fee + tip_total, 2)
            pid = conn.execute("INSERT INTO payouts(merchant_id,period,gross,fee,net,status,created_at) VALUES(?,?,?,?,?, 'pending',?)",
                               (m["id"], period, gross + tip_total, fee, net, now_iso())).lastrowid
            conn.executemany("UPDATE vouchers SET payout_id=? WHERE id=?", [(pid, x["id"]) for x in v])
            conn.executemany("UPDATE orders SET payout_id=? WHERE id=?", [(pid, t["id"]) for t in tips])
            audit(conn, user["id"], "payout.created", "payout", pid, None, {"merchant_id": m["id"], "net": net})
            created.append(pid)
    return {"created": created}


@router.get("/payouts")
def payouts(user=Depends(admin), conn=Depends(get_db)):
    return rows(conn.execute("SELECT p.*, m.name merchant_name FROM payouts p JOIN merchants m ON m.id=p.merchant_id ORDER BY p.id DESC"))


@router.post("/payouts/{pid}/release")
def release_payout(pid: int, user=Depends(admin), conn=Depends(get_db)):
    with tx(conn):
        cur = conn.execute("UPDATE payouts SET status='released', released_at=? WHERE id=? AND status='pending'", (now_iso(), pid))
        if cur.rowcount != 1:
            raise conflict("Payout not found or already released", "invalid_state")
        audit(conn, user["id"], "payout.released", "payout", pid, {"status": "pending"}, {"status": "released"})
    return {"status": "released"}


@router.get("/stats")
def stats(user=Depends(admin), conn=Depends(get_db)):
    q = lambda sql: conn.execute(sql).fetchone()
    sold = q("SELECT COUNT(*) c, COALESCE(SUM(o.amount),0) gmv FROM vouchers v JOIN orders o ON o.id=v.order_id")
    redeemed = q("SELECT COUNT(*) c FROM vouchers WHERE status='redeemed'")["c"]
    return {
        "users": q("SELECT COUNT(*) c FROM users WHERE role='consumer'")["c"],
        "merchants": q("SELECT COUNT(*) c FROM merchants WHERE verification_status='approved'")["c"],
        "active_deals": q("SELECT COUNT(*) c FROM deals WHERE status='active'")["c"],
        "vouchers_sold": sold["c"], "gmv": round(sold["gmv"], 2), "redeemed": redeemed,
        "redemption_rate": round(redeemed / sold["c"], 3) if sold["c"] else 0,
        "pending_merchants": q("SELECT COUNT(*) c FROM merchants WHERE verification_status='pending'")["c"],
        "pending_deals": q("SELECT COUNT(*) c FROM deals WHERE status='pending'")["c"],
        "pending_refunds": q("SELECT COUNT(*) c FROM refunds WHERE status IN('requested','approved')")["c"],
        "pending_payouts": q("SELECT COUNT(*) c FROM payouts WHERE status='pending'")["c"],
        "platform_fee_earned": round(q("SELECT COALESCE(SUM(fee),0) s FROM payouts")["s"], 2),
    }


@router.get("/audit")
def audit_log(limit: int = 100, entity: str | None = None, user=Depends(admin), conn=Depends(get_db)):
    sql, args = "SELECT * FROM audit_log", []
    if entity:
        sql += " WHERE entity=?"
        args.append(entity)
    return rows(conn.execute(sql + " ORDER BY id DESC LIMIT ?", args + [max(1, min(limit, 500))]))


@router.get("/reviews")
def reviews(user=Depends(admin), conn=Depends(get_db)):
    return rows(conn.execute("SELECT r.*, u.name consumer_name, m.name merchant_name FROM reviews r JOIN users u ON u.id=r.consumer_id JOIN merchants m ON m.id=r.merchant_id ORDER BY r.id DESC LIMIT 100"))


@router.post("/reviews/{rid}/hide")
def hide_review(rid: int, user=Depends(admin), conn=Depends(get_db)):
    with tx(conn):
        cur = conn.execute("UPDATE reviews SET hidden=1 WHERE id=?", (rid,))
        if cur.rowcount != 1:
            raise not_found("Review not found")
        audit(conn, user["id"], "review.hidden", "review", rid, {"hidden": 0}, {"hidden": 1})
    return {"hidden": True}


@router.get("/users")
def users(user=Depends(admin), conn=Depends(get_db)):
    return rows(conn.execute("SELECT id,email,name,role,suspended,created_at FROM users ORDER BY id DESC LIMIT 200"))


@router.post("/users/{uid}/suspend")
def suspend(uid: int, suspended: bool = True, user=Depends(admin), conn=Depends(get_db)):
    if uid == user["id"]:
        raise bad("You cannot suspend yourself")
    with tx(conn):
        cur = conn.execute("UPDATE users SET suspended=? WHERE id=?", (1 if suspended else 0, uid))
        if cur.rowcount != 1:
            raise not_found("User not found")
        audit(conn, user["id"], "user.suspended" if suspended else "user.reinstated", "user", uid)
    return {"suspended": suspended}


class ReconcileIn(BaseModel):
    older_than_minutes: float | None = None


@router.post("/jobs/expire")
def job_expire(user=Depends(admin), conn=Depends(get_db)):
    return svc.expire_pending(conn)


@router.post("/jobs/reconcile")
def job_reconcile(body: ReconcileIn, user=Depends(admin), conn=Depends(get_db)):
    svc.expire_pending(conn)
    return svc.reconcile(conn, body.older_than_minutes)
