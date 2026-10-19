"""Synthetic leave-one-out ranking dataset with a meaningful chosen-flight process."""

import os

import numpy as np
import pandas as pd

np.random.seed(21)
N_QUERIES = 400
CANDIDATES = 8


def generate():
    rows = []
    qid = 0
    for _ in range(N_QUERIES):
        qid += 1
        n = np.random.randint(5, CANDIDATES + 1)
        fare = np.random.uniform(2800, 12000, n)
        duration = np.random.randint(70, 220, n)
        available = np.random.randint(2, 60, n)
        occupancy = np.random.uniform(40, 98, n)
        risk = np.random.uniform(0.05, 0.55, n)
        # passenger preference in [0,1] — higher for cheaper + lower risk + moderate occ
        pref = np.clip(1 - (fare - fare.min()) / (fare.max() - fare.min() + 1e-6), 0, 1)
        pref = 0.5 * pref + 0.5 * (1 - risk)
        # probability of being chosen: similar to ranking score plus noise
        util = (
            0.30 * (1 - (fare - fare.min()) / (fare.max() - fare.min() + 1e-6))
            + 0.20 * (1 - (duration - duration.min()) / (duration.max() - duration.min() + 1e-6))
            + 0.15 * (available / available.max())
            + 0.15 * (1 - np.abs(occupancy - 75) / 75)
            + 0.10 * pref
            + 0.10 * (1 - risk)
        )
        util = util + np.random.normal(0, 0.05, n)
        chosen_idx = int(np.argmax(util))
        for i in range(n):
            rows.append({
                "query_id": qid,
                "fare": round(fare[i], 2),
                "duration_minutes": int(duration[i]),
                "available_seats": int(available[i]),
                "occupancy_pct": round(occupancy[i], 2),
                "risk": round(risk[i], 4),
                "preference": round(pref[i], 4),
                "chosen": 1 if i == chosen_idx else 0,
            })
    return pd.DataFrame(rows)


def main():
    df = generate()
    os.makedirs("data", exist_ok=True)
    path = os.path.join("data", "recommendation_history.csv")
    df.to_csv(path, index=False)
    print(f"Wrote {len(df)} rows / {df['query_id'].nunique()} queries to {path}")


if __name__ == "__main__":
    main()
