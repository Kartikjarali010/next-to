"""Deal ranking: simple, explainable, cold-start safe (FR-D1, FR-D2, NFR-6).

score = w_d*distance + w_c*category + w_r*recency + w_u*urgency     (each term in [0,1])
"""
import math
from datetime import datetime

EARTH_R = 6371000.0

SIBLINGS = {
    "food": {"cafe", "bakery"}, "cafe": {"food", "bakery"}, "bakery": {"food", "cafe"},
    "salon": {"spa", "fitness"}, "spa": {"salon", "fitness"}, "fitness": {"spa", "salon"},
    "retail": {"services"}, "services": {"retail"}, "entertainment": set(),
}
CATEGORIES = sorted(SIBLINGS)


def haversine_m(lat1, lng1, lat2, lng2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(a))


def distance_score(dist_m: float, radius_m: float) -> float:
    return 1 - min(dist_m / radius_m, 1) if radius_m > 0 else 0.0


def category_score(deal_cat: str, selected: str | None) -> float:
    if not selected:
        return 0.5
    if deal_cat == selected:
        return 1.0
    return 0.5 if deal_cat in SIBLINGS.get(selected, set()) else 0.0


def recency_score(age_hours: float) -> float:
    return math.exp(-max(age_hours, 0) / 72)


def urgency_score(ends_at: datetime, now: datetime, stock: int) -> float:
    left_h = (ends_at - now).total_seconds() / 3600
    return 1.0 if 0 < left_h <= 6 and stock > 0 else 0.0


def score_deal(*, dist_m, radius_m, deal_cat, selected_cat, age_hours, ends_at, now, stock, weights) -> dict:
    parts = {
        "distance": distance_score(dist_m, radius_m),
        "category": category_score(deal_cat, selected_cat),
        "recency": recency_score(age_hours),
        "urgency": urgency_score(ends_at, now, stock),
    }
    total = sum(weights[k] * parts[k] for k in parts)
    return {"score": round(total, 4), "parts": {k: round(v, 3) for k, v in parts.items()}}
