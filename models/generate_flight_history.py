"""
models/generate_flight_history.py
--------------------------------------------------------------------
Generates a realistic SYNTHETIC dataset for training the flight
occupancy regressor, since a real airline dataset isn't available.

actual_passengers is built from current_bookings minus a realistic
number of cancellations/no-shows (driven by historical_cancellation_rate
and historical_no_show_rate), not from random noise, so the model
learns a genuine relationship.

Run:
    python models/generate_flight_history.py
Produces:
    data/flight_history.csv
--------------------------------------------------------------------
"""

import os

import numpy as np
import pandas as pd

import sys
sys.path.append(".")
from ml.feature_engineering import SEASONS  # noqa: E402

np.random.seed(7)

N_RECORDS = 6000


def generate():
    flight_capacity = np.random.choice([120, 150, 168, 180, 220], size=N_RECORDS)

    days_before_departure = np.random.exponential(scale=15, size=N_RECORDS).clip(0, 120).round().astype(int)

    # bookings fill up as departure approaches: booking_progress in [0,1]
    booking_progress = np.clip(1 - (days_before_departure / 120), 0.05, 0.99)
    route_demand = np.random.uniform(0.5, 1.3, N_RECORDS)  # relative demand multiplier for the route

    current_bookings = (flight_capacity * booking_progress * route_demand).round().clip(0, flight_capacity).astype(int)

    historical_average_occupancy = np.random.normal(78, 10, N_RECORDS).clip(40, 99)
    historical_cancellation_rate = np.random.normal(0.08, 0.03, N_RECORDS).clip(0.01, 0.30)
    historical_no_show_rate = np.random.normal(0.04, 0.02, N_RECORDS).clip(0.005, 0.20)

    day_of_week = np.random.randint(0, 7, N_RECORDS)  # 0=Mon ... 6=Sun
    is_weekend = (day_of_week >= 5).astype(int)

    season = np.random.choice(SEASONS, size=N_RECORDS)

    # -----------------------------------------------------------------
    # actual_passengers = current_bookings minus the passengers who,
    # based on this flight's historical cancellation/no-show behaviour,
    # are expected to not travel -- plus a little noise for realism.
    # -----------------------------------------------------------------
    expected_drop_rate = historical_cancellation_rate + historical_no_show_rate
    expected_no_shows = current_bookings * expected_drop_rate
    noise = np.random.normal(0, current_bookings * 0.03 + 0.5, N_RECORDS)

    actual_passengers = (current_bookings - expected_no_shows + noise).round().clip(0, flight_capacity).astype(int)

    df = pd.DataFrame({
        "flight_capacity": flight_capacity,
        "current_bookings": current_bookings,
        "days_before_departure": days_before_departure,
        "historical_average_occupancy": historical_average_occupancy.round(2),
        "historical_cancellation_rate": historical_cancellation_rate.round(4),
        "historical_no_show_rate": historical_no_show_rate.round(4),
        "route_demand": route_demand.round(3),
        "day_of_week": day_of_week,
        "is_weekend": is_weekend,
        "season": season,
        "actual_passengers": actual_passengers,
    })

    return df


def main():
    df = generate()
    os.makedirs("data", exist_ok=True)
    out_path = os.path.join("data", "flight_history.csv")
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} rows to {out_path}")
    print(f"Mean occupancy: {(df['actual_passengers'] / df['flight_capacity']).mean() * 100:.1f}%")


if __name__ == "__main__":
    main()
