"""Synthetic passenger behaviour for clustering — labels are NOT pre-assigned."""

import os

import numpy as np
import pandas as pd

np.random.seed(11)
N = 2500


def generate():
    # Mix of latent behaviours (used only to generate features, not as training labels)
    latent = np.random.choice(["frequent", "occasional", "premium", "risky"], size=N, p=[0.22, 0.45, 0.18, 0.15])
    total_bookings = np.zeros(N, dtype=int)
    cancelled = np.zeros(N, dtype=int)
    avg_fare = np.zeros(N)
    total_spend = np.zeros(N)
    lead = np.zeros(N)
    duration = np.zeros(N)
    biz = np.zeros(N)

    for i, kind in enumerate(latent):
        if kind == "frequent":
            total_bookings[i] = np.random.randint(8, 25)
            cancelled[i] = np.random.binomial(total_bookings[i], 0.06)
            avg_fare[i] = np.random.normal(6500, 800)
            lead[i] = np.random.normal(18, 6)
            duration[i] = np.random.normal(120, 20)
            biz[i] = np.random.beta(1.5, 6)
        elif kind == "occasional":
            total_bookings[i] = np.random.randint(1, 5)
            cancelled[i] = np.random.binomial(total_bookings[i], 0.12)
            avg_fare[i] = np.random.normal(4800, 900)
            lead[i] = np.random.normal(25, 10)
            duration[i] = np.random.normal(110, 25)
            biz[i] = np.random.beta(1, 10)
        elif kind == "premium":
            total_bookings[i] = np.random.randint(4, 16)
            cancelled[i] = np.random.binomial(total_bookings[i], 0.05)
            avg_fare[i] = np.random.normal(14000, 2500)
            lead[i] = np.random.normal(12, 5)
            duration[i] = np.random.normal(140, 25)
            biz[i] = np.random.beta(6, 2)
        else:
            total_bookings[i] = np.random.randint(3, 12)
            cancelled[i] = np.random.binomial(total_bookings[i], 0.32)
            avg_fare[i] = np.random.normal(4200, 1000)
            lead[i] = np.random.normal(4, 3)
            duration[i] = np.random.normal(100, 20)
            biz[i] = np.random.beta(1, 8)

    completed = (total_bookings - cancelled).clip(min=0)
    no_shows = np.array([np.random.binomial(max(c, 0), 0.35) for c in cancelled])
    avg_fare = avg_fare.clip(1500, 30000)
    total_spend = (completed * avg_fare).clip(min=0)
    lead = lead.clip(0, 90)
    duration = duration.clip(60, 240)
    biz = biz.clip(0, 1)
    travel_frequency = completed + cancelled

    return pd.DataFrame({
        "total_bookings": total_bookings,
        "completed_trips": completed,
        "cancelled_bookings": cancelled,
        "no_shows": no_shows,
        "average_fare": avg_fare.round(2),
        "total_spend": total_spend.round(2),
        "average_booking_lead_time": lead.round(2),
        "travel_frequency": travel_frequency,
        "average_trip_duration": duration.round(2),
        "business_class_ratio": biz.round(4),
    })


def main():
    df = generate()
    os.makedirs("data", exist_ok=True)
    path = os.path.join("data", "passenger_behavior.csv")
    df.to_csv(path, index=False)
    print(f"Wrote {len(df)} rows to {path}")


if __name__ == "__main__":
    main()
