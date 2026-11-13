"""Demo data around REVA University, Kattigenahalli (Bengaluru). Built through the real service
functions where possible so history (orders, vouchers, reviews, refunds) is genuine."""
from datetime import timedelta

from . import services as svc
from .core import hash_password
from .db import iso, now, now_iso, one, plus, rows
from .providers import SimulatedProvider, get_provider

PW = "demo123"


def _user(conn, email, name, role):
    cur = conn.execute("INSERT INTO users(email,password_hash,name,role,created_at) VALUES(?,?,?,?,?)",
                       (email, hash_password(PW if role != "admin" else "admin123"), name, role, now_iso()))
    return cur.lastrowid


def _merchant(conn, owner, name, cat, addr, lat, lng, desc, status="approved"):
    return conn.execute(
        "INSERT INTO merchants(owner_id,name,category,address,lat,lng,description,doc_note,verification_status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (owner, name, cat, addr, lat, lng, desc, "GST + trade licence uploaded (demo)", status, now_iso())).lastrowid


def _deal(conn, mid, title, desc, cat, typ, price, orig, stock, start_h, end_h, status="active", window=30, age_h=6):
    n = now()
    pub = iso(n - timedelta(hours=age_h)) if status == "active" else None
    return conn.execute(
        "INSERT INTO deals(merchant_id,title,description,category,type,price,original_price,stock_total,stock_remaining,starts_at,ends_at,redeem_window_days,status,created_at,published_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (mid, title, desc, cat, typ, price, orig, stock, stock, iso(n + timedelta(hours=start_h)), iso(n + timedelta(hours=end_h)),
         window, status, iso(n - timedelta(hours=age_h)), pub)).lastrowid


def _slots(conn, deal_id, days=(1, 2, 3), hours=(11, 15, 17), cap=2):
    n = now().replace(minute=0, second=0, microsecond=0)
    for d in days:
        for h in hours:
            t = (n + timedelta(days=d)).replace(hour=h)
            conn.execute("INSERT INTO slots(deal_id,starts_at,capacity) VALUES(?,?,?)", (deal_id, iso(t), cap))


def _buy(conn, user_id, deal_id, key, pay=True):
    u = {"id": user_id}
    o = svc.create_order(conn, u, deal_id, key)
    if pay:
        prov = get_provider()
        raw, sig = prov.make_event(o["gateway_order_id"], o["amount"], "success")
        svc.handle_webhook(conn, raw, sig)
    return one(conn.execute("SELECT * FROM vouchers WHERE order_id=?", (o["id"],)))


def seed(conn):
    admin = _user(conn, "admin@nextto.dev", "NextTo Admin", "admin")
    kartik = _user(conn, "kartik@demo.com", "Kartik Jarali", "consumer")
    leah = _user(conn, "leah@demo.com", "Leah Chakarmakal", "consumer")
    _user(conn, "rahul@demo.com", "Rahul Nair", "consumer")
    o_cafe = _user(conn, "cafe@demo.com", "Anita (Brew & Bean)", "merchant")
    o_salon = _user(conn, "salon@demo.com", "Meera (Glow Salon)", "merchant")
    o_gym = _user(conn, "gym@demo.com", "Vikram (FitZone)", "merchant")
    o_bake = _user(conn, "bakery@demo.com", "Suresh (Sweet Crumbs)", "merchant")
    o_new = _user(conn, "new@demo.com", "Farah (Spice Route)", "merchant_applicant")

    cafe = _merchant(conn, o_cafe, "Brew & Bean Café", "cafe", "Kattigenahalli Main Rd, Yelahanka", 13.1163, 77.6368, "Specialty coffee and fresh sandwiches near campus.")
    salon = _merchant(conn, o_salon, "Glow Unisex Salon", "salon", "Jakkur Main Rd, Bengaluru", 13.1122, 77.6301, "Haircuts, colour and facials.")
    gym = _merchant(conn, o_gym, "FitZone Gym", "fitness", "Yelahanka New Town", 13.1031, 77.6012, "Strength, cardio and group classes.")
    bake = _merchant(conn, o_bake, "Sweet Crumbs Bakery", "bakery", "Attur Layout, Yelahanka", 13.1055, 77.6190, "Cakes, breads and puffs baked daily.")
    spice = _merchant(conn, o_new, "Spice Route Restaurant", "food", "Doddaballapur Rd, Kattigenahalli", 13.1190, 77.6410, "North Indian thali and biryani.", status="pending")
    pizza = None  # placeholder for future merchants

    d_coffee = _deal(conn, cafe, "Buy 1 Get 1 Free Cappuccino", "Two cappuccinos for the price of one, any weekday.", "cafe", "voucher", 120, 240, 40, -24, 72)
    d_combo = _deal(conn, cafe, "Sandwich + Cold Coffee Combo", "Grilled veg sandwich with a cold coffee.", "cafe", "voucher", 149, 260, 25, -12, 4, age_h=3)  # ends in 4h: urgent
    d_cake = _deal(conn, bake, "Chocolate Truffle Cake (500 g) 30% off", "Fresh baked, eggless option available.", "bakery", "voucher", 420, 600, 15, -48, 120, age_h=30)
    d_puff = _deal(conn, bake, "Box of 6 Puffs", "Mix of veg and paneer puffs.", "bakery", "voucher", 99, 180, 60, -6, 48, age_h=2)
    d_hair = _deal(conn, salon, "Haircut + Head Wash", "Includes style consultation. Appointment required.", "salon", "service", 199, 450, 30, -20, 96, age_h=10)
    d_facial = _deal(conn, salon, "Deep Cleansing Facial", "60-minute facial. Appointment required.", "salon", "service", 599, 1200, 12, -8, 120, age_h=5)
    d_gym = _deal(conn, gym, "1-Month Gym Membership", "All equipment + one trial personal-training session.", "fitness", "voucher", 999, 2000, 20, -30, 200, window=60, age_h=40)
    d_yoga = _deal(conn, gym, "Yoga Class Pass (5 sessions)", "Morning batches. Book your slot after purchase.", "fitness", "service", 349, 700, 25, -10, 150, age_h=8)
    d_pending = _deal(conn, cafe, "Weekend Brunch for Two", "Pancakes, eggs and two coffees.", "food", "voucher", 349, 700, 20, 0, 96, status="pending")
    _deal(conn, cafe, "Cold Brew Tasting Flight (draft)", "A draft the merchant has not submitted yet.", "cafe", "voucher", 199, 320, 10, 0, 72, status="draft")
    _deal(conn, bake, "Cupcake Dozen (ended)", "An old deal.", "bakery", "voucher", 299, 480, 10, -100, -10, status="ended", age_h=110)
    for did in (d_hair, d_facial):
        _slots(conn, did, hours=(11, 15, 17))
    _slots(conn, d_yoga, days=(1, 2, 3, 4), hours=(6, 7, 8), cap=10)

    # ---- real history through the service layer (so audit log, vouchers, points are genuine)
    prov = get_provider()
    v1 = _buy(conn, kartik, d_coffee, "seed-kartik-coffee-1")
    v2 = _buy(conn, kartik, d_hair, "seed-kartik-hair-1")
    v3 = _buy(conn, leah, d_cake, "seed-leah-cake-1")
    v4 = _buy(conn, leah, d_gym, "seed-leah-gym-1")
    v5 = _buy(conn, leah, d_puff, "seed-leah-puff-1")
    m_cafe = one(conn.execute("SELECT * FROM merchants WHERE id=?", (cafe,)))
    m_bake = one(conn.execute("SELECT * FROM merchants WHERE id=?", (bake,)))
    svc.redeem_voucher(conn, m_cafe, v1["code"])
    svc.redeem_voucher(conn, m_bake, v3["code"])
    conn.execute("INSERT INTO reviews(voucher_id,consumer_id,merchant_id,rating,comment,created_at) VALUES(?,?,?,?,?,?)",
                 (v1["id"], kartik, cafe, 5, "Great coffee and quick service!", now_iso()))
    conn.execute("INSERT INTO reviews(voucher_id,consumer_id,merchant_id,rating,comment,created_at) VALUES(?,?,?,?,?,?)",
                 (v3["id"], leah, bake, 4, "Cake was fresh and delicious.", now_iso()))
    # an open refund request for the admin queue
    svc.request_refund(conn, {"id": leah}, v4["id"], "Changed my plans, cannot visit this month")
    # a service voucher with a booking
    slot = one(conn.execute("SELECT id FROM slots WHERE deal_id=? ORDER BY starts_at LIMIT 1", (d_hair,)))
    svc.create_booking(conn, {"id": kartik}, v2["id"], slot["id"])
    # a pending (unpaid) order showing the stock reservation
    svc.create_order(conn, {"id": kartik}, d_puff, "seed-kartik-puff-pending")
    return True
