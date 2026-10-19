"""
Hybrid flight ranking: fare + duration + availability + occupancy
+ passenger preference + cancellation-risk. Weights come from
config / recommendation_config.pkl — never duplicated in pages.
"""

import os

import joblib
import numpy as np

from config import MODEL_VERSIONS, RECOMMENDATION_WEIGHTS
from database.db_connection import (
    get_latest_occupancy_prediction,
    get_passenger_preferences,
    log_recommendation_event,
)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "recommendation_config.pkl")

_WEIGHTS = None


def load_weights():
    global _WEIGHTS
    if _WEIGHTS is not None:
        return _WEIGHTS
    if os.path.exists(CONFIG_PATH):
        bundle = joblib.load(CONFIG_PATH)
        _WEIGHTS = bundle.get("weights", RECOMMENDATION_WEIGHTS)
    else:
        _WEIGHTS = dict(RECOMMENDATION_WEIGHTS)
    return _WEIGHTS


def _minmax(values, invert=False):
    arr = np.array(values, dtype=float)
    if len(arr) == 0:
        return arr
    lo, hi = np.nanmin(arr), np.nanmax(arr)
    if hi - lo < 1e-9:
        return np.ones_like(arr) * 0.5
    scaled = (arr - lo) / (hi - lo)
    return 1.0 - scaled if invert else scaled


def _hour(dt):
    if hasattr(dt, "hour"):
        return dt.hour
    return 12


def rank_flights(flights, passenger_id=None, persist_events=True):
    """
    Rank candidate flights. Occupancy predictions are used if already
    stored; missing occupancy falls back to current booked/capacity.
    Cancellation risk for unbooked flights uses a cheap proxy from
    occupancy + lead time (not a fake per-booking classifier score).
    """
    if not flights:
        return []

    weights = load_weights()
    prefs = get_passenger_preferences(passenger_id) if passenger_id else {}
    has_history = bool(prefs) and prefs.get("avg_fare") is not None

    fares, durs, avails, occs, risks, pref_s = [], [], [], [], [], []
    enriched = []

    for f in flights:
        cap = int(f.get("total_seats") or 1)
        avail = int(f.get("available_seats") or 0)
        booked = cap - avail
        occ_pred = get_latest_occupancy_prediction(f["flight_id"])
        if occ_pred and occ_pred.get("predicted_occupancy") is not None:
            occ_pct = float(occ_pred["predicted_occupancy"])
        else:
            occ_pct = booked / cap * 100 if cap else 0.0

        # Proxy risk: fuller last-minute flights tend to have more messy ops;
        # this is a ranking feature, not the trained classifier.
        dep = f.get("departure_time")
        from datetime import datetime, date
        if hasattr(dep, "date"):
            days_left = max((dep.date() - date.today()).days, 0)
        else:
            days_left = 7
        proxy_risk = min(0.95, 0.08 + (0.35 if days_left < 3 else 0) + (0.15 if occ_pct > 90 else 0))

        pref = 0.5
        if has_history:
            avg_fare = float(prefs.get("avg_fare") or 0)
            avg_hour = float(prefs.get("avg_dep_hour") or 12)
            hour = _hour(dep)
            fare_fit = 1.0 - min(abs(float(f["base_fare"]) - avg_fare) / max(avg_fare, 1.0), 1.0)
            time_fit = 1.0 - min(abs(hour - avg_hour) / 12.0, 1.0)
            pref = 0.5 * fare_fit + 0.5 * time_fit

        row = dict(f)
        row["_occ_pct"] = occ_pct
        row["_proxy_risk"] = proxy_risk
        row["_pref"] = pref
        row["_has_history"] = has_history
        enriched.append(row)
        fares.append(float(f["base_fare"]))
        durs.append(int(f.get("duration_minutes") or 0))
        avails.append(avail)
        occs.append(occ_pct)
        risks.append(proxy_risk)
        pref_s.append(pref)

    fare_s = _minmax(fares, invert=True)
    dur_s = _minmax(durs, invert=True)
    avail_s = _minmax(avails, invert=False)
    # Prefer moderate occupancy (not empty, not overfull): peak at 75%
    occ_s = 1.0 - np.abs(np.array(occs) - 75.0) / 75.0
    occ_s = np.clip(occ_s, 0, 1)
    risk_s = _minmax(risks, invert=True)  # lower risk is better
    pref_arr = np.array(pref_s)

    ranked = []
    for i, row in enumerate(enriched):
        score = 100.0 * (
            weights["fare_weight"] * fare_s[i]
            + weights["duration_weight"] * dur_s[i]
            + weights["availability_weight"] * avail_s[i]
            + weights["occupancy_weight"] * occ_s[i]
            + weights["preference_weight"] * pref_arr[i]
            + weights["risk_weight"] * risk_s[i]
        )
        reasons = []
        if fare_s[i] >= 0.65:
            reasons.append("Good fare versus similar flights on this search")
        if dur_s[i] >= 0.65:
            reasons.append("Shorter duration than other options")
        if avail_s[i] >= 0.55:
            reasons.append("Good seat availability")
        if occ_s[i] >= 0.55:
            reasons.append("Healthy predicted occupancy (not empty, not overcrowded)")
        if risk_s[i] >= 0.6:
            reasons.append("Lower operational/cancellation-risk proxy")
        if row["_has_history"] and pref_arr[i] >= 0.55:
            reasons.append("Matches this passenger's historical fare/time preferences")
        if not row["_has_history"]:
            reasons.append("Cold-start ranking: popularity, price, availability, occupancy, risk")

        row["recommendation_score"] = round(float(score), 1)
        row["recommendation_reasons"] = reasons
        row["predicted_occupancy"] = round(float(row["_occ_pct"]), 1)
        row["risk_proxy"] = "LOW" if row["_proxy_risk"] < 0.25 else ("MEDIUM" if row["_proxy_risk"] < 0.45 else "HIGH")
        row["model_version"] = MODEL_VERSIONS["recommendation"]
        ranked.append(row)

    ranked.sort(key=lambda r: r["recommendation_score"], reverse=True)
    if persist_events and passenger_id:
        for r in ranked[:10]:
            try:
                log_recommendation_event(passenger_id, r["flight_id"], "SHOWN", r["recommendation_score"])
            except Exception:
                pass
    return ranked


def ranking_metrics_at_k(relevance_lists, k):
    """
    relevance_lists: list of binary relevance arrays in ranked order
    (1 if the held-out chosen flight is at that rank).
    """
    precs, recs, ndcgs, aps, hits = [], [], [], [], []
    for rel in relevance_lists:
        rel = np.array(rel, dtype=float)
        top = rel[:k]
        n_rel = rel.sum()
        hits.append(1.0 if top.sum() > 0 else 0.0)
        precs.append(top.sum() / k)
        recs.append(top.sum() / n_rel if n_rel else 0.0)
        dcg = sum((2 ** r - 1) / np.log2(i + 2) for i, r in enumerate(top))
        ideal = sorted(rel, reverse=True)[:k]
        idcg = sum((2 ** r - 1) / np.log2(i + 2) for i, r in enumerate(ideal)) or 1.0
        ndcgs.append(dcg / idcg)
        # AP@K
        if n_rel == 0:
            aps.append(0.0)
        else:
            cum = 0.0
            hit = 0.0
            for i, r in enumerate(top, start=1):
                if r > 0:
                    hit += 1
                    cum += hit / i
            aps.append(cum / min(n_rel, k))
    def avg(xs):
        return float(np.mean(xs)) if xs else None
    p, r = avg(precs), avg(recs)
    f1 = (2 * p * r / (p + r)) if p and r else 0.0
    return {
        f"Precision@{k}": p,
        f"Recall@{k}": r,
        f"F1@{k}": f1,
        f"NDCG@{k}": avg(ndcgs),
        f"MAP@{k}": avg(aps),
        f"HitRate@{k}": avg(hits),
        "n_queries": len(relevance_lists),
    }
