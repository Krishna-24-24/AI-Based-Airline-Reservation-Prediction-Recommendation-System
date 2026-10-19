"""Runtime cancellation / no-show risk. Model is loaded once, never retrained here."""

import os
from datetime import date, datetime
import time

import joblib

from config import MODEL_VERSIONS
from database.db_connection import count_passenger_history, get_booking_by_id, record_metric, save_prediction
from ml.explainability import explain_cancellation_risk
from ml.feature_engineering import build_cancellation_feature_row, cancellation_risk_level

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "cancellation_model.pkl")
_model_cache = None


def _load_model():
    global _model_cache
    if _model_cache is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                "Cancellation model not found. Run `python models/train_cancellation_model.py` first."
            )
        _model_cache = joblib.load(MODEL_PATH)
    return _model_cache


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def predict_cancellation_risk(booking_id, persist=True):
    started = time.perf_counter()
    booking = get_booking_by_id(booking_id)
    if booking is None:
        raise ValueError(f"Booking {booking_id} not found.")

    history = count_passenger_history(booking["passenger_id"], before_booking_id=booking_id)

    travel_date = _as_date(booking["travel_date"])
    booking_date = booking["booking_date"]
    booking_date = booking_date.date() if isinstance(booking_date, datetime) else _as_date(booking_date)

    days_before_departure = max((travel_date - date.today()).days, 0)
    booking_lead_time = max((travel_date - booking_date).days, 0)
    is_weekend = 1 if travel_date.weekday() >= 5 else 0
    previous_no_shows = round(history["previous_cancellations"] * 0.35)

    feat_kwargs = dict(
        days_before_departure=days_before_departure,
        ticket_fare=float(booking["fare"]),
        passenger_age=int(booking["passenger_age"]),
        previous_bookings=history["previous_bookings"],
        previous_cancellations=history["previous_cancellations"],
        previous_no_shows=previous_no_shows,
        travel_frequency=history["previous_completed_trips"] + history["previous_cancellations"],
        previous_completed_trips=history["previous_completed_trips"],
        is_weekend=is_weekend,
        flight_duration=int(booking["duration_minutes"]),
        booking_lead_time=booking_lead_time,
    )
    features = build_cancellation_feature_row(**feat_kwargs)

    bundle = _load_model()
    model = bundle["model"]
    probability = float(model.predict_proba(features)[0][1])
    probability = min(max(probability, 0.0), 1.0)
    risk_level = cancellation_risk_level(probability)
    version = bundle.get("model_version", MODEL_VERSIONS["cancellation"])
    explanation = explain_cancellation_risk(feat_kwargs, probability, risk_level)

    if persist:
        save_prediction(
            flight_id=booking["flight_id"],
            booking_id=booking_id,
            passenger_id=booking["passenger_id"],
            cancellation_probability=round(probability, 4),
            cancellation_risk=risk_level,
            prediction_type="CANCELLATION_RISK",
            recommendation="; ".join(explanation["reasons"][:3]),
            model_version=version,
        )

    record_metric("ml_prediction", (time.perf_counter() - started) * 1000.0)
    return {
        "booking_id": booking_id,
        "probability": probability,
        "risk_level": risk_level,
        "features_used": feat_kwargs,
        "explanation": explanation,
        "model_version": version,
    }
