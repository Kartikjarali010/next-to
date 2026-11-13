"""Consumer-facing API: discovery, orders, webhook, vouchers, refunds, bookings, reviews, rewards."""
import math

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field

from .. import services as svc
from ..core import AppError, bad, conflict, forbidden, not_found, rate_limit, require
from ..db import audit, cfg, get_db, now, now_iso, one, parse, points_balance, rows, tx
from ..providers import get_provider, SimulatedProvider
from ..ranking import CATEGORIES, haversine_m, score_deal

router = APIRouter(prefix="/api", tags=["consumer"])

AREAS = [  # location fallback when device GPS is denied (NFR-7)
    {"name": "Kattigenahalli / REVA University", "lat": 13.1147, "lng": 77.6340},
    {"name": "Yelahanka New Town", "lat": 13.1007, "lng": 77.5963},
    {"name": "Jakkur", "lat": 13.0780, "lng": 77.6070},
    {"name": "Hebbal", "lat": 13.0358, "lng": 77.5970},
    {"name": "Bengaluru Centre (MG Road)", "lat": 12.9756, "lng": 77.6070},
]


@router.get("/meta")
def meta():
    return {"categories": CATEGORIES, "areas": AREAS}


def _deal_card(d: dict) -> dict:
    return {k: d[k] for k in d if k not in ("m_lat", "m_lng")}


@router.get("/deals/nearby")
def deals_nearby(lat: float | None = None, lng: float | None = None, area: str | None = None,
                 radius_km: float = 5, category: str | None = None, q: str | None = None,
                 cursor: int = 0, limit: int = 20, conn=Depends(get_db)):
    if (lat is None or lng is None):
        a = next((a for a in AREAS if a["name"] == area), AREAS[0])  # fallback: chosen area or default city point
        lat, lng = a["lat"], a["lng"]
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise bad("Invalid coordinates", "bad_coords")
    limit = max(1, min(limit, 50))
    if category and category not in CATEGORIES:
        raise bad("Unknown category")
    widened = False
    radius = max(0.2, min(radius_km, 50))
    results = _search(conn, lat, lng, radius, category, q)
    if not results and radius < 50:           # cold-start: automatically widen the radius
        for r in (radius * 3, 25, 50):
            results = _search(conn, lat, lng, r, category, q)
            if results:
                radius, widened = r, True
                break
    page = results[cursor:cursor + limit]
    return {"deals": page, "total": len(results), "radius_km": radius, "widened": widened,
            "origin": {"lat": lat, "lng": lng}, "next_cursor": cursor + limit if cursor + limit < len(results) else None}


def _search(conn, lat, lng, radius_km, category, q):
    radius_m = radius_km * 1000
    dlat = radius_km / 111.0
    dlng = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.01))
    n = now_iso()
    sql = ("SELECT d.*, m.name merchant_name, m.address merchant_address, m.lat m_lat, m.lng m_lng, "
           "COALESCE((SELECT ROUND(AVG(rating),1) FROM reviews r WHERE r.merchant_id=m.id AND r.hidden=0),NULL) rating, "
           "(SELECT COUNT(*) FROM reviews r WHERE r.merchant_id=m.id AND r.hidden=0) review_count "
           "FROM deals d JOIN merchants m ON m.id=d.merchant_id "
           "WHERE d.status='active' AND m.verification_status='approved' AND d.starts_at<=? AND d.ends_at>=? AND d.stock_remaining>0 "
           "AND m.lat BETWEEN ? AND ? AND m.lng BETWEEN ? AND ?")
    args = [n, n, lat - dlat, lat + dlat, lng - dlng, lng + dlng]
    if q:
        sql += " AND (d.title LIKE ? OR d.description LIKE ? OR m.name LIKE ?)"
        args += [f"%{q}%"] * 3
    w = cfg(conn, "ranking_weights")
    now_dt = now()
    out = []
    for d in rows(conn.execute(sql, args)):
        dist = haversine_m(lat, lng, d["m_lat"], d["m_lng"])
        if dist > radius_m:
            continue
        age_h = (now_dt - parse(d["published_at"] or d["created_at"])).total_seconds() / 3600
        s = score_deal(dist_m=dist, radius_m=radius_m, deal_cat=d["category"], selected_cat=category, age_hours=age_h,
                       ends_at=parse(d["ends_at"]), now=now_dt, stock=d["stock_remaining"], weights=w)
        if category and s["parts"]["category"] == 0:
            continue
        d["distance_m"] = round(dist)
        d["score"], d["score_parts"] = s["score"], s["parts"]
        d["lat"], d["lng"] = d.pop("m_lat"), d.pop("m_lng")
        out.append(d)
    out.sort(key=lambda x: (-x["score"], x["distance_m"]))
    return out


@router.get("/shops/{shop_id}")
def shop_profile(shop_id: int, conn=Depends(get_db)):
    """Public shopper-facing merchant profile: details, live deals and reviews (verified shops only)."""
    m = one(conn.execute("SELECT id,name,category,address,lat,lng,description,hours,image_url FROM merchants WHERE id=? AND verification_status='approved'", (shop_id,)))
    if not m:
        raise not_found("Shop not found")
    n = now_iso()
    m["deals"] = rows(conn.execute(
        "SELECT id,title,category,type,price,original_price,stock_remaining,ends_at,image_url FROM deals "
        "WHERE merchant_id=? AND status='active' AND starts_at<=? AND ends_at>=? AND stock_remaining>0 ORDER BY id DESC", (shop_id, n, n)))
    m["reviews"] = rows(conn.execute(
        "SELECT r.rating,r.comment,r.created_at,u.name FROM reviews r JOIN users u ON u.id=r.consumer_id "
        "WHERE r.merchant_id=? AND r.hidden=0 ORDER BY r.id DESC LIMIT 20", (shop_id,)))
    agg = one(conn.execute("SELECT ROUND(AVG(rating),1) a, COUNT(*) c FROM reviews WHERE merchant_id=? AND hidden=0", (shop_id,)))
    m["rating"], m["review_count"] = agg["a"], agg["c"]
    m["redeemed_count"] = conn.execute("SELECT COUNT(*) c FROM vouchers WHERE merchant_id=? AND status='redeemed'", (shop_id,)).fetchone()["c"]
    return m


@router.get("/deals/{deal_id}")
def deal_detail(deal_id: int, conn=Depends(get_db)):
    d = one(conn.execute(
        "SELECT d.*, m.name merchant_name, m.address merchant_address, m.lat, m.lng, m.description merchant_description, m.image_url merchant_image, m.hours merchant_hours "
        "FROM deals d JOIN merchants m ON m.id=d.merchant_id WHERE d.id=? AND d.status='active'", (deal_id,)))
    if not d:
        raise not_found("Deal not found")
    d["slots"] = rows(conn.execute("SELECT id,starts_at,capacity,booked_count FROM slots WHERE deal_id=? AND starts_at>? ORDER BY starts_at", (deal_id, now_iso()))) if d["type"] == "service" else []
    d["reviews"] = rows(conn.execute(
        "SELECT r.rating,r.comment,r.created_at,u.name FROM reviews r JOIN users u ON u.id=r.consumer_id "
        "JOIN deals dd ON dd.merchant_id=r.merchant_id WHERE dd.id=? AND r.hidden=0 ORDER BY r.created_at DESC LIMIT 10", (deal_id,)))
    return d


# ---------------------------------------------------------------- orders
class OrderIn(BaseModel):
    deal_id: int
    use_points: int = 0


@router.post("/orders")
def create_order(body: OrderIn, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                 user=Depends(require("consumer")), conn=Depends(get_db)):
    if not idempotency_key:
        raise bad("Idempotency-Key header is required", "missing_idempotency_key")
    return svc.create_order(conn, user, body.deal_id, idempotency_key, body.use_points)


@router.get("/orders")
def my_orders(user=Depends(require("consumer")), conn=Depends(get_db)):
    return [svc.order_view(conn, o) for o in rows(conn.execute("SELECT * FROM orders WHERE consumer_id=? ORDER BY id DESC", (user["id"],)))]


@router.get("/orders/{oid}")
def get_order(oid: int, user=Depends(require("consumer")), conn=Depends(get_db)):
    o = one(conn.execute("SELECT * FROM orders WHERE id=? AND consumer_id=?", (oid, user["id"])))
    if not o:
        raise not_found("Order not found")  # same answer for someone else's order
    return svc.order_view(conn, o)


@router.post("/webhooks/payment")
async def payment_webhook(request: Request, x_signature: str | None = Header(default=None, alias="X-Signature"), conn=Depends(get_db)):
    """Called by the PSP, not by a user: no JWT, authenticated solely by the signature over the raw body."""
    raw = await request.body()
    return svc.handle_webhook(conn, raw, x_signature)


class SimPay(BaseModel):
    order_id: int
    outcome: str = "success"   # success | failed | wrong_amount | lost


@router.post("/dev/simulate-payment")
def simulate_payment(body: SimPay, user=Depends(require("consumer")), conn=Depends(get_db)):
    """DEV ONLY: stands in for the UPI app + PSP. It builds a *signed* callback and sends it through the
    real webhook code path. Disabled in production."""
    import os
    if os.environ.get("NEXTTO_ENV") == "production":
        raise not_found()
    prov = get_provider()
    if not isinstance(prov, SimulatedProvider):
        raise bad("Simulation only works with the simulated provider")
    o = one(conn.execute("SELECT * FROM orders WHERE id=? AND consumer_id=?", (body.order_id, user["id"])))
    if not o or not o["gateway_order_id"]:
        raise not_found("Order not found")
    if body.outcome == "lost":  # payment succeeded at the PSP but the webhook never arrives
        prov.orders[o["gateway_order_id"]] = {"amount": o["amount"], "status": "paid"}
        return {"status": "callback_lost", "hint": "Run reconciliation to recover this payment"}
    amount = o["amount"] + (1 if body.outcome == "wrong_amount" else 0)
    st = "failed" if body.outcome == "failed" else "success"
    raw, sig = prov.make_event(o["gateway_order_id"], amount, st)
    return svc.handle_webhook(conn, raw, sig)


# ---------------------------------------------------------------- vouchers / refunds
@router.get("/vouchers")
def my_vouchers(status: str | None = None, user=Depends(require("consumer")), conn=Depends(get_db)):
    svc.expire_pending(conn)
    sql, args = "SELECT * FROM vouchers WHERE consumer_id=?", [user["id"]]
    if status:
        sql += " AND status=?"
        args.append(status)
    return [svc.voucher_view(conn, v) for v in rows(conn.execute(sql + " ORDER BY id DESC", args))]


@router.get("/vouchers/{vid}")
def get_voucher(vid: int, user=Depends(require("consumer")), conn=Depends(get_db)):
    v = one(conn.execute("SELECT * FROM vouchers WHERE id=? AND consumer_id=?", (vid, user["id"])))
    if not v:
        raise not_found("Voucher not found")
    return svc.voucher_view(conn, v)


class RefundIn(BaseModel):
    voucher_id: int
    reason: str = ""


@router.post("/refunds")
def request_refund(body: RefundIn, user=Depends(require("consumer")), conn=Depends(get_db)):
    return svc.request_refund(conn, user, body.voucher_id, body.reason)


@router.get("/refunds")
def my_refunds(user=Depends(require("consumer")), conn=Depends(get_db)):
    return rows(conn.execute("SELECT r.* FROM refunds r JOIN orders o ON o.id=r.order_id WHERE o.consumer_id=? ORDER BY r.id DESC", (user["id"],)))


# ---------------------------------------------------------------- bookings
class BookingIn(BaseModel):
    voucher_id: int
    slot_id: int


@router.get("/deals/{deal_id}/slots")
def slots_list(deal_id: int, conn=Depends(get_db)):
    return rows(conn.execute("SELECT id,starts_at,capacity,booked_count FROM slots WHERE deal_id=? AND starts_at>? ORDER BY starts_at", (deal_id, now_iso())))


@router.post("/bookings")
def booking_create(body: BookingIn, user=Depends(require("consumer")), conn=Depends(get_db)):
    return svc.create_booking(conn, user, body.voucher_id, body.slot_id)


@router.post("/bookings/{bid}/cancel")
def booking_cancel(bid: int, user=Depends(require("consumer")), conn=Depends(get_db)):
    return svc.cancel_booking(conn, user, bid)


# ---------------------------------------------------------------- reviews / tips / rewards
class ReviewIn(BaseModel):
    voucher_id: int
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=1000)
    tip: float = Field(default=0, ge=0, le=5000)


@router.post("/reviews")
def review_create(body: ReviewIn, user=Depends(require("consumer")), conn=Depends(get_db)):
    v = one(conn.execute("SELECT * FROM vouchers WHERE id=? AND consumer_id=?", (body.voucher_id, user["id"])))
    if not v:
        raise not_found("Voucher not found")
    if v["status"] != "redeemed":
        raise forbidden("You can review only after the voucher has been redeemed")
    tip_order = None
    with tx(conn):
        if conn.execute("SELECT 1 FROM reviews WHERE voucher_id=?", (v["id"],)).fetchone():
            raise conflict("You already reviewed this voucher", "already_reviewed")
        rid = conn.execute("INSERT INTO reviews(voucher_id,consumer_id,merchant_id,rating,comment,created_at) VALUES(?,?,?,?,?,?)",
                           (v["id"], user["id"], v["merchant_id"], body.rating, body.comment.strip(), now_iso())).lastrowid
        audit(conn, user["id"], "review.created", "review", rid, None, {"rating": body.rating})
        if body.tip > 0:  # a tip is an order of kind 'tip': same payment path, no voucher
            oid = conn.execute(
                "INSERT INTO orders(consumer_id,merchant_id,kind,ref_voucher_id,amount,status,idempotency_key,created_at,expires_at) VALUES(?,?, 'tip',?,?, 'pending',?,?,?)",
                (user["id"], v["merchant_id"], v["id"], round(body.tip, 2), f"tip-{v['id']}", now_iso(), None)).lastrowid
            tip_order = oid
    out = {"review_id": rid}
    if tip_order:
        o = one(conn.execute("SELECT * FROM orders WHERE id=?", (tip_order,)))
        out["tip_order"] = svc._resume(conn, o)
    return out


@router.get("/rewards")
def rewards(user=Depends(require("consumer")), conn=Depends(get_db)):
    return {"balance": points_balance(conn, user["id"]),
            "point_value_rupees": cfg(conn, "point_value_rupees"),
            "max_discount_pct": cfg(conn, "max_points_discount_pct"),
            "ledger": rows(conn.execute("SELECT delta,reason,ref,created_at FROM reward_ledger WHERE user_id=? ORDER BY id DESC LIMIT 50", (user["id"],)))}


@router.get("/notifications")
def notifications(user=Depends(require("consumer", "merchant", "admin", "merchant_applicant")), conn=Depends(get_db)):
    return rows(conn.execute("SELECT id,type,message,payload,read,created_at FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 30", (user["id"],)))


@router.post("/notifications/read")
def notifications_read(user=Depends(require("consumer", "merchant", "admin", "merchant_applicant")), conn=Depends(get_db)):
    conn.execute("UPDATE notifications SET read=1 WHERE user_id=?", (user["id"],))
    return {"ok": True}
