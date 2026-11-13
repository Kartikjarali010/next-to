DEAL = {"title": "Brunch for two", "description": "x", "category": "cafe", "type": "voucher", "price": 300, "original_price": 600,
        "stock_total": 10, "starts_at": "2026-01-01T00:00:00Z", "ends_at": "2099-01-01T00:00:00Z", "redeem_window_days": 30}


def test_public_shop_profile_shows_details_live_deals_and_reviews(h):
    mt, mid, _ = h.make_merchant(name="Brew House")
    h.conn.execute("UPDATE merchants SET hours='Mon-Sun 9-9', image_url='/img/shop-cafe.jpg', description='Nice cafe' WHERE id=?", (mid,))
    live = h.make_deal(mid, title="Live deal")
    h.make_deal(mid, status="pending", title="Hidden pending")
    h.make_deal(mid, stock=0, title="Sold out")
    ct, _ = h.consumer()
    v = h.buy(ct, live)["voucher"]
    h.c.post("/api/merchant/vouchers/redeem", json={"code": v["code"]}, headers=h.hdr(mt))
    h.c.post("/api/reviews", json={"voucher_id": v["id"], "rating": 4, "comment": "good"}, headers=h.hdr(ct))
    r = h.c.get(f"/api/shops/{mid}")
    assert r.status_code == 200          # public: no sign-in needed
    s = r.json()
    assert s["name"] == "Brew House" and s["hours"] == "Mon-Sun 9-9" and s["image_url"] == "/img/shop-cafe.jpg"
    assert [d["title"] for d in s["deals"]] == ["Live deal"]            # only live deals with stock
    assert s["rating"] == 4.0 and s["review_count"] == 1 and s["redeemed_count"] == 1
    assert s["reviews"][0]["comment"] == "good"


def test_unverified_or_unknown_shop_has_no_public_page(h):
    _, mid, _ = h.make_merchant("pending@t.dev", approved=False)
    assert h.c.get(f"/api/shops/{mid}").status_code == 404
    assert h.c.get("/api/shops/9999").status_code == 404


def test_deal_photo_must_come_from_the_library_or_https(h):
    mt, mid, _ = h.make_merchant()
    post = lambda url: h.c.post("/api/merchant/deals", json=dict(DEAL, image_url=url), headers=h.hdr(mt))
    assert post("/img/deal-cake.jpg").status_code == 200
    assert post("https://example.com/photo.jpg").status_code == 200
    assert post(None).status_code == 200
    for bad in ("javascript:alert(1)", "http://insecure.example/x.jpg", "/img/../secret.txt", "file:///etc/passwd", "data:image/png;base64,AAAA"):
        r = post(bad)
        assert r.status_code == 400 and r.json()["error"]["code"] == "bad_image", bad


def test_merchant_edits_the_public_profile_and_it_is_validated(h):
    mt, mid, _ = h.make_merchant()
    ok = h.c.put("/api/merchant/profile", json={"description": "New about", "hours": "9-5", "image_url": "/img/shop-salon.jpg"}, headers=h.hdr(mt))
    assert ok.status_code == 200 and ok.json()["hours"] == "9-5"
    assert h.c.get(f"/api/shops/{mid}").json()["description"] == "New about"
    bad = h.c.put("/api/merchant/profile", json={"description": "x", "hours": "", "image_url": "javascript:1"}, headers=h.hdr(mt))
    assert bad.status_code == 400
    ct, _ = h.consumer()
    assert h.c.put("/api/merchant/profile", json={"description": "x"}, headers=h.hdr(ct)).status_code == 403       # shoppers cannot edit shops
    app, _, _ = h.make_merchant("applicant@t.dev", approved=False)
    assert h.c.put("/api/merchant/profile", json={"description": "x"}, headers=h.hdr(app)).status_code == 403     # unverified merchants cannot either
