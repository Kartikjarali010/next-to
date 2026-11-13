import json
import threading

from app import services as svc
from app.db import connect, one, plus, rows


def stock(h, did):
    return h.conn.execute("SELECT stock_remaining s FROM deals WHERE id=?", (did,)).fetchone()["s"]


def setup(h, stock_n=5, price=100):
    mt, mid, mowner = h.make_merchant()
    did = h.make_deal(mid, stock=stock_n, price=price)
    ct, cid = h.consumer()
    return mt, mid, did, ct, cid


# ---------------------------------------------------------------- create-order
def test_order_reserves_stock_and_is_pending(h):
    _, _, did, ct, _ = setup(h)
    r = h.order(ct, did)
    assert r.status_code == 200
    o = r.json()
    assert o["status"] == "pending" and o["amount"] == 100 and o["voucher"] is None and o["checkout"]["provider"] == "simulated"
    assert stock(h, did) == 4        # reserved at order creation, not at payment


def test_same_idempotency_key_returns_same_order_once(h):
    _, _, did, ct, _ = setup(h)
    a = h.order(ct, did, key="same-key-12345").json()
    b = h.order(ct, did, key="same-key-12345").json()
    assert a["id"] == b["id"]
    assert h.conn.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"] == 1
    assert stock(h, did) == 4


def test_missing_or_short_idempotency_key_rejected(h):
    _, _, did, ct, _ = setup(h)
    r = h.c.post("/api/orders", json={"deal_id": did}, headers=h.hdr(ct))
    assert r.status_code == 400
    assert h.order(ct, did, key="short").status_code == 400


def test_unavailable_deals_cannot_be_ordered(h):
    mt, mid, _, ct, _ = setup(h)
    for kw in ({"status": "pending"}, {"stock": 0}, {"ends_h": -1, "starts_h": -5}):
        did = h.make_deal(mid, **kw)
        r = h.order(ct, did)
        assert r.status_code == 409 and r.json()["error"]["code"] == "deal_unavailable"


def test_last_unit_race_only_one_buyer_wins(h):
    """Negative/concurrency: 6 buyers race for the single remaining unit."""
    mt, mid, _, _, _ = setup(h)
    did = h.make_deal(mid, stock=1)
    users = [h.signup(f"u{i}@t.dev")["user"] for i in range(6)]
    results = []

    def buy(u):
        c = connect()
        try:
            results.append(svc.create_order(c, u, did, f"race-key-{u['id']}-xxxx")["status"])
        except Exception as e:
            results.append(type(e).__name__)
        finally:
            c.close()

    ts = [threading.Thread(target=buy, args=(u,)) for u in users]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert results.count("pending") == 1 and len(results) == 6
    assert stock(h, did) == 0
    assert h.conn.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"] == 1


def test_provider_outage_keeps_order_and_retry_reuses_it(h):
    _, _, did, ct, _ = setup(h)
    h.prov.fail_create = True
    r = h.order(ct, did, key="outage-key-123")
    assert r.status_code == 502 and r.json()["error"]["code"] == "provider_unavailable"
    h.prov.fail_create = False
    r2 = h.order(ct, did, key="outage-key-123")
    assert r2.status_code == 200 and r2.json()["checkout"]["provider"] == "simulated"
    assert h.conn.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"] == 1


def test_risk_scorer_can_block_a_purchase(h):
    from app import providers

    class Block(providers.RiskScorer):
        def score(self, ctx): return {"decision": "block"}
    providers.set_risk(Block())
    _, _, did, ct, _ = setup(h)
    assert h.order(ct, did).status_code == 403
    assert h.conn.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"] == 0


def test_consumer_cannot_see_someone_elses_order(h):
    _, _, did, ct, _ = setup(h)
    o = h.order(ct, did).json()
    other, _ = h.consumer("other@t.dev")
    assert h.c.get(f"/api/orders/{o['id']}", headers=h.hdr(other)).status_code == 404
    assert h.c.get("/api/orders/9999", headers=h.hdr(other)).status_code == 404   # same answer as a missing order


# ---------------------------------------------------------------- webhook
def test_valid_signed_webhook_pays_and_issues_voucher(h):
    _, _, did, ct, _ = setup(h)
    o = h.order(ct, did).json()
    r = h.webhook(o["gateway_order_id"], o["amount"])
    assert r.status_code == 200 and r.json()["order_status"] == "paid"
    o2 = h.c.get(f"/api/orders/{o['id']}", headers=h.hdr(ct)).json()
    assert o2["status"] == "paid" and o2["voucher"]["status"] == "active" and len(o2["voucher"]["code"]) == 10
    assert stock(h, did) == 4        # stays consumed


def test_bad_or_missing_signature_rejected_and_nothing_changes(h):
    _, _, did, ct, _ = setup(h)
    o = h.order(ct, did).json()
    assert h.webhook(o["gateway_order_id"], o["amount"], sig="deadbeef").status_code == 401
    assert h.c.post("/api/webhooks/payment", content=b"{}").status_code == 401
    assert h.c.get(f"/api/orders/{o['id']}", headers=h.hdr(ct)).json()["status"] == "pending"
    assert h.conn.execute("SELECT COUNT(*) c FROM vouchers").fetchone()["c"] == 0
    assert h.conn.execute("SELECT COUNT(*) c FROM audit_log WHERE action='webhook.rejected'").fetchone()["c"] == 2


def test_tampered_body_fails_signature(h):
    _, _, did, ct, _ = setup(h)
    o = h.order(ct, did).json()
    raw, sig = h.prov.make_event(o["gateway_order_id"], o["amount"])
    tampered = raw.replace(str(o["amount"]).encode(), b"1.0")
    r = h.c.post("/api/webhooks/payment", content=tampered, headers={"X-Signature": sig})
    assert r.status_code == 401


def test_duplicate_event_is_idempotent(h):
    _, _, did, ct, _ = setup(h)
    o = h.order(ct, did).json()
    h.webhook(o["gateway_order_id"], o["amount"], event_id="evt-1")
    r = h.webhook(o["gateway_order_id"], o["amount"], event_id="evt-1")
    assert r.json()["status"] == "duplicate"
    assert h.conn.execute("SELECT COUNT(*) c FROM vouchers").fetchone()["c"] == 1
    assert stock(h, did) == 4


def test_failure_event_after_success_does_not_undo_a_paid_order(h):
    """Out-of-order delivery."""
    _, _, did, ct, _ = setup(h)
    o = h.order(ct, did).json()
    h.webhook(o["gateway_order_id"], o["amount"], "success", event_id="e1")
    r = h.webhook(o["gateway_order_id"], o["amount"], "failed", event_id="e2")
    assert r.json()["status"] == "ignored"
    assert h.c.get(f"/api/orders/{o['id']}", headers=h.hdr(ct)).json()["status"] == "paid"


def test_failed_payment_releases_stock(h):
    _, _, did, ct, _ = setup(h)
    o = h.order(ct, did).json()
    assert stock(h, did) == 4
    h.pay(ct, o["id"], "failed")
    assert stock(h, did) == 5
    assert h.c.get(f"/api/orders/{o['id']}", headers=h.hdr(ct)).json()["status"] == "failed"


def test_amount_mismatch_is_not_fulfilled_and_auto_refunded(h):
    _, _, did, ct, _ = setup(h)
    o = h.order(ct, did).json()
    h.pay(ct, o["id"], "wrong_amount")
    o2 = h.c.get(f"/api/orders/{o['id']}", headers=h.hdr(ct)).json()
    assert o2["status"] == "refunded" and o2["voucher"] is None
    assert stock(h, did) == 5


def test_webhook_rolls_back_completely_on_failure(h, monkeypatch):
    """All-or-nothing: if voucher issue explodes, order must stay pending."""
    _, _, did, ct, _ = setup(h)
    o = h.order(ct, did).json()
    monkeypatch.setattr(svc, "_issue_voucher", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    raw, sig = h.prov.make_event(o["gateway_order_id"], o["amount"])
    try:
        svc.handle_webhook(h.conn, raw, sig)
    except RuntimeError:
        pass
    row = h.conn.execute("SELECT status FROM orders WHERE id=?", (o["id"],)).fetchone()
    assert row["status"] == "pending"
    assert h.conn.execute("SELECT COUNT(*) c FROM payments").fetchone()["c"] == 0


# ---------------------------------------------------------------- expiry / late payment / reconcile
def _expire(h, oid):
    h.conn.execute("UPDATE orders SET expires_at=? WHERE id=?", (plus(minutes=-1), oid))
    return svc.expire_pending(h.conn)


def test_unpaid_order_expires_and_returns_stock(h):
    _, _, did, ct, _ = setup(h)
    o = h.order(ct, did).json()
    assert _expire(h, o["id"])["orders"] == 1
    assert stock(h, did) == 5
    assert h.c.get(f"/api/orders/{o['id']}", headers=h.hdr(ct)).json()["status"] == "expired"


def test_late_payment_after_expiry_with_free_stock_still_fulfils(h):
    _, _, did, ct, _ = setup(h)
    o = h.order(ct, did).json()
    _expire(h, o["id"])
    h.pay(ct, o["id"])
    assert h.c.get(f"/api/orders/{o['id']}", headers=h.hdr(ct)).json()["status"] == "paid"
    assert stock(h, did) == 4


def test_late_payment_with_no_stock_is_auto_refunded(h):
    mt, mid, _, ct, _ = setup(h)
    did = h.make_deal(mid, stock=1)
    o = h.order(ct, did).json()
    _expire(h, o["id"])
    other, _ = h.consumer("o2@t.dev")
    h.buy(other, did)                    # someone else takes the freed unit
    h.pay(ct, o["id"])
    o2 = h.c.get(f"/api/orders/{o['id']}", headers=h.hdr(ct)).json()
    assert o2["status"] == "refunded" and o2["voucher"] is None


def test_reconcile_recovers_a_lost_callback(h):
    _, _, did, ct, _ = setup(h)
    o = h.order(ct, did).json()
    assert h.pay(ct, o["id"], "lost").json()["status"] == "callback_lost"
    assert h.c.get(f"/api/orders/{o['id']}", headers=h.hdr(ct)).json()["status"] == "pending"
    res = svc.reconcile(h.conn, older_than_minutes=0)
    assert res["paid"] == 1
    o2 = h.c.get(f"/api/orders/{o['id']}", headers=h.hdr(ct)).json()
    assert o2["status"] == "paid" and o2["voucher"]["status"] == "active"


def test_reconcile_leaves_recent_orders_alone(h):
    _, _, did, ct, _ = setup(h)
    h.order(ct, did)
    assert svc.reconcile(h.conn)["checked"] == 0      # default 15-minute rule
