"""
Central configuration. Thresholds and recommendation weights live here
so they are never copy-pasted through the codebase.
"""

import os
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", 3306))
DB_NAME = os.environ.get("DB_NAME", "airline_ai_system")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

CANCELLATION_RISK_THRESHOLDS = {
    "LOW_MAX": float(os.environ.get("CANCEL_LOW_MAX", "0.40")),
    "MEDIUM_MAX": float(os.environ.get("CANCEL_MEDIUM_MAX", "0.70")),
}

OCCUPANCY_LEVEL_THRESHOLDS = {
    "LOW_MAX": float(os.environ.get("OCC_LOW_MAX", "60.0")),
    "MEDIUM_MAX": float(os.environ.get("OCC_MEDIUM_MAX", "85.0")),
}

RECOMMENDATION_WEIGHTS = {
    "fare_weight": 0.25,
    "duration_weight": 0.20,
    "availability_weight": 0.15,
    "occupancy_weight": 0.15,
    "preference_weight": 0.15,
    "risk_weight": 0.10,
}

MODEL_VERSIONS = {
    "cancellation": "cancellation_rf_v1.2",
    "occupancy": "occupancy_rf_v1.1",
    "clustering": "clustering_kmeans_v1.0",
    "recommendation": "recommendation_v1.0",
}

REFUND_POLICY = {
    "gt_7_days": 0.90,
    "between_2_and_7_days": 0.50,
    "lt_2_days": 0.00,
}

SEAT_CLASS_FARE_MULTIPLIER = {
    "ECONOMY": 1.00,
    "PREMIUM_ECONOMY": 1.25,
    "BUSINESS": 1.60,
}


def utc_now_iso():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
