import threading

from app import services as svc
from app.core import qr_payload
from app.db import connect, plus


def world(h, stock=5, typ="voucher", price=100):
    mt, mid, mo = h.make_merchant()
    did = h.make_deal(mid, stock=stock, price=price, typ=typ)
    ct, cid = h.consumer()
    o = h.buy(ct, did)
    return dict(mt=mt, mid=mid, did=did, ct=ct, cid=cid, order=o, voucher=o["voucher"])


def redeem(h, w, code=None, token=None):
    return h.c.post("/api/merchant/vouchers/redeem", json={"code": code or w["voucher"]["code"]}, headers=h.hdr(token or w["mt"]))


def pts(h, uid):
    return h.conn.execute("SELECT COALESCE(SUM(delta),0) s FROM reward_ledger WHERE user_id=?", (uid,)).fetchone()["s"]


# ---------------------------------------------------------------- redemption
def test_redeem_once_awards_points_at_redemption_not_purchase(h):
    w = world(h)
    assert pts(h, w["cid"]) == 0                       # nothing at purchase
    r = redeem(h, w)
    assert r.status_code == 200 and r.json()["result"] == "redeemed" and r.json()["points_awarded"] == 10
    assert pts(h, w["cid"]) == 10


def test_second_redeem_is_rejected(h):
    w = world(h)
    redeem(h, w)
    r = redeem(h, w)
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_redeemed"
    assert pts(h, w["cid"]) == 10                      # not doubled


def test_qr_payload_accepted_and_forged_qr_rejected(h):
    w = world(h)
    code = w["voucher"]["code"]
    forged = f"NT.{code}.0000000000"
    r = redeem(h, w, code=forged)
    assert r.status_code == 400 and r.json()["error"]["code"] == "bad_qr"
    assert redeem(h, w, code=qr_payload(code)).status_code == 200


def test_another_merchant_cannot_redeem(h):
    w = world(h)
    other, _, _ = h.make_merchant("other@t.dev", name="Other")
    r = redeem(h, w, token=other)
    assert r.status_code == 409 and r.json()["error"]["code"] == "wrong_merchant"
    assert h.c.get("/api/vouchers", headers=h.hdr(w["ct"])).json()[0]["status"] == "active"


def test_unknown_code_404(h):
    w = world(h)
    assert redeem(h, w, code="ZZZZZZZZZZ").status_code == 404


def test_expired_voucher_cannot_be_redeemed(h):
    w = world(h)
    h.conn.execute("UPDATE vouchers SET valid_until=? WHERE id=?", (plus(days=-1), w["voucher"]["id"]))
    r = redeem(h, w)
    assert r.status_code == 409 and r.json()["error"]["code"] == "expired"


def test_voucher_validity_is_independent_of_sale_window(h):
    w = world(h)
    h.conn.execute("UPDATE deals SET ends_at=?, status='ended' WHERE id=?", (plus(hours=-1), w["did"]))
    assert redeem(h, w).status_code == 200            # sale closed, voucher still valid


def test_two_simultaneous_scans_only_one_succeeds(h):
    w = world(h)
    m = h.conn.execute("SELECT * FROM merchants WHERE id=?", (w["mid"],)).fetchone()
    m = dict(m)
    out = []

    def scan():
        c = connect()
        try:
            out.append(svc.redeem_voucher(c, m, w["voucher"]["code"])["result"])
        except Exception as e:
            out.append(getattr(e, "code", type(e).__name__))
        finally:
            c.close()

    ts = [threading.Thread(target=scan) for _ in range(5)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert out.count("redeemed") == 1 and out.count("already_redeemed") == 4
    assert pts(h, w["cid"]) == 10


def test_redeem_requires_merchant_role(h):
    w = world(h)
    r = h.c.post("/api/merchant/vouchers/redeem", json={"code": w["voucher"]["code"]}, headers=h.hdr(w["ct"]))
    assert r.status_code == 403


# ---------------------------------------------------------------- refunds
def refund(h, w, reason="changed mind"):
    return h.c.post("/api/refunds", json={"voucher_id": w["voucher"]["id"], "reason": reason}, headers=h.hdr(w["ct"]))


def decide(h, admin, rid, decision, reason=None):
    return h.c.post(f"/api/admin/refunds/{rid}/decision", json={"decision": decision, "reason": reason}, headers=h.hdr(admin))


def test_refund_request_blocks_redemption_while_pending(h):
    w = world(h)
    r = refund(h, w)
    assert r.status_code == 200
    assert redeem(h, w).status_code == 409           # voucher is refund_pending
    assert h.c.get("/api/vouchers", headers=h.hdr(w["ct"])).json()[0]["status"] == "refund_pending"


def test_cannot_request_refund_for_redeemed_voucher_or_twice(h):
    w = world(h)
    assert refund(h, w).status_code == 200
    assert refund(h, w).status_code == 409           # already refund_pending


def test_refund_after_redemption_not_allowed(h):
    w = world(h)
    redeem(h, w)
    r = refund(h, w)
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_refundable"


def test_only_admin_can_decide_refund(h):
    w = world(h)
    rid = refund(h, w).json()["refund_id"]
    assert decide(h, w["ct"], rid, "approve").status_code == 403
    assert decide(h, w["mt"], rid, "approve").status_code == 403


def test_approved_refund_refunds_order_voucher_and_restores_stock(h):
    w = world(h, stock=5)
    rid = refund(h, w).json()["refund_id"]
    admin = h.make_admin()
    assert decide(h, admin, rid, "approve").json()["status"] == "processed"
    assert h.c.get(f"/api/orders/{w['order']['id']}", headers=h.hdr(w["ct"])).json()["status"] == "refunded"
    assert h.c.get("/api/vouchers", headers=h.hdr(w["ct"])).json()[0]["status"] == "refunded"
    assert h.conn.execute("SELECT stock_remaining s FROM deals WHERE id=?", (w["did"],)).fetchone()["s"] == 5
    assert decide(h, admin, rid, "approve").status_code == 409     # double refund impossible


def test_reject_needs_reason_and_reactivates_voucher(h):
    w = world(h)
    rid = refund(h, w).json()["refund_id"]
    admin = h.make_admin()
    assert decide(h, admin, rid, "reject").status_code == 400
    assert decide(h, admin, rid, "reject", "Policy: used soon").json()["status"] == "rejected"
    assert h.c.get("/api/vouchers", headers=h.hdr(w["ct"])).json()[0]["status"] == "active"
    assert redeem(h, w).status_code == 200


def test_provider_failure_leaves_refund_approved_and_retry_completes(h):
    w = world(h)
    rid = refund(h, w).json()["refund_id"]
    admin = h.make_admin()
    h.prov.fail_refund = True
    r = decide(h, admin, rid, "approve")
    assert r.status_code == 502
    assert h.conn.execute("SELECT status FROM refunds WHERE id=?", (rid,)).fetchone()["status"] == "approved"
    assert h.conn.execute("SELECT status FROM orders WHERE id=?", (w["order"]["id"],)).fetchone()["status"] == "paid"   # no money moved
    h.prov.fail_refund = False
    assert decide(h, admin, rid, "approve").json()["status"] == "processed"


def test_refund_with_points_restores_points(h):
    mt, mid, _ = h.make_merchant()
    did = h.make_deal(mid, price=100)
    ct, cid = h.consumer()
    h.conn.execute("INSERT INTO reward_ledger(user_id,delta,reason,created_at) VALUES(?,40,'earn','x')", (cid,))
    o = h.order(ct, did, use_points=30).json()
    assert o["amount"] == 70 and pts(h, cid) == 10
    h.pay(ct, o["id"])
    v = h.c.get("/api/vouchers", headers=h.hdr(ct)).json()[0]
    rid = h.c.post("/api/refunds", json={"voucher_id": v["id"]}, headers=h.hdr(ct)).json()["refund_id"]
    decide(h, h.make_admin(), rid, "approve")
    assert pts(h, cid) == 40


def test_points_discount_is_capped_at_half_price_and_balance(h):
    mt, mid, _ = h.make_merchant()
    did = h.make_deal(mid, price=100)
    ct, cid = h.consumer()
    h.conn.execute("INSERT INTO reward_ledger(user_id,delta,reason,created_at) VALUES(?,500,'earn','x')", (cid,))
    r = h.order(ct, did, use_points=51)
    assert r.status_code == 400 and r.json()["error"]["code"] == "bad_points"
    assert h.order(ct, did, use_points=50).json()["amount"] == 50


# ---------------------------------------------------------------- bookings
def test_service_booking_capacity_cancel_and_completion(h):
    mt, mid, _ = h.make_merchant()
    did = h.make_deal(mid, typ="service", stock=5)
    slot = h.make_slot(did, hours_ahead=24, capacity=1)
    a, _ = h.consumer("a@t.dev"); b, _ = h.consumer("b@t.dev")
    va = h.buy(a, did)["voucher"]; vb = h.buy(b, did)["voucher"]
    r1 = h.c.post("/api/bookings", json={"voucher_id": va["id"], "slot_id": slot}, headers=h.hdr(a))
    assert r1.status_code == 200
    r2 = h.c.post("/api/bookings", json={"voucher_id": vb["id"], "slot_id": slot}, headers=h.hdr(b))
    assert r2.status_code == 409 and r2.json()["error"]["code"] == "slot_full"     # capacity never exceeded
    assert h.c.post("/api/bookings", json={"voucher_id": va["id"], "slot_id": slot}, headers=h.hdr(a)).status_code == 409   # one booking/voucher
    assert h.c.post(f"/api/bookings/{r1.json()['booking_id']}/cancel", headers=h.hdr(a)).status_code == 200
    assert h.c.post("/api/bookings", json={"voucher_id": vb["id"], "slot_id": slot}, headers=h.hdr(b)).status_code == 200   # slot freed
    h.c.post("/api/merchant/vouchers/redeem", json={"code": vb["code"]}, headers=h.hdr(mt))
    assert h.conn.execute("SELECT status FROM bookings WHERE voucher_id=?", (vb["id"],)).fetchone()["status"] == "completed"


def test_booking_for_other_deals_slot_or_other_users_voucher_rejected(h):
    mt, mid, _ = h.make_merchant()
    d1 = h.make_deal(mid, typ="service"); d2 = h.make_deal(mid, typ="service", title="Other")
    s2 = h.make_slot(d2)
    a, _ = h.consumer("a@t.dev"); b, _ = h.consumer("b@t.dev")
    va = h.buy(a, d1)["voucher"]
    assert h.c.post("/api/bookings", json={"voucher_id": va["id"], "slot_id": s2}, headers=h.hdr(a)).status_code == 404
    s1 = h.make_slot(d1)
    assert h.c.post("/api/bookings", json={"voucher_id": va["id"], "slot_id": s1}, headers=h.hdr(b)).status_code == 404


def test_late_cancellation_blocked(h):
    mt, mid, _ = h.make_merchant()
    did = h.make_deal(mid, typ="service")
    slot = h.make_slot(did, hours_ahead=1)
    a, _ = h.consumer("a@t.dev")
    va = h.buy(a, did)["voucher"]
    bid = h.c.post("/api/bookings", json={"voucher_id": va["id"], "slot_id": slot}, headers=h.hdr(a)).json()["booking_id"]
    r = h.c.post(f"/api/bookings/{bid}/cancel", headers=h.hdr(a))
    assert r.status_code == 409 and r.json()["error"]["code"] == "too_late"


# ---------------------------------------------------------------- reviews and tips
def test_review_only_after_redemption_once_per_voucher(h):
    w = world(h)
    body = {"voucher_id": w["voucher"]["id"], "rating": 5, "comment": "great"}
    assert h.c.post("/api/reviews", json=body, headers=h.hdr(w["ct"])).status_code == 403     # not redeemed yet
    redeem(h, w)
    assert h.c.post("/api/reviews", json=body, headers=h.hdr(w["ct"])).status_code == 200
    r = h.c.post("/api/reviews", json=body, headers=h.hdr(w["ct"]))
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_reviewed"


def test_review_rating_bounds_validated(h):
    w = world(h)
    redeem(h, w)
    r = h.c.post("/api/reviews", json={"voucher_id": w["voucher"]["id"], "rating": 6}, headers=h.hdr(w["ct"]))
    assert r.status_code == 422


def test_tip_is_an_order_without_a_voucher_and_goes_to_payout(h):
    w = world(h)
    redeem(h, w)
    r = h.c.post("/api/reviews", json={"voucher_id": w["voucher"]["id"], "rating": 5, "tip": 20}, headers=h.hdr(w["ct"])).json()
    tip = r["tip_order"]
    assert tip["amount"] == 20 and tip["checkout"]
    assert h.pay(w["ct"], tip["id"]).json()["order_status"] == "paid"
    assert h.conn.execute("SELECT COUNT(*) c FROM vouchers").fetchone()["c"] == 1
    admin = h.make_admin()
    h.c.post("/api/admin/payouts/run", json={}, headers=h.hdr(admin))
    p = h.c.get("/api/merchant/payouts", headers=h.hdr(w["mt"])).json()[0]
    assert p["gross"] == 120 and p["fee"] == 10 and p["net"] == 110     # 10% fee on the deal only, tip passes through
