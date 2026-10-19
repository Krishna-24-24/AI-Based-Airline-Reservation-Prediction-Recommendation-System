"""
models/generate_booking_history.py
--------------------------------------------------------------------
Generates a realistic SYNTHETIC dataset for training the
cancellation/no-show risk classifier, since a real airline dataset
isn't available.

The target `cancelled_or_no_show` is NOT random: it is built from a
logistic function of the features, so the relationships a real
airline would expect actually hold in the data, e.g.:
    - very late bookings (short lead time)          -> higher risk
    - more previous cancellations / no-shows          -> higher risk
    - long-time, frequent, loyal travellers            -> lower risk
    - higher fare (more "skin in the game")             -> slightly lower risk

Run:
    python models/generate_booking_history.py
Produces:
    data/airline_booking_history.csv
--------------------------------------------------------------------
"""

import os

import numpy as np
import pandas as pd

np.random.seed(42)

N_RECORDS = 8000


def generate():
    days_before_departure = np.random.exponential(scale=20, size=N_RECORDS).clip(0, 180).round().astype(int)
    booking_lead_time = (days_before_departure + np.random.normal(0, 3, N_RECORDS)).clip(0, 180).round().astype(int)

    ticket_fare = np.random.normal(6000, 2200, N_RECORDS).clip(1500, 20000).round(2)
    passenger_age = np.random.randint(18, 75, N_RECORDS)

    previous_bookings = np.random.poisson(4, N_RECORDS)
    # cancellations/no-shows can't exceed previous bookings
    previous_cancellations = np.array([
        np.random.binomial(n, 0.15) for n in previous_bookings
    ])
    previous_no_shows = np.array([
        np.random.binomial(max(n - c, 0), 0.08) for n, c in zip(previous_bookings, previous_cancellations)
    ])
    previous_completed_trips = (previous_bookings - previous_cancellations - previous_no_shows).clip(min=0)

    travel_frequency = np.random.poisson(3, N_RECORDS)  # trips per year
    is_weekend = np.random.binomial(1, 0.28, N_RECORDS)
    flight_duration = np.random.randint(60, 240, N_RECORDS)  # minutes

    # -----------------------------------------------------------------
    # Build the target with a genuine (noisy) logistic relationship.
    # -----------------------------------------------------------------
    logit = (
        -2.0
        + 0.020 * days_before_departure          # booked far ahead -> more time for plans to change -> slightly higher risk
        + 0.35 * previous_cancellations           # a history of cancelling -> higher risk
        + 0.45 * previous_no_shows                # a history of no-shows -> higher risk
        - 0.10 * previous_completed_trips         # loyal, reliable travellers -> lower risk
        - 0.00012 * ticket_fare                   # more money on the line -> slightly lower risk
        - 0.05 * travel_frequency                 # frequent flyers are more predictable -> lower risk
        + 0.30 * is_weekend                       # weekend trips (leisure) cancel more than weekday (business)
        + 0.003 * flight_duration                 # longer flights, slightly higher risk
    )

    # very-last-minute bookings are historically MORE likely to end in a no-show
    last_minute_penalty = np.where(booking_lead_time < 3, 0.9, 0.0)
    logit += last_minute_penalty

    prob = 1 / (1 + np.exp(-logit))
    noise = np.random.normal(0, 0.05, N_RECORDS)
    prob_noisy = np.clip(prob + noise, 0.01, 0.99)

    cancelled_or_no_show = np.random.binomial(1, prob_noisy)

    df = pd.DataFrame({
        "days_before_departure": days_before_departure,
        "ticket_fare": ticket_fare,
        "passenger_age": passenger_age,
        "previous_bookings": previous_bookings,
        "previous_cancellations": previous_cancellations,
        "previous_no_shows": previous_no_shows,
        "travel_frequency": travel_frequency,
        "previous_completed_trips": previous_completed_trips,
        "is_weekend": is_weekend,
        "flight_duration": flight_duration,
        "booking_lead_time": booking_lead_time,
        "cancelled_or_no_show": cancelled_or_no_show,
    })

    return df


def main():
    df = generate()
    os.makedirs("data", exist_ok=True)
    out_path = os.path.join("data", "airline_booking_history.csv")
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} rows to {out_path}")
    print(f"Positive class rate (cancelled_or_no_show=1): {df['cancelled_or_no_show'].mean():.3f}")


if __name__ == "__main__":
    main()
