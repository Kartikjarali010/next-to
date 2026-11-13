"""SQLite access, schema and helpers.

Every operation that must be atomic (reserve stock, confirm payment, redeem, refund)
runs inside `tx()`, which opens a BEGIN IMMEDIATE transaction: SQLite then serialises
writers, so two buyers racing for the last unit can never both succeed.
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_DB = str(Path(__file__).resolve().parent.parent / "nextto.db")


def db_path() -> str:
    return os.environ.get("NEXTTO_DB", DEFAULT_DB)


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def now_iso() -> str:
    return iso(now())


def parse(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def plus(**kw) -> str:
    return iso(now() + timedelta(**kw))


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path(), isolation_level=None, check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def tx(conn: sqlite3.Connection):
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def one(cur) -> dict | None:
    r = cur.fetchone()
    return dict(r) if r else None


SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  name TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN('consumer','merchant_applicant','merchant','admin')),
  suspended INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS merchants(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_id INTEGER NOT NULL REFERENCES users(id),
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  address TEXT NOT NULL,
  lat REAL NOT NULL,
  lng REAL NOT NULL,
  description TEXT DEFAULT '',
  doc_note TEXT DEFAULT '',
  verification_status TEXT NOT NULL DEFAULT 'pending'
    CHECK(verification_status IN('pending','approved','rejected')),
  reject_reason TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_merchants_geo ON merchants(lat,lng);
CREATE TABLE IF NOT EXISTS deals(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  merchant_id INTEGER NOT NULL REFERENCES merchants(id),
  title TEXT NOT NULL,
  description TEXT DEFAULT '',
  category TEXT NOT NULL,
  type TEXT NOT NULL DEFAULT 'voucher' CHECK(type IN('voucher','service')),
  price REAL NOT NULL CHECK(price>=0),
  original_price REAL NOT NULL,
  stock_total INTEGER NOT NULL CHECK(stock_total>=0),
  stock_remaining INTEGER NOT NULL CHECK(stock_remaining>=0),
  starts_at TEXT NOT NULL,
  ends_at TEXT NOT NULL,
  redeem_window_days INTEGER NOT NULL DEFAULT 30,
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK(status IN('draft','pending','active','rejected','ended')),
  reject_reason TEXT,
  created_at TEXT NOT NULL,
  published_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_deals_status ON deals(status, ends_at);
CREATE TABLE IF NOT EXISTS slots(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  deal_id INTEGER NOT NULL REFERENCES deals(id),
  starts_at TEXT NOT NULL,
  capacity INTEGER NOT NULL CHECK(capacity>0),
  booked_count INTEGER NOT NULL DEFAULT 0 CHECK(booked_count>=0)
);
CREATE TABLE IF NOT EXISTS orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  consumer_id INTEGER NOT NULL REFERENCES users(id),
  deal_id INTEGER REFERENCES deals(id),
  merchant_id INTEGER REFERENCES merchants(id),
  kind TEXT NOT NULL DEFAULT 'deal' CHECK(kind IN('deal','tip')),
  ref_voucher_id INTEGER,
  amount REAL NOT NULL,
  points_used INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK(status IN('pending','paid','expired','failed','refund_required','refunded')),
  idempotency_key TEXT NOT NULL,
  gateway_order_id TEXT,
  checkout TEXT,
  stock_held INTEGER NOT NULL DEFAULT 0,
  expires_at TEXT,
  created_at TEXT NOT NULL,
  paid_at TEXT,
  payout_id INTEGER,
  UNIQUE(consumer_id, idempotency_key)
);
CREATE TABLE IF NOT EXISTS payments(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL REFERENCES orders(id),
  event_id TEXT UNIQUE NOT NULL,
  status TEXT NOT NULL,
  amount REAL NOT NULL,
  raw TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vouchers(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),
  consumer_id INTEGER NOT NULL REFERENCES users(id),
  deal_id INTEGER NOT NULL REFERENCES deals(id),
  merchant_id INTEGER NOT NULL REFERENCES merchants(id),
  code TEXT UNIQUE NOT NULL,
  status TEXT NOT NULL DEFAULT 'active'
    CHECK(status IN('active','redeemed','expired','refund_pending','refunded')),
  valid_until TEXT NOT NULL,
  issued_at TEXT NOT NULL,
  redeemed_at TEXT,
  payout_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_vouchers_merchant ON vouchers(merchant_id, status);
CREATE TABLE IF NOT EXISTS refunds(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL REFERENCES orders(id),
  voucher_id INTEGER REFERENCES vouchers(id),
  reason TEXT,
  status TEXT NOT NULL DEFAULT 'requested'
    CHECK(status IN('requested','approved','rejected','processed')),
  decided_by INTEGER,
  decided_at TEXT,
  decision_reason TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bookings(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  voucher_id INTEGER NOT NULL UNIQUE REFERENCES vouchers(id),
  slot_id INTEGER NOT NULL REFERENCES slots(id),
  status TEXT NOT NULL DEFAULT 'confirmed' CHECK(status IN('confirmed','completed','cancelled')),
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bookings_slot ON bookings(slot_id);
CREATE TABLE IF NOT EXISTS reviews(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  voucher_id INTEGER NOT NULL UNIQUE REFERENCES vouchers(id),
  consumer_id INTEGER NOT NULL REFERENCES users(id),
  merchant_id INTEGER NOT NULL REFERENCES merchants(id),
  rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
  comment TEXT DEFAULT '',
  hidden INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reward_ledger(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  delta INTEGER NOT NULL,
  reason TEXT NOT NULL,
  ref TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS payouts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  merchant_id INTEGER NOT NULL REFERENCES merchants(id),
  period TEXT NOT NULL,
  gross REAL NOT NULL,
  fee REAL NOT NULL,
  net REAL NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN('pending','released')),
  created_at TEXT NOT NULL,
  released_at TEXT
);
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  entity TEXT NOT NULL,
  entity_id TEXT,
  before TEXT,
  after TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  type TEXT NOT NULL,
  message TEXT NOT NULL,
  payload TEXT,
  read INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

DEFAULT_CONFIG = {
    "ranking_weights": {"distance": 0.50, "category": 0.25, "recency": 0.15, "urgency": 0.10},
    "platform_fee_pct": 10,
    "point_earn_per_rupees": 10,   # 1 point per Rs 10 spent, credited at redemption
    "point_value_rupees": 1,       # 1 point = Rs 1 off
    "max_points_discount_pct": 50,
    "reservation_minutes": 10,
    "reconcile_after_minutes": 15,
}


def init_db(conn: sqlite3.Connection | None = None) -> None:
    own = conn is None
    conn = conn or connect()
    conn.executescript(SCHEMA)
    for k, v in DEFAULT_CONFIG.items():
        conn.execute("INSERT OR IGNORE INTO config(key,value) VALUES(?,?)", (k, json.dumps(v)))
    if own:
        conn.close()


def cfg(conn: sqlite3.Connection, key: str):
    r = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    return json.loads(r["value"]) if r else DEFAULT_CONFIG[key]


def audit(conn, actor, action, entity, entity_id=None, before=None, after=None):
    conn.execute(
        "INSERT INTO audit_log(actor,action,entity,entity_id,before,after,created_at) VALUES(?,?,?,?,?,?,?)",
        (str(actor), action, entity, None if entity_id is None else str(entity_id),
         None if before is None else json.dumps(before, default=str),
         None if after is None else json.dumps(after, default=str), now_iso()),
    )


def notify(conn, user_id, type_, message, payload=None):
    """Queue an in-app notification (email/push delivery is a Phase-2 adapter)."""
    conn.execute(
        "INSERT INTO notifications(user_id,type,message,payload,created_at) VALUES(?,?,?,?,?)",
        (user_id, type_, message, json.dumps(payload) if payload else None, now_iso()),
    )


def points_balance(conn, user_id) -> int:
    return conn.execute("SELECT COALESCE(SUM(delta),0) s FROM reward_ledger WHERE user_id=?", (user_id,)).fetchone()["s"]
