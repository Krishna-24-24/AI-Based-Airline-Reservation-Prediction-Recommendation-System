"""
Offline ranking evaluation from historical choices.

For each synthetic passenger with enough flights on a route:
hide the chosen flight, rank the rest + the hidden one, measure Top-K hits.

If the CSV is missing or too thin, writes a results file that says so
without fabricating numbers.
"""

import json
import os
import sys

import joblib
import numpy as np
import pandas as pd

sys.path.append(".")
from config import MODEL_VERSIONS, RECOMMENDATION_WEIGHTS, utc_now_iso
from ml.evaluation import write_json
from ml.recommendation_engine import ranking_metrics_at_k

DATA_PATH = os.path.join("data", "recommendation_history.csv")
EVAL_PATH = os.path.join("evaluation", "recommendation_results.json")
CONFIG_PATH = os.path.join("models", "recommendation_config.pkl")
META_PATH = os.path.join("models", "model_metadata.json")
MIN_QUERIES = 30


def _score_group(g):
    """Score candidates inside one (passenger, origin, dest, date) group."""
    fares = g["fare"].astype(float).values
    durs = g["duration_minutes"].astype(float).values
    avails = g["available_seats"].astype(float).values
    occ = g["occupancy_pct"].astype(float).values
    risk = g["risk"].astype(float).values
    pref = g["preference"].astype(float).values

    def mm(a, invert=False):
        lo, hi = np.min(a), np.max(a)
        if hi - lo < 1e-9:
            s = np.ones_like(a) * 0.5
        else:
            s = (a - lo) / (hi - lo)
        return 1 - s if invert else s

    w = RECOMMENDATION_WEIGHTS
    occ_s = np.clip(1.0 - np.abs(occ - 75.0) / 75.0, 0, 1)
    score = 100 * (
        w["fare_weight"] * mm(fares, True)
        + w["duration_weight"] * mm(durs, True)
        + w["availability_weight"] * mm(avails, False)
        + w["occupancy_weight"] * occ_s
        + w["preference_weight"] * pref
        + w["risk_weight"] * mm(risk, True)
    )
    return score


def main():
    os.makedirs("models", exist_ok=True)
    joblib.dump({
        "weights": RECOMMENDATION_WEIGHTS,
        "model_version": MODEL_VERSIONS["recommendation"],
        "trained_at": utc_now_iso(),
    }, CONFIG_PATH)

    if not os.path.exists(DATA_PATH):
        write_json(EVAL_PATH, {
            "status": "insufficient_data",
            "message": "No recommendation_history.csv. Pipeline is implemented; run generate script then re-evaluate.",
            "metrics": {},
        })
        print("No recommendation history CSV — wrote insufficient_data status.")
        return

    df = pd.read_csv(DATA_PATH)
    relevance_lists = []
    for _, g in df.groupby(["query_id"]):
        if len(g) < 3:
            continue
        scores = _score_group(g)
        order = np.argsort(-scores)
        chosen = g["chosen"].values[order]
        relevance_lists.append(chosen.astype(float))

    if len(relevance_lists) < MIN_QUERIES:
        write_json(EVAL_PATH, {
            "status": "insufficient_data",
            "message": (
                f"Only {len(relevance_lists)} valid leave-one-out queries "
                f"(need {MIN_QUERIES}). Metrics are not reported."
            ),
            "n_queries": len(relevance_lists),
            "metrics": {},
        })
        print(f"Insufficient queries ({len(relevance_lists)}).")
        return

    metrics = {}
    for k in (3, 5, 10):
        metrics.update(ranking_metrics_at_k(relevance_lists, k))

    write_json(EVAL_PATH, {
        "status": "ok",
        "model_version": MODEL_VERSIONS["recommendation"],
        "n_queries": len(relevance_lists),
        "k_values": [3, 5, 10],
        "protocol": "Leave-one-out: hide historically chosen flight, rank candidates, measure Top-K.",
        "metrics": metrics,
        "weights": RECOMMENDATION_WEIGHTS,
    })
    meta = {}
    if os.path.exists(META_PATH):
        with open(META_PATH, encoding="utf-8") as f:
            meta = json.load(f)
    meta["recommendation"] = {
        "model_name": "hybrid_score",
        "model_version": MODEL_VERSIONS["recommendation"],
        "training_date": utc_now_iso(),
        "dataset_size": int(len(df)),
        "metrics": {k: metrics[k] for k in metrics if k.startswith(("Precision", "Recall", "NDCG", "MAP", "Hit"))},
    }
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(json.dumps(metrics, indent=2))
    print(f"Saved {EVAL_PATH}")


if __name__ == "__main__":
    main()
