import os
import tempfile
from datetime import timedelta

import pytest

os.environ["NEXTTO_DISABLE_RATELIMIT"] = "1"
_tmp = tempfile.mkdtemp(prefix="nextto_test_")


@pytest.fixture()
def env(monkeypatch):
    """Fresh database + simulated provider for every test."""
    path = os.path.join(tempfile.mkdtemp(dir=_tmp), "t.db")
    monkeypatch.setenv("NEXTTO_DB", path)
    from app import db, providers
    db.init_db()
    prov = providers.SimulatedProvider(secret="test-secret")
    providers.set_provider(prov)
    providers.set_risk(providers.RiskScorer())
    conn = db.connect()
    yield type("Env", (), {"conn": conn, "prov": prov, "path": path})
    conn.close()


class Helper:
    def __init__(self, env):
        from fastapi.testclient import TestClient
        from app.main import app
        self.env, self.conn, self.prov = env, env.conn, env.prov
        self.c = TestClient(app)
        self.n = 0

    # ---- http helpers
    def signup(self, email, name="Test User", account_type="consumer", business=None, password="secret1"):
        body = {"email": email, "password": password, "name": name, "account_type": account_type}
        if business:
            body["business"] = business
        r = self.c.post("/api/auth/signup", json=body)
        assert r.status_code == 200, r.text
        return r.json()

    def hdr(self, token):
        return {"Authorization": f"Bearer {token}"}

    def login(self, email, password="secret1"):
        r = self.c.post("/api/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text
        return r.json()["token"]

    # ---- fixtures through direct DB
    def make_admin(self, email="admin@t.dev"):
        from app.core import hash_password
        from app.db import now_iso
        self.conn.execute("INSERT INTO users(email,password_hash,name,role,created_at) VALUES(?,?,?,'admin',?)", (email, hash_password("secret1"), "Admin", now_iso()))
        return self.login(email)

    def make_merchant(self, email="m@t.dev", lat=13.1147, lng=77.6340, approved=True, category="cafe", name="Test Cafe"):
        s = self.signup(email, "Owner", "merchant", {"name": name, "category": category, "address": "1 Main Rd", "lat": lat, "lng": lng})
        mid = s["user"]["merchant"]["id"]
        if approved:
            self.conn.execute("UPDATE merchants SET verification_status='approved' WHERE id=?", (mid,))
            self.conn.execute("UPDATE users SET role='merchant' WHERE id=?", (s["user"]["id"],))
            return self.login(email), mid, s["user"]["id"]
        return s["token"], mid, s["user"]["id"]

    def make_deal(self, mid, stock=5, price=100, status="active", typ="voucher", category="cafe", ends_h=48, starts_h=-1, window=30, title="Test Deal"):
        from app.db import iso, now, now_iso
        n = now()
        return self.conn.execute(
            "INSERT INTO deals(merchant_id,title,description,category,type,price,original_price,stock_total,stock_remaining,starts_at,ends_at,redeem_window_days,status,created_at,published_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (mid, title, "", category, typ, price, price * 2, stock, stock, iso(n + timedelta(hours=starts_h)), iso(n + timedelta(hours=ends_h)), window, status, now_iso(), now_iso())).lastrowid

    def make_slot(self, deal_id, hours_ahead=24, capacity=1):
        from app.db import iso, now
        return self.conn.execute("INSERT INTO slots(deal_id,starts_at,capacity) VALUES(?,?,?)", (deal_id, iso(now() + timedelta(hours=hours_ahead)), capacity)).lastrowid

    def consumer(self, email="c@t.dev"):
        s = self.signup(email)
        return s["token"], s["user"]["id"]

    def order(self, token, deal_id, key=None, use_points=0):
        self.n += 1
        return self.c.post("/api/orders", json={"deal_id": deal_id, "use_points": use_points},
                           headers={**self.hdr(token), "Idempotency-Key": key or f"key-{self.n}-abcdefgh"})

    def pay(self, token, order_id, outcome="success"):
        return self.c.post("/api/dev/simulate-payment", json={"order_id": order_id, "outcome": outcome}, headers=self.hdr(token))

    def buy(self, token, deal_id, key=None):
        o = self.order(token, deal_id, key).json()
        assert self.pay(token, o["id"]).status_code == 200
        return self.c.get(f"/api/orders/{o['id']}", headers=self.hdr(token)).json()

    def webhook(self, gateway_order_id, amount, status="success", event_id=None, sig=None):
        raw, good = self.prov.make_event(gateway_order_id, amount, status, event_id)
        return self.c.post("/api/webhooks/payment", content=raw, headers={"X-Signature": sig if sig is not None else good, "Content-Type": "application/json"})


@pytest.fixture()
def h(env):
    return Helper(env)
