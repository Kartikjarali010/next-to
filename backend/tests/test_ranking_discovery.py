from datetime import datetime, timedelta, timezone

from app.ranking import category_score, distance_score, haversine_m, recency_score, score_deal, urgency_score

W = {"distance": 0.5, "category": 0.25, "recency": 0.15, "urgency": 0.10}
NOW = datetime.now(timezone.utc)


def sc(**kw):
    base = dict(dist_m=500, radius_m=5000, deal_cat="cafe", selected_cat=None, age_hours=1, ends_at=NOW + timedelta(days=2), now=NOW, stock=5, weights=W)
    base.update(kw)
    return score_deal(**base)["score"]


def test_haversine_known_distance():
    # REVA University to Yelahanka New Town is about 4.3 km
    d = haversine_m(13.1147, 77.6340, 13.1007, 77.5963)
    assert 3800 < d < 4800


def test_distance_score_is_monotonic_and_bounded():
    assert distance_score(0, 5000) == 1
    assert distance_score(2500, 5000) == 0.5
    assert distance_score(9000, 5000) == 0
    assert sc(dist_m=100) > sc(dist_m=1000) > sc(dist_m=4000)


def test_category_score_exact_sibling_other():
    assert category_score("cafe", "cafe") == 1
    assert category_score("bakery", "cafe") == 0.5
    assert category_score("salon", "cafe") == 0
    assert category_score("salon", None) == 0.5


def test_recency_decays_and_urgency_window():
    assert recency_score(0) == 1 and recency_score(72) < 0.4 and recency_score(10) > recency_score(100)
    assert urgency_score(NOW + timedelta(hours=3), NOW, 5) == 1
    assert urgency_score(NOW + timedelta(hours=7), NOW, 5) == 0
    assert urgency_score(NOW + timedelta(hours=3), NOW, 0) == 0


def test_weights_sum_and_score_in_unit_interval():
    assert abs(sum(W.values()) - 1) < 1e-9
    assert 0 <= sc() <= 1
    assert sc(dist_m=0, selected_cat="cafe", age_hours=0, ends_at=NOW + timedelta(hours=1)) == 1.0


# ---------------- API level
def test_nearby_ranks_closer_deal_first_and_hides_unapproved(h):
    _, m1, _ = h.make_merchant("a@t.dev", lat=13.1150, lng=77.6342)
    _, m2, _ = h.make_merchant("b@t.dev", lat=13.1400, lng=77.6600, name="Far")
    _, m3, _ = h.make_merchant("c@t.dev", approved=False, name="Unverified")
    d_near = h.make_deal(m1, title="Near")
    d_far = h.make_deal(m2, title="Far")
    h.make_deal(m3, title="Hidden")
    h.make_deal(m1, status="pending", title="NotLive")
    h.make_deal(m1, stock=0, title="SoldOut")
    r = h.c.get("/api/deals/nearby?lat=13.1147&lng=77.6340&radius_km=10").json()
    titles = [d["title"] for d in r["deals"]]
    assert titles[:2] == ["Near", "Far"]
    assert "Hidden" not in titles and "NotLive" not in titles and "SoldOut" not in titles


def test_nearby_filters_by_radius_and_category(h):
    _, m1, _ = h.make_merchant("a@t.dev", lat=13.1150, lng=77.6342, category="cafe")
    _, m2, _ = h.make_merchant("b@t.dev", lat=13.1148, lng=77.6341, category="salon", name="Salon")
    h.make_deal(m1, category="cafe", title="Coffee")
    h.make_deal(m2, category="salon", title="Haircut")
    r = h.c.get("/api/deals/nearby?lat=13.1147&lng=77.6340&radius_km=2&category=salon").json()
    assert [d["title"] for d in r["deals"]] == ["Haircut"]


def test_missing_location_falls_back_to_area_and_widens_when_empty(h):
    _, m1, _ = h.make_merchant("a@t.dev", lat=13.2100, lng=77.7100)  # ~14 km from default point
    h.make_deal(m1, title="Faraway")
    r = h.c.get("/api/deals/nearby?radius_km=2").json()   # no coordinates at all
    assert r["origin"]["lat"] == 13.1147        # area fallback used (NFR-7)
    assert r["widened"] is True and r["total"] == 1   # cold-start: radius auto-widened


def test_invalid_coordinates_rejected(h):
    r = h.c.get("/api/deals/nearby?lat=999&lng=77")
    assert r.status_code == 400 and r.json()["error"]["code"] == "bad_coords"
