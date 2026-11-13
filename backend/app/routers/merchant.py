"""Merchant API: onboarding status, deals, slots, voucher validation, bookings, dashboard."""
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from .. import services as svc
from ..core import bad, conflict, forbidden, not_found, qr_parse, rate_limit, require
from ..db import audit, get_db, iso, now, now_iso, one, parse, rows, tx
from ..ranking import CATEGORIES

router = APIRouter(prefix="/api/merchant", tags=["merchant"])


def my_merchant(conn, user, need_approved=True) -> dict:
    m = one(conn.execute("SELECT * FROM merchants WHERE owner_id=?", (user["id"],)))
    if not m:
        raise not_found("No business profile found")
    if need_approved and m["verification_status"] != "approved":
        raise forbidden("Your business is not verified yet")
    return m


@router.get("/me")
def me(user=Depends(require("merchant", "merchant_applicant")), conn=Depends(get_db)):
    return my_merchant(conn, user, need_approved=False)


class DealIn(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=1000)
    category: str
    type: str = "voucher"
    price: float = Field(gt=0, le=100000)
    original_price: float = Field(gt=0, le=100000)
    stock_total: int = Field(ge=1, le=10000)
    starts_at: str
    ends_at: str
    redeem_window_days: int = Field(default=30, ge=1, le=365)


def _validate(d: DealIn):
    if d.category not in CATEGORIES:
        raise bad("Unknown category")
    if d.type not in ("voucher", "service"):
        raise bad("type must be voucher or service")
    if d.original_price < d.price:
        raise bad("Original price must be at least the deal price")
    try:
        s, e = parse(d.starts_at), parse(d.ends_at)
    except Exception:
        raise bad("starts_at/ends_at must be ISO timestamps")
    if e <= s:
        raise bad("ends_at must be after starts_at")


@router.get("/deals")
def my_deals(user=Depends(require("merchant")), conn=Depends(get_db)):
    m = my_merchant(conn, user)
    svc.expire_pending(conn)
    out = rows(conn.execute("SELECT * FROM deals WHERE merchant_id=? ORDER BY id DESC", (m["id"],)))
    for d in out:
        d["sold"] = conn.execute("SELECT COUNT(*) c FROM vouchers WHERE deal_id=?", (d["id"],)).fetchone()["c"]
    return out


@router.post("/deals")
def deal_create(body: DealIn, user=Depends(require("merchant")), conn=Depends(get_db)):
    m = my_merchant(conn, user)
    _validate(body)
    with tx(conn):
        did = conn.execute(
            "INSERT INTO deals(merchant_id,title,description,category,type,price,original_price,stock_total,stock_remaining,starts_at,ends_at,redeem_window_days,status,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'draft',?)",
            (m["id"], body.title.strip(), body.description, body.category, body.type, body.price, body.original_price,
             body.stock_total, body.stock_total, body.starts_at, body.ends_at, body.redeem_window_days, now_iso())).lastrowid
        audit(conn, user["id"], "deal.created", "deal", did, None, {"status": "draft"})
    return one(conn.execute("SELECT * FROM deals WHERE id=?", (did,)))


def _own_deal(conn, m, deal_id):
    d = one(conn.execute("SELECT * FROM deals WHERE id=? AND merchant_id=?", (deal_id, m["id"])))
    if not d:
        raise not_found("Deal not found")
    return d


@router.put("/deals/{deal_id}")
def deal_update(deal_id: int, body: DealIn, user=Depends(require("merchant")), conn=Depends(get_db)):
    m = my_merchant(conn, user)
    d = _own_deal(conn, m, deal_id)
    _validate(body)
    # editing a live deal sends it back for re-approval; a merchant can never set 'active' itself
    new_status = "pending" if d["status"] == "active" else ("draft" if d["status"] in ("rejected", "ended") else d["status"])
    sold = d["stock_total"] - d["stock_remaining"]
    if body.stock_total < sold:
        raise bad(f"Stock cannot be below units already sold/reserved ({sold})")
    with tx(conn):
        conn.execute(
            "UPDATE deals SET title=?,description=?,category=?,type=?,price=?,original_price=?,stock_total=?,stock_remaining=?,starts_at=?,ends_at=?,redeem_window_days=?,status=? WHERE id=?",
            (body.title.strip(), body.description, body.category, body.type, body.price, body.original_price, body.stock_total,
             body.stock_total - sold, body.starts_at, body.ends_at, body.redeem_window_days, new_status, deal_id))
        audit(conn, user["id"], "deal.updated", "deal", deal_id, {"status": d["status"]}, {"status": new_status})
    return one(conn.execute("SELECT * FROM deals WHERE id=?", (deal_id,)))


@router.post("/deals/{deal_id}/submit")
def deal_submit(deal_id: int, user=Depends(require("merchant")), conn=Depends(get_db)):
    m = my_merchant(conn, user)
    d = _own_deal(conn, m, deal_id)
    if d["status"] not in ("draft", "rejected"):
        raise conflict(f"A {d['status']} deal cannot be submitted", "invalid_state")
    with tx(conn):
        conn.execute("UPDATE deals SET status='pending', reject_reason=NULL WHERE id=?", (deal_id,))
        audit(conn, user["id"], "deal.submitted", "deal", deal_id, {"status": d["status"]}, {"status": "pending"})
        for a in rows(conn.execute("SELECT id FROM users WHERE role='admin'")):
            from ..db import notify
            notify(conn, a["id"], "deal_pending", f"Deal awaiting approval: {d['title']}")
    return {"status": "pending"}


class SlotIn(BaseModel):
    starts_at: str
    capacity: int = Field(ge=1, le=500)


@router.post("/deals/{deal_id}/slots")
def slot_create(deal_id: int, body: SlotIn, user=Depends(require("merchant")), conn=Depends(get_db)):
    m = my_merchant(conn, user)
    d = _own_deal(conn, m, deal_id)
    if d["type"] != "service":
        raise bad("Slots can only be added to service deals")
    try:
        parse(body.starts_at)
    except Exception:
        raise bad("starts_at must be an ISO timestamp")
    sid = conn.execute("INSERT INTO slots(deal_id,starts_at,capacity) VALUES(?,?,?)", (deal_id, body.starts_at, body.capacity)).lastrowid
    return {"id": sid}


@router.get("/deals/{deal_id}/slots")
def slots(deal_id: int, user=Depends(require("merchant")), conn=Depends(get_db)):
    m = my_merchant(conn, user)
    _own_deal(conn, m, deal_id)
    return rows(conn.execute("SELECT * FROM slots WHERE deal_id=? ORDER BY starts_at", (deal_id,)))


@router.get("/bookings")
def bookings(user=Depends(require("merchant")), conn=Depends(get_db)):
    m = my_merchant(conn, user)
    return rows(conn.execute(
        "SELECT b.id,b.status,s.starts_at,d.title deal_title,u.name consumer_name,v.code voucher_code "
        "FROM bookings b JOIN slots s ON s.id=b.slot_id JOIN deals d ON d.id=s.deal_id JOIN vouchers v ON v.id=b.voucher_id "
        "JOIN users u ON u.id=v.consumer_id WHERE d.merchant_id=? AND b.status!='cancelled' ORDER BY s.starts_at", (m["id"],)))


class CodeIn(BaseModel):
    code: str = Field(min_length=3, max_length=200)


@router.post("/vouchers/lookup")
def voucher_lookup(body: CodeIn, request: Request, user=Depends(require("merchant")), conn=Depends(get_db)):
    """Preview a voucher before redeeming (read-only)."""
    rate_limit(request, "lookup", 60)
    m = my_merchant(conn, user)
    code = qr_parse(body.code)
    v = one(conn.execute("SELECT v.*, d.title, d.type, u.name consumer_name FROM vouchers v JOIN deals d ON d.id=v.deal_id JOIN users u ON u.id=v.consumer_id WHERE v.code=?", (code,)))
    if not v:
        raise not_found("Voucher not found")
    if v["merchant_id"] != m["id"]:
        raise conflict("This voucher belongs to a different merchant", "wrong_merchant")
    return {"code": v["code"], "status": v["status"], "valid_until": v["valid_until"], "deal_title": v["title"],
            "deal_type": v["type"], "consumer_name": v["consumer_name"]}


@router.post("/vouchers/redeem")
def voucher_redeem(body: CodeIn, request: Request, user=Depends(require("merchant")), conn=Depends(get_db)):
    rate_limit(request, "redeem", 60)
    m = my_merchant(conn, user)
    return svc.redeem_voucher(conn, m, body.code)


@router.get("/stats")
def stats(user=Depends(require("merchant")), conn=Depends(get_db)):
    m = my_merchant(conn, user)
    mid = m["id"]
    q = lambda sql, *a: conn.execute(sql, a).fetchone()
    sold = q("SELECT COUNT(*) c, COALESCE(SUM(o.amount + o.points_used),0) rev FROM vouchers v JOIN orders o ON o.id=v.order_id WHERE v.merchant_id=? AND v.status IN('active','redeemed','refund_pending','expired')", mid)
    redeemed = q("SELECT COUNT(*) c FROM vouchers WHERE merchant_id=? AND status='redeemed'", mid)["c"]
    refunded = q("SELECT COUNT(*) c FROM vouchers WHERE merchant_id=? AND status='refunded'", mid)["c"]
    tips = q("SELECT COALESCE(SUM(amount),0) s FROM orders WHERE merchant_id=? AND kind='tip' AND status='paid'", mid)["s"]
    rating = q("SELECT ROUND(AVG(rating),2) a, COUNT(*) c FROM reviews WHERE merchant_id=? AND hidden=0", mid)
    daily = []
    for i in range(6, -1, -1):
        day = (now() - timedelta(days=i)).strftime("%Y-%m-%d")
        r = q("SELECT COUNT(*) c, COALESCE(SUM(o.amount+o.points_used),0) rev FROM vouchers v JOIN orders o ON o.id=v.order_id WHERE v.merchant_id=? AND substr(v.issued_at,1,10)=?", mid, day)
        daily.append({"day": day, "sales": r["c"], "revenue": r["rev"]})
    return {"vouchers_sold": sold["c"], "revenue": round(sold["rev"], 2), "redeemed": redeemed, "refunded": refunded,
            "redemption_rate": round(redeemed / sold["c"], 3) if sold["c"] else 0, "tips": tips,
            "avg_rating": rating["a"], "review_count": rating["c"],
            "active_deals": q("SELECT COUNT(*) c FROM deals WHERE merchant_id=? AND status='active'", mid)["c"],
            "pending_deals": q("SELECT COUNT(*) c FROM deals WHERE merchant_id=? AND status='pending'", mid)["c"],
            "daily": daily}


@router.get("/reviews")
def reviews(user=Depends(require("merchant")), conn=Depends(get_db)):
    m = my_merchant(conn, user)
    return rows(conn.execute("SELECT r.rating,r.comment,r.created_at,u.name FROM reviews r JOIN users u ON u.id=r.consumer_id WHERE r.merchant_id=? AND r.hidden=0 ORDER BY r.id DESC LIMIT 50", (m["id"],)))


@router.get("/payouts")
def payouts(user=Depends(require("merchant")), conn=Depends(get_db)):
    m = my_merchant(conn, user)
    return rows(conn.execute("SELECT * FROM payouts WHERE merchant_id=? ORDER BY id DESC", (m["id"],)))
