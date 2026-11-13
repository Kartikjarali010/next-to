import re

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ..core import bad, conflict, current_user, forbidden, hash_password, make_token, rate_limit, unauthorized, verify_password
from ..db import audit, get_db, now_iso, one, points_balance, tx
from ..ranking import CATEGORIES

router = APIRouter(prefix="/api/auth", tags=["auth"])
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Business(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    category: str
    address: str = Field(min_length=3, max_length=200)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    description: str = ""
    doc_note: str = ""


class SignupIn(BaseModel):
    email: str
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(min_length=2, max_length=80)
    account_type: str = "consumer"  # consumer | merchant
    business: Business | None = None


class LoginIn(BaseModel):
    email: str
    password: str
    portal: str | None = None   # consumer | merchant | admin: each portal accepts only its own roles

PORTAL_ROLES = {"consumer": {"consumer"}, "merchant": {"merchant", "merchant_applicant"}, "admin": {"admin"}}


def user_out(conn, u: dict) -> dict:
    out = {"id": u["id"], "email": u["email"], "name": u["name"], "role": u["role"]}
    if u["role"] == "consumer":
        out["points"] = points_balance(conn, u["id"])
    m = one(conn.execute("SELECT id,name,verification_status,reject_reason FROM merchants WHERE owner_id=?", (u["id"],)))
    if m:
        out["merchant"] = m
    return out


@router.post("/signup")
def signup(body: SignupIn, request: Request, conn=Depends(get_db)):
    rate_limit(request, "signup", 20)
    email = body.email.strip().lower()
    if not EMAIL.match(email):
        raise bad("Enter a valid email address", "bad_email")
    if body.account_type not in ("consumer", "merchant"):
        raise bad("account_type must be consumer or merchant")
    if body.account_type == "merchant":
        if not body.business:
            raise bad("Business details are required for a merchant account")
        if body.business.category not in CATEGORIES:
            raise bad(f"category must be one of {', '.join(CATEGORIES)}")
    if conn.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
        raise conflict("An account with this email already exists", "email_taken")
    # merchants start as 'merchant_applicant'; the merchant role is granted only after admin approval
    role = "merchant_applicant" if body.account_type == "merchant" else "consumer"
    with tx(conn):
        uid = conn.execute("INSERT INTO users(email,password_hash,name,role,created_at) VALUES(?,?,?,?,?)",
                           (email, hash_password(body.password), body.name.strip(), role, now_iso())).lastrowid
        if body.business:
            b = body.business
            mid = conn.execute(
                "INSERT INTO merchants(owner_id,name,category,address,lat,lng,description,doc_note,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (uid, b.name, b.category, b.address, b.lat, b.lng, b.description, b.doc_note, now_iso())).lastrowid
            audit(conn, uid, "merchant.applied", "merchant", mid, None, {"status": "pending"})
        audit(conn, uid, "user.signup", "user", uid, None, {"role": role})
    u = one(conn.execute("SELECT * FROM users WHERE id=?", (uid,)))
    return {"token": make_token(u), "user": user_out(conn, u)}


@router.post("/login")
def login(body: LoginIn, request: Request, conn=Depends(get_db)):
    rate_limit(request, "login", 15)
    u = one(conn.execute("SELECT * FROM users WHERE email=?", (body.email.strip().lower(),)))
    if not u or not verify_password(body.password, u["password_hash"]):
        raise unauthorized("Incorrect email or password")
    if u["suspended"]:
        raise unauthorized("This account is suspended")
    if body.portal is not None:
        if body.portal not in PORTAL_ROLES:
            raise bad("Unknown portal")
        if u["role"] not in PORTAL_ROLES[body.portal]:   # checked only after the password, so roles are not leaked
            raise forbidden("This account cannot sign in here. Please use the correct sign-in page for your account.")
    return {"token": make_token(u), "user": user_out(conn, u)}


@router.get("/me")
def me(user=Depends(current_user), conn=Depends(get_db)):
    u = one(conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)))
    return user_out(conn, u)


@router.post("/refresh")
def refresh(user=Depends(current_user), conn=Depends(get_db)):
    """Re-issue the token so a newly granted role (e.g. merchant approval) takes effect."""
    u = one(conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)))
    return {"token": make_token(u), "user": user_out(conn, u)}
