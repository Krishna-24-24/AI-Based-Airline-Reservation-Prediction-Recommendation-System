"""
ml/feature_engineering.py
--------------------------------------------------------------------
Single source of truth for feature ORDER and ENCODING for both ML
models. Training scripts and runtime prediction modules both import
these constants/functions, so the features fed to the model at
prediction time can never silently drift out of sync with what the
model was trained on (a very common source of bugs in projects like
this one).
--------------------------------------------------------------------
"""

import pandas as pd

from config import CANCELLATION_RISK_THRESHOLDS, OCCUPANCY_LEVEL_THRESHOLDS

# ---------------------------------------------------------------------
# Model 1: Cancellation / No-Show risk (classification)
# ---------------------------------------------------------------------
CANCELLATION_FEATURES = [
    "days_before_departure",
    "ticket_fare",
    "passenger_age",
    "previous_bookings",
    "previous_cancellations",
    "previous_no_shows",
    "travel_frequency",
    "previous_completed_trips",
    "is_weekend",
    "flight_duration",
    "booking_lead_time",
]

CANCELLATION_TARGET = "cancelled_or_no_show"

# Cancellation features available at booking time only (no post-cancellation
# fields). previous_* counts use bookings with booking_id strictly less than
# the current booking so they cannot leak future behaviour.


def cancellation_risk_level(probability):
    if probability < CANCELLATION_RISK_THRESHOLDS["LOW_MAX"]:
        return "LOW"
    elif probability < CANCELLATION_RISK_THRESHOLDS["MEDIUM_MAX"]:
        return "MEDIUM"
    else:
        return "HIGH"


def build_cancellation_feature_row(**kwargs):
    """Builds a single-row DataFrame in the exact column order the model expects."""
    row = {feat: kwargs.get(feat, 0) for feat in CANCELLATION_FEATURES}
    return pd.DataFrame([row], columns=CANCELLATION_FEATURES)


# ---------------------------------------------------------------------
# Model 2: Flight Occupancy (regression)
# ---------------------------------------------------------------------
OCCUPANCY_NUMERIC_FEATURES = [
    "flight_capacity",
    "current_bookings",
    "days_before_departure",
    "historical_average_occupancy",
    "historical_cancellation_rate",
    "historical_no_show_rate",
    "route_demand",
    "day_of_week",
    "is_weekend",
]

# season is categorical -> one-hot encoded at both train and predict time
SEASONS = ["WINTER", "SUMMER", "MONSOON", "AUTUMN"]
OCCUPANCY_SEASON_COLUMNS = [f"season_{s}" for s in SEASONS]

OCCUPANCY_FEATURES = OCCUPANCY_NUMERIC_FEATURES + OCCUPANCY_SEASON_COLUMNS

OCCUPANCY_TARGET = "actual_passengers"

CLUSTERING_FEATURES = [
    "total_bookings",
    "completed_trips",
    "cancelled_bookings",
    "no_shows",
    "average_fare",
    "total_spend",
    "average_booking_lead_time",
    "travel_frequency",
    "average_trip_duration",
    "business_class_ratio",
]


def occupancy_level(pct):
    if pct < OCCUPANCY_LEVEL_THRESHOLDS["LOW_MAX"]:
        return "LOW"
    elif pct < OCCUPANCY_LEVEL_THRESHOLDS["MEDIUM_MAX"]:
        return "MEDIUM"
    else:
        return "HIGH"


def month_to_season(month):
    """India-centric season mapping used consistently across the project."""
    if month in (12, 1, 2):
        return "WINTER"
    elif month in (3, 4, 5):
        return "SUMMER"
    elif month in (6, 7, 8, 9):
        return "MONSOON"
    else:
        return "AUTUMN"


def build_occupancy_feature_row(season, **kwargs):
    """Builds a single-row DataFrame in the exact column order the model expects,
    including one-hot encoded season columns."""
    row = {feat: kwargs.get(feat, 0) for feat in OCCUPANCY_NUMERIC_FEATURES}
    for s in SEASONS:
        row[f"season_{s}"] = 1 if s == season else 0
    return pd.DataFrame([row], columns=OCCUPANCY_FEATURES)


def encode_season_column(df, season_col="season"):
    """Used during training: turns a raw `season` text column into the
    one-hot columns defined by OCCUPANCY_SEASON_COLUMNS, guaranteeing all
    columns exist (even if a season never appears in the training sample)."""
    for s in SEASONS:
        df[f"season_{s}"] = (df[season_col] == s).astype(int)
    return df
