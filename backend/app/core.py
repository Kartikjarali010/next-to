"""Errors, password hashing, JWT with app_role claim, role guards, simple rate limiter."""
import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict, deque

import jwt
from fastapi import Depends, Header
from fastapi.requests import Request

from .db import get_db

JWT_SECRET = os.environ.get("NEXTTO_JWT_SECRET", "dev-only-secret-change-me-32-bytes-min!!")
QR_SECRET = os.environ.get("NEXTTO_QR_SECRET", "dev-only-qr-secret-change-me")
TOKEN_HOURS = 24


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def bad(msg, code="invalid_request"): return AppError(400, code, msg)
def unauthorized(msg="Authentication required"): return AppError(401, "unauthorized", msg)
def forbidden(msg="Not allowed"): return AppError(403, "forbidden", msg)
def not_found(msg="Not found"): return AppError(404, "not_found", msg)
def conflict(msg, code="conflict"): return AppError(409, code, msg)


# ---- passwords (PBKDF2, stdlib) ----
def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000)
    return salt.hex() + "$" + dk.hex()


def verify_password(pw: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt_hex), 200_000)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


# ---- JWT carrying the app_role claim ----
def make_token(user: dict) -> str:
    return jwt.encode(
        {"sub": str(user["id"]), "app_role": user["role"], "exp": int(time.time()) + TOKEN_HOURS * 3600},
        JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise unauthorized("Invalid or expired token")


def current_user(authorization: str | None = Header(default=None), conn=Depends(get_db)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise unauthorized()
    claims = decode_token(authorization[7:].strip())
    u = conn.execute("SELECT id,email,name,role,suspended FROM users WHERE id=?", (int(claims["sub"]),)).fetchone()
    if not u:
        raise unauthorized("Unknown user")
    u = dict(u)
    if u["suspended"]:
        raise forbidden("Account suspended")
    u["role"] = claims["app_role"]  # role is read from the signed claim, never from the request body
    return u


def require(*roles: str):
    def dep(user=Depends(current_user)):
        if user["role"] not in roles:
            raise forbidden(f"Requires role: {', '.join(roles)}")
        return user
    return dep


# ---- QR payload: NT.<code>.<sig> ----
def qr_sign(code: str) -> str:
    return hmac.new(QR_SECRET.encode(), code.encode(), hashlib.sha256).hexdigest()[:10]


def qr_payload(code: str) -> str:
    return f"NT.{code}.{qr_sign(code)}"


def qr_parse(raw: str) -> str:
    """Accept a bare code or a signed QR payload; reject forged signatures."""
    raw = raw.strip()
    if raw.startswith("NT."):
        parts = raw.split(".")
        if len(parts) != 3 or not hmac.compare_digest(parts[2], qr_sign(parts[1])):
            raise bad("QR code signature is invalid", "bad_qr")
        return parts[1]
    return raw.upper()


def new_voucher_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(10))


# ---- naive in-memory rate limiter (auth + redemption endpoints) ----
_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(request: Request, key: str, limit: int, window: int = 60):
    if os.environ.get("NEXTTO_DISABLE_RATELIMIT"):
        return
    k = f"{key}:{request.client.host if request.client else 'x'}"
    q, t = _hits[k], time.time()
    while q and q[0] < t - window:
        q.popleft()
    if len(q) >= limit:
        raise AppError(429, "rate_limited", "Too many attempts, try again shortly")
    q.append(t)
