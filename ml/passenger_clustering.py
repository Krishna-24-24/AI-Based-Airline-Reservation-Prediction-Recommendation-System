"""Runtime passenger segmentation using the saved K-Means model."""

import os

import joblib
import numpy as np
import pandas as pd

from config import MODEL_VERSIONS
from database.db_connection import fetch_passenger_feature_rows, save_passenger_cluster
from ml.feature_engineering import CLUSTERING_FEATURES  # defined below if missing

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "clustering_model.pkl")
_model_cache = None

# Imported after we add CLUSTERING_FEATURES to feature_engineering.


def _load():
    global _model_cache
    if _model_cache is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError("Clustering model not found. Run models/train_clustering_model.py")
        _model_cache = joblib.load(MODEL_PATH)
    return _model_cache


def _rows_to_frame(rows):
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["no_shows"] = (df["cancelled_bookings"] * 0.35).round()
    df["travel_frequency"] = df["completed_trips"] + df["cancelled_bookings"]
    for col in CLUSTERING_FEATURES:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def assign_all_passengers(persist=True):
    bundle = _load()
    rows = fetch_passenger_feature_rows()
    df = _rows_to_frame(rows)
    if df.empty:
        return []
    X = df[CLUSTERING_FEATURES].values
    Xs = bundle["scaler"].transform(X)
    labels = bundle["model"].predict(Xs)
    label_map = bundle.get("cluster_labels", {})
    version = bundle.get("model_version", MODEL_VERSIONS["clustering"])
    results = []
    for rec, lab in zip(df.to_dict("records"), labels):
        name = label_map.get(int(lab), f"Cluster {lab}")
        item = {
            "passenger_id": int(rec["passenger_id"]),
            "cluster_id": int(lab),
            "cluster_label": name,
            **{k: rec[k] for k in CLUSTERING_FEATURES if k in rec},
        }
        results.append(item)
        if persist:
            save_passenger_cluster(item["passenger_id"], item["cluster_id"], name, version)
    return results


def cluster_profiles(assignments):
    if not assignments:
        return []
    df = pd.DataFrame(assignments)
    profiles = []
    for cid, g in df.groupby("cluster_id"):
        cancel_rate = (g["cancelled_bookings"].sum() / max(g["total_bookings"].sum(), 1))
        profiles.append({
            "cluster_id": int(cid),
            "cluster_label": g["cluster_label"].iloc[0],
            "passengers": int(len(g)),
            "average_bookings": float(g["total_bookings"].mean()),
            "average_spend": float(g["total_spend"].mean()),
            "average_fare": float(g["average_fare"].mean()),
            "cancellation_rate": float(cancel_rate),
            "business_class_ratio": float(g["business_class_ratio"].mean()),
        })
    return profiles


def predict_passenger_cluster(passenger_id):
    bundle = _load()
    rows = fetch_passenger_feature_rows()
    df = _rows_to_frame(rows)
    row = df[df["passenger_id"] == passenger_id]
    if row.empty:
        return None
    Xs = bundle["scaler"].transform(row[CLUSTERING_FEATURES].values)
    lab = int(bundle["model"].predict(Xs)[0])
    return {
        "cluster_id": lab,
        "cluster_label": bundle.get("cluster_labels", {}).get(lab, f"Cluster {lab}"),
        "model_version": bundle.get("model_version", MODEL_VERSIONS["clustering"]),
    }
