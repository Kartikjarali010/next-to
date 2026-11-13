import jwt

from app.core import JWT_SECRET


# ---------------------------------------------------------------- auth
def test_signup_login_me(h):
    s = h.signup("new@t.dev", "New User")
    assert s["user"]["role"] == "consumer" and s["user"]["points"] == 0
    tok = h.login("new@t.dev")
    me = h.c.get("/api/auth/me", headers=h.hdr(tok)).json()
    assert me["email"] == "new@t.dev"


def test_duplicate_email_bad_email_short_password(h):
    h.signup("dup@t.dev")
    assert h.c.post("/api/auth/signup", json={"email": "DUP@t.dev", "password": "secret1", "name": "X Y"}).status_code == 409
    assert h.c.post("/api/auth/signup", json={"email": "nope", "password": "secret1", "name": "X Y"}).status_code == 400
    assert h.c.post("/api/auth/signup", json={"email": "ok@t.dev", "password": "123", "name": "X Y"}).status_code == 422


def test_wrong_password_and_unknown_user_same_error(h):
    h.signup("a@t.dev")
    r1 = h.c.post("/api/auth/login", json={"email": "a@t.dev", "password": "wrong-pass"})
    r2 = h.c.post("/api/auth/login", json={"email": "ghost@t.dev", "password": "wrong-pass"})
    assert r1.status_code == r2.status_code == 401 and r1.json() == r2.json()


def test_passwords_are_hashed_not_stored(h):
    h.signup("a@t.dev", password="supersecret")
    ph = h.conn.execute("SELECT password_hash FROM users WHERE email='a@t.dev'").fetchone()["password_hash"]
    assert "supersecret" not in ph and "$" in ph


def test_merchant_signup_requires_business_and_starts_as_applicant(h):
    r = h.c.post("/api/auth/signup", json={"email": "m@t.dev", "password": "secret1", "name": "M O", "account_type": "merchant"})
    assert r.status_code == 400
    tok, mid, _ = h.make_merchant("m2@t.dev", approved=False)
    me = h.c.get("/api/auth/me", headers=h.hdr(tok)).json()
    assert me["role"] == "merchant_applicant" and me["merchant"]["verification_status"] == "pending"


def test_unverified_merchant_cannot_create_deals(h):
    tok, mid, _ = h.make_merchant("m3@t.dev", approved=False)
    r = h.c.post("/api/merchant/deals", json={}, headers=h.hdr(tok))
    assert r.status_code == 403


def test_no_token_or_garbage_token_is_401(h):
    assert h.c.get("/api/orders").status_code == 401
    assert h.c.get("/api/orders", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_role_claim_cannot_be_forged_without_secret(h):
    tok, uid = h.consumer()
    forged = jwt.encode({"sub": str(uid), "app_role": "admin", "exp": 9999999999}, "wrong-secret-wrong-secret-1234567", algorithm="HS256")
    assert h.c.get("/api/admin/stats", headers=h.hdr(forged)).status_code == 401
    assert h.c.get("/api/admin/stats", headers=h.hdr(tok)).status_code == 403


def test_suspended_user_is_locked_out(h):
    tok, uid = h.consumer()
    admin = h.make_admin()
    h.c.post(f"/api/admin/users/{uid}/suspend?suspended=true", headers=h.hdr(admin))
    assert h.c.get("/api/auth/me", headers=h.hdr(tok)).status_code == 403
    assert h.c.post("/api/auth/login", json={"email": "c@t.dev", "password": "secret1"}).status_code == 401


# ---------------------------------------------------------------- role separation (RBAC)
def test_role_matrix(h):
    ct, _ = h.consumer()
    mt, mid, _ = h.make_merchant()
    admin = h.make_admin()
    assert h.c.get("/api/merchant/stats", headers=h.hdr(ct)).status_code == 403
    assert h.c.get("/api/merchant/stats", headers=h.hdr(admin)).status_code == 403
    assert h.c.get("/api/orders", headers=h.hdr(mt)).status_code == 403
    assert h.c.get("/api/admin/audit", headers=h.hdr(mt)).status_code == 403
    assert h.c.get("/api/admin/audit", headers=h.hdr(ct)).status_code == 403
    assert h.c.get("/api/admin/audit", headers=h.hdr(admin)).status_code == 200


# ---------------------------------------------------------------- deal approval workflow
DEAL = {"title": "Brunch for two", "description": "x", "category": "cafe", "type": "voucher", "price": 300, "original_price": 600,
        "stock_total": 10, "starts_at": "2026-01-01T00:00:00Z", "ends_at": "2099-01-01T00:00:00Z", "redeem_window_days": 30}


def test_deal_lifecycle_and_merchant_cannot_self_approve(h):
    mt, mid, _ = h.make_merchant()
    admin = h.make_admin()
    d = h.c.post("/api/merchant/deals", json=DEAL, headers=h.hdr(mt)).json()
    assert d["status"] == "draft"
    # a draft is invisible to shoppers
    assert h.c.get(f"/api/deals/{d['id']}").status_code == 404
    assert h.c.post(f"/api/merchant/deals/{d['id']}/submit", headers=h.hdr(mt)).json()["status"] == "pending"
    # merchant has no way to activate
    assert h.c.post(f"/api/admin/deals/{d['id']}/decision", json={"decision": "approve"}, headers=h.hdr(mt)).status_code == 403
    assert h.c.post(f"/api/admin/deals/{d['id']}/decision", json={"decision": "reject"}, headers=h.hdr(admin)).status_code == 400   # reason required
    assert h.c.post(f"/api/admin/deals/{d['id']}/decision", json={"decision": "approve"}, headers=h.hdr(admin)).json()["status"] == "active"
    assert h.c.get(f"/api/deals/{d['id']}").status_code == 200
    # editing a live deal sends it back to pending (cannot change a live deal without review)
    upd = dict(DEAL, price=250)
    assert h.c.put(f"/api/merchant/deals/{d['id']}", json=upd, headers=h.hdr(mt)).json()["status"] == "pending"
    assert h.c.get(f"/api/deals/{d['id']}").status_code == 404


def test_deal_validation(h):
    mt, _, _ = h.make_merchant()
    bad = lambda **kw: h.c.post("/api/merchant/deals", json=dict(DEAL, **kw), headers=h.hdr(mt)).status_code
    assert bad(price=0) == 422
    assert bad(original_price=100, price=300) == 400
    assert bad(ends_at="2020-01-01T00:00:00Z") == 400
    assert bad(category="nonsense") == 400
    assert bad(stock_total=0) == 422


def test_merchant_cannot_touch_other_merchants_deal(h):
    m1, mid1, _ = h.make_merchant("m1@t.dev")
    m2, _, _ = h.make_merchant("m2@t.dev", name="Other")
    d = h.c.post("/api/merchant/deals", json=DEAL, headers=h.hdr(m1)).json()
    assert h.c.put(f"/api/merchant/deals/{d['id']}", json=DEAL, headers=h.hdr(m2)).status_code == 404
    assert h.c.post(f"/api/merchant/deals/{d['id']}/submit", headers=h.hdr(m2)).status_code == 404


def test_merchant_approval_grants_role_after_token_refresh(h):
    s = h.signup("biz@t.dev", "Biz", "merchant", {"name": "Biz", "category": "cafe", "address": "x road", "lat": 13.1, "lng": 77.6})
    tok, mid = s["token"], s["user"]["merchant"]["id"]
    admin = h.make_admin()
    assert h.c.post(f"/api/admin/merchants/{mid}/decision", json={"decision": "reject"}, headers=h.hdr(admin)).status_code == 400
    h.c.post(f"/api/admin/merchants/{mid}/decision", json={"decision": "approve"}, headers=h.hdr(admin))
    assert h.c.get("/api/merchant/stats", headers=h.hdr(tok)).status_code == 403          # old token still says applicant
    new = h.c.post("/api/auth/refresh", headers=h.hdr(tok)).json()["token"]
    assert h.c.get("/api/merchant/stats", headers=h.hdr(new)).status_code == 200


# ---------------------------------------------------------------- admin: payouts, audit, moderation
def test_payout_run_is_idempotent_and_release_is_once(h):
    mt, mid, _ = h.make_merchant()
    did = h.make_deal(mid, price=200)
    ct, _ = h.consumer()
    v = h.buy(ct, did)["voucher"]
    h.c.post("/api/merchant/vouchers/redeem", json={"code": v["code"]}, headers=h.hdr(mt))
    admin = h.make_admin()
    r1 = h.c.post("/api/admin/payouts/run", json={}, headers=h.hdr(admin)).json()
    r2 = h.c.post("/api/admin/payouts/run", json={}, headers=h.hdr(admin)).json()
    assert len(r1["created"]) == 1 and r2["created"] == []       # voucher cannot be settled twice
    p = h.c.get("/api/admin/payouts", headers=h.hdr(admin)).json()[0]
    assert (p["gross"], p["fee"], p["net"]) == (200, 20, 180)
    pid = r1["created"][0]
    assert h.c.post(f"/api/admin/payouts/{pid}/release", headers=h.hdr(admin)).status_code == 200
    assert h.c.post(f"/api/admin/payouts/{pid}/release", headers=h.hdr(admin)).status_code == 409


def test_refunded_vouchers_are_not_paid_out(h):
    mt, mid, _ = h.make_merchant()
    did = h.make_deal(mid)
    ct, _ = h.consumer()
    v = h.buy(ct, did)["voucher"]
    rid = h.c.post("/api/refunds", json={"voucher_id": v["id"]}, headers=h.hdr(ct)).json()["refund_id"]
    admin = h.make_admin()
    h.c.post(f"/api/admin/refunds/{rid}/decision", json={"decision": "approve"}, headers=h.hdr(admin))
    assert h.c.post("/api/admin/payouts/run", json={}, headers=h.hdr(admin)).json()["created"] == []


def test_audit_log_records_the_whole_journey(h):
    mt, mid, _ = h.make_merchant()
    did = h.make_deal(mid)
    ct, _ = h.consumer()
    v = h.buy(ct, did)["voucher"]
    h.c.post("/api/merchant/vouchers/redeem", json={"code": v["code"]}, headers=h.hdr(mt))
    admin = h.make_admin()
    actions = {a["action"] for a in h.c.get("/api/admin/audit?limit=200", headers=h.hdr(admin)).json()}
    assert {"order.created", "order.paid", "voucher.issued", "voucher.redeemed", "user.signup"} <= actions


def test_admin_stats_and_hide_review(h):
    mt, mid, _ = h.make_merchant()
    did = h.make_deal(mid)
    ct, _ = h.consumer()
    v = h.buy(ct, did)["voucher"]
    h.c.post("/api/merchant/vouchers/redeem", json={"code": v["code"]}, headers=h.hdr(mt))
    rid = h.c.post("/api/reviews", json={"voucher_id": v["id"], "rating": 1, "comment": "spam"}, headers=h.hdr(ct)).json()["review_id"]
    admin = h.make_admin()
    st = h.c.get("/api/admin/stats", headers=h.hdr(admin)).json()
    assert st["vouchers_sold"] == 1 and st["redeemed"] == 1 and st["gmv"] == 100 and st["redemption_rate"] == 1
    assert h.c.get("/api/merchant/reviews", headers=h.hdr(mt)).json()[0]["comment"] == "spam"
    h.c.post(f"/api/admin/reviews/{rid}/hide", headers=h.hdr(admin))
    assert h.c.get("/api/merchant/reviews", headers=h.hdr(mt)).json() == []


def test_merchant_dashboard_stats(h):
    mt, mid, _ = h.make_merchant()
    did = h.make_deal(mid, price=100)
    ct, _ = h.consumer()
    h.c.post("/api/merchant/vouchers/redeem", json={"code": h.buy(ct, did)["voucher"]["code"]}, headers=h.hdr(mt))
    h.buy(ct, did)
    s = h.c.get("/api/merchant/stats", headers=h.hdr(mt)).json()
    assert s["vouchers_sold"] == 2 and s["revenue"] == 200 and s["redeemed"] == 1 and s["redemption_rate"] == 0.5
    assert len(s["daily"]) == 7 and s["daily"][-1]["sales"] == 2


def test_validation_errors_use_common_error_shape(h):
    r = h.c.post("/api/auth/login", json={})
    assert r.status_code == 422 and set(r.json()["error"]) == {"code", "message"}
