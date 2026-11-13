"""End-to-end journey against a running server (default http://localhost:8000):
merchant applies -> admin approves -> merchant creates + submits deal -> admin approves -> consumer finds, buys, pays
-> merchant redeems -> consumer reviews/tips -> admin settles payout. Prints each step."""
import sys, time, httpx
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
c = httpx.Client(base_url=BASE + "/api", timeout=15)
def call(m, p, tok=None, **kw):
    h = {"Authorization": f"Bearer {tok}"} if tok else {}
    h.update(kw.pop("headers", {}))
    r = c.request(m, p, headers=h, **kw)
    return r.status_code, (r.json() if r.content else None)
def step(n, label, ok): print(f"{n:>2}. {'PASS' if ok else 'FAIL'}  {label}"); assert ok, label
sfx = str(int(time.time()))[-6:]
_, adm = call("POST", "/auth/login", json={"email": "admin@nextto.dev", "password": "admin123"}); A = adm["token"]
s, m = call("POST", "/auth/signup", json={"email": f"biz{sfx}@demo.com", "password": "demo123", "name": "Demo Owner", "account_type": "merchant",
    "business": {"name": f"E2E Cafe {sfx}", "category": "cafe", "address": "Kattigenahalli", "lat": 13.1150, "lng": 77.6345, "doc_note": "GST 29ABCDE1234F1Z5"}})
M, mid = m["token"], m["user"]["merchant"]["id"]; step(1, "merchant applies (role=merchant_applicant)", s == 200 and m["user"]["role"] == "merchant_applicant")
s, _ = call("POST", "/merchant/deals", M, json={}); step(2, "unverified merchant cannot create deals", s in (403, 422) and s != 200)
s, _ = call("POST", f"/admin/merchants/{mid}/decision", A, json={"decision": "approve"}); step(3, "admin approves merchant", s == 200)
_, r = call("POST", "/auth/refresh", M); M = r["token"]; step(4, "token refresh grants merchant role", r["user"]["role"] == "merchant")
deal = {"title": f"E2E Latte Deal {sfx}", "description": "demo", "category": "cafe", "type": "voucher", "price": 80, "original_price": 160, "stock_total": 3,
        "starts_at": "2026-01-01T00:00:00Z", "ends_at": "2099-01-01T00:00:00Z", "redeem_window_days": 30}
s, d = call("POST", "/merchant/deals", M, json=deal); did = d["id"]; step(5, "merchant creates deal (draft)", s == 200 and d["status"] == "draft")
step(6, "draft is invisible to shoppers", call("GET", f"/deals/{did}")[0] == 404)
s, _ = call("POST", f"/merchant/deals/{did}/submit", M); step(7, "merchant submits for approval", s == 200)
s, _ = call("POST", f"/admin/deals/{did}/decision", A, json={"decision": "approve"}); step(8, "admin approves deal -> active", s == 200)
_, nb = call("GET", "/deals/nearby?lat=13.1147&lng=77.6340&radius_km=3"); step(9, "deal appears in nearby search", any(x["id"] == did for x in nb["deals"]))
_, cu = call("POST", "/auth/signup", json={"email": f"c{sfx}@demo.com", "password": "demo123", "name": "Demo Shopper"}); C = cu["token"]
key = f"e2e-key-{sfx}"
s, o1 = call("POST", "/orders", C, json={"deal_id": did}, headers={"Idempotency-Key": key})
s2, o2 = call("POST", "/orders", C, json={"deal_id": did}, headers={"Idempotency-Key": key})
step(10, "order created; same Idempotency-Key returns same order", s == 200 and o1["id"] == o2["id"] and o1["status"] == "pending")
_, dd = call("GET", f"/deals/{did}"); step(11, "stock reserved at order creation (3 -> 2)", dd["stock_remaining"] == 2)
s, bad = call("POST", "/webhooks/payment", content=b'{"x":1}', headers={"X-Signature": "00"}); step(12, "forged webhook rejected (401)", s == 401)
s, p = call("POST", "/dev/simulate-payment", C, json={"order_id": o1["id"], "outcome": "success"}); step(13, "signed webhook -> order paid", p["order_status"] == "paid")
_, vs = call("GET", "/vouchers", C); v = vs[0]; step(14, "voucher issued with signed QR payload", v["qr"].startswith("NT.") and v["status"] == "active")
s, r = call("POST", "/merchant/vouchers/redeem", M, json={"code": v["qr"]}); step(15, "merchant scans QR -> redeemed, points awarded", s == 200 and r["points_awarded"] == 8)
s, r = call("POST", "/merchant/vouchers/redeem", M, json={"code": v["code"]}); step(16, "second scan rejected (already_redeemed)", s == 409 and r["error"]["code"] == "already_redeemed")
s, rv = call("POST", "/reviews", C, json={"voucher_id": v["id"], "rating": 5, "comment": "Lovely!", "tip": 10}); step(17, "review + tip order created", s == 200 and rv["tip_order"]["amount"] == 10)
call("POST", "/dev/simulate-payment", C, json={"order_id": rv["tip_order"]["id"], "outcome": "success"})
_, rw = call("GET", "/rewards", C); step(18, "points credited at redemption", rw["balance"] == 8)
s, pr = call("POST", "/admin/payouts/run", A, json={}); step(19, "admin settlement creates payout", s == 200 and len(pr["created"]) >= 1)
_, ps = call("GET", "/merchant/payouts", M); step(20, "payout = 80 - 10% fee + 10 tip = 82", ps[0]["net"] == 82 and ps[0]["fee"] == 8)
_, au = call("GET", "/admin/audit?limit=200", A); acts = {a["action"] for a in au}; step(21, "audit log captured the journey", {"order.paid", "voucher.redeemed", "payout.created", "merchant.approved"} <= acts)
print("\nALL STEPS PASSED")
