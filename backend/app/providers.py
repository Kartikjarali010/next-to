"""Payment provider + risk scorer interfaces (NFR-5).

Swapping Razorpay for Cashfree, or attaching an ML fraud model, changes one adapter only.
"""
import hashlib
import hmac
import json
import os
import secrets

import httpx


def sign(raw: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


class ProviderError(Exception):
    pass


class PaymentProvider:
    name = "base"

    def create_order(self, amount: float, order_id: int) -> dict: raise NotImplementedError
    def verify_webhook(self, raw: bytes, signature: str | None) -> bool: raise NotImplementedError
    def refund(self, gateway_order_id: str, amount: float) -> dict: raise NotImplementedError
    def get_status(self, gateway_order_id: str) -> str: raise NotImplementedError  # paid|failed|pending


class SimulatedProvider(PaymentProvider):
    """Development provider. Signs/verifies webhooks with HMAC-SHA256, the scheme Razorpay and
    Cashfree use, so the verification code is the real thing; only the money movement is faked."""
    name = "simulated"

    def __init__(self, secret: str | None = None):
        self.secret = secret or os.environ.get("NEXTTO_WEBHOOK_SECRET", "dev-webhook-secret")
        self.orders: dict[str, dict] = {}
        self.fail_refund = False
        self.fail_create = False

    def create_order(self, amount, order_id):
        if self.fail_create:
            raise ProviderError("provider unavailable")
        gid = f"sim_order_{order_id}_{secrets.token_hex(3)}"
        self.orders[gid] = {"amount": amount, "status": "pending"}
        return {"gateway_order_id": gid, "checkout": {"provider": "simulated", "upi_intent": f"upi://pay?pa=nextto@sim&am={amount:.2f}&tn=NextTo+{order_id}"}}

    def verify_webhook(self, raw, signature):
        if not signature:
            return False
        try:
            return hmac.compare_digest(sign(raw, self.secret), signature)
        except Exception:
            return False

    def refund(self, gateway_order_id, amount):
        if self.fail_refund:
            raise ProviderError("refund API unavailable")
        return {"refund_id": f"sim_rf_{secrets.token_hex(4)}", "status": "processed"}

    def get_status(self, gateway_order_id):
        return self.orders.get(gateway_order_id, {}).get("status", "pending")

    # dev helper
    def make_event(self, gateway_order_id: str, amount: float, status="success", event_id: str | None = None):
        body = json.dumps({"event_id": event_id or f"evt_{secrets.token_hex(6)}",
                           "gateway_order_id": gateway_order_id, "amount": amount, "status": status}).encode()
        return body, sign(body, self.secret)


class RazorpayProvider(PaymentProvider):
    """Razorpay test-mode adapter. Enable with NEXTTO_PROVIDER=razorpay, RAZORPAY_KEY_ID/SECRET,
    RAZORPAY_WEBHOOK_SECRET. Not exercised in the demo without keys."""
    name = "razorpay"

    def __init__(self):
        self.key = os.environ["RAZORPAY_KEY_ID"]
        self.secret = os.environ["RAZORPAY_KEY_SECRET"]
        self.webhook_secret = os.environ["RAZORPAY_WEBHOOK_SECRET"]
        self.client = httpx.Client(base_url="https://api.razorpay.com/v1", auth=(self.key, self.secret), timeout=10)

    def create_order(self, amount, order_id):
        try:
            r = self.client.post("/orders", json={"amount": int(round(amount * 100)), "currency": "INR", "receipt": f"nt_{order_id}"})
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise ProviderError(str(e))
        d = r.json()
        return {"gateway_order_id": d["id"], "checkout": {"provider": "razorpay", "key_id": self.key, "order_id": d["id"], "amount": d["amount"]}}

    def verify_webhook(self, raw, signature):
        return bool(signature) and hmac.compare_digest(sign(raw, self.webhook_secret), signature)

    def refund(self, gateway_order_id, amount):
        try:
            pay = self.client.get(f"/orders/{gateway_order_id}/payments").json()["items"][0]["id"]
            r = self.client.post(f"/payments/{pay}/refund", json={"amount": int(round(amount * 100))})
            r.raise_for_status()
            return {"refund_id": r.json()["id"], "status": "processed"}
        except (httpx.HTTPError, KeyError, IndexError) as e:
            raise ProviderError(str(e))

    def get_status(self, gateway_order_id):
        try:
            st = self.client.get(f"/orders/{gateway_order_id}").json().get("status")
        except httpx.HTTPError as e:
            raise ProviderError(str(e))
        return {"paid": "paid", "attempted": "pending", "created": "pending"}.get(st, "pending")


class RiskScorer:
    """Phase 2 plug-in point for an ML fraud model. Default: always allow."""
    def score(self, ctx: dict) -> dict:
        return {"decision": "allow"}


_provider: PaymentProvider | None = None
_risk: RiskScorer = RiskScorer()


def get_provider() -> PaymentProvider:
    global _provider
    if _provider is None:
        _provider = RazorpayProvider() if os.environ.get("NEXTTO_PROVIDER") == "razorpay" else SimulatedProvider()
    return _provider


def set_provider(p: PaymentProvider | None):
    global _provider
    _provider = p


def get_risk() -> RiskScorer:
    return _risk


def set_risk(r: RiskScorer):
    global _risk
    _risk = r
