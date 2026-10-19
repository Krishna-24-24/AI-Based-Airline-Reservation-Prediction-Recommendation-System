"""K-Means passenger segmentation. K chosen by silhouette among k=2..6."""

import json
import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score
from sklearn.preprocessing import StandardScaler

sys.path.append(".")
from config import MODEL_VERSIONS, utc_now_iso
from ml.evaluation import write_json
from ml.feature_engineering import CLUSTERING_FEATURES

DATA_PATH = os.path.join("data", "passenger_behavior.csv")
MODEL_PATH = os.path.join("models", "clustering_model.pkl")
EVAL_PATH = os.path.join("evaluation", "clustering_results.json")
META_PATH = os.path.join("models", "model_metadata.json")


def name_clusters(df, labels):
    """Assign human labels AFTER clustering from actual centroid stats."""
    df = df.copy()
    df["cluster"] = labels
    names = {}
    for cid, g in df.groupby("cluster"):
        cancel_rate = g["cancelled_bookings"].sum() / max(g["total_bookings"].sum(), 1)
        avg_bookings = g["total_bookings"].mean()
        avg_spend = g["total_spend"].mean()
        biz = g["business_class_ratio"].mean()
        tags = []
        if cancel_rate >= 0.22:
            tags.append("High Cancellation Risk")
        if avg_bookings >= 8:
            tags.append("Frequent Travelers")
        elif avg_bookings <= 3.5:
            tags.append("Occasional Travelers")
        if avg_spend >= 80000 or biz >= 0.35:
            tags.append("Premium/High-Spending")
        if not tags:
            tags.append("Mainstream Travelers")
        names[int(cid)] = " / ".join(tags)
    return names


def main():
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError("Run models/generate_passenger_segments.py first.")
    df = pd.read_csv(DATA_PATH)
    X = df[CLUSTERING_FEATURES].values
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)

    k_results = []
    inertias = []
    sils = []
    best = None
    for k in range(2, 7):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(Xs)
        sil = float(silhouette_score(Xs, labels))
        dbi = float(davies_bouldin_score(Xs, labels))
        ch = float(calinski_harabasz_score(Xs, labels))
        inertias.append(float(km.inertia_))
        sils.append(sil)
        rec = {"k": k, "silhouette": sil, "davies_bouldin": dbi, "calinski_harabasz": ch, "inertia": float(km.inertia_)}
        k_results.append(rec)
        print(f"k={k}  sil={sil:.4f}  DB={dbi:.4f}  CH={ch:.1f}")
        if best is None or sil > best["silhouette"]:
            best = rec
            best_model = km
            best_labels = labels

    names = name_clusters(df, best_labels)
    profiles = []
    tmp = df.copy()
    tmp["cluster"] = best_labels
    for cid, g in tmp.groupby("cluster"):
        profiles.append({
            "cluster_id": int(cid),
            "cluster_label": names[int(cid)],
            "passengers": int(len(g)),
            "average_bookings": float(g["total_bookings"].mean()),
            "average_spend": float(g["total_spend"].mean()),
            "average_fare": float(g["average_fare"].mean()),
            "cancellation_rate": float(g["cancelled_bookings"].sum() / max(g["total_bookings"].sum(), 1)),
            "business_class_ratio": float(g["business_class_ratio"].mean()),
        })

    os.makedirs("models", exist_ok=True)
    joblib.dump({
        "model": best_model,
        "scaler": scaler,
        "features": CLUSTERING_FEATURES,
        "k": best["k"],
        "cluster_labels": names,
        "model_version": MODEL_VERSIONS["clustering"],
        "trained_at": utc_now_iso(),
        "dataset_size": int(len(df)),
        "metrics": best,
        "profiles": profiles,
    }, MODEL_PATH)

    write_json(EVAL_PATH, {
        "model_name": "KMeans",
        "model_version": MODEL_VERSIONS["clustering"],
        "dataset_size": int(len(df)),
        "optimal_k": best["k"],
        "selection_rule": "Highest silhouette score among k=2..6; elbow inertia also recorded.",
        "k_search": k_results,
        "elbow_inertia": inertias,
        "silhouette_by_k": sils,
        "metrics": best,
        "cluster_labels": names,
        "profiles": profiles,
        "pca_sample": _pca_sample(Xs, best_labels),
    })
    meta = {}
    if os.path.exists(META_PATH):
        with open(META_PATH, encoding="utf-8") as f:
            meta = json.load(f)
    meta["clustering"] = {
        "model_name": "KMeans",
        "model_version": MODEL_VERSIONS["clustering"],
        "training_date": utc_now_iso(),
        "dataset_size": int(len(df)),
        "features": CLUSTERING_FEATURES,
        "metrics": best,
        "optimal_k": best["k"],
    }
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"\nSelected k={best['k']}  {names}")
    print(f"Saved {MODEL_PATH} and {EVAL_PATH}")


def _pca_sample(Xs, labels, n=400):
    from sklearn.decomposition import PCA
    pca = PCA(n_components=2, random_state=42)
    xy = pca.fit_transform(Xs)
    idx = np.linspace(0, len(Xs) - 1, min(n, len(Xs))).astype(int)
    return {
        "x": xy[idx, 0].tolist(),
        "y": xy[idx, 1].tolist(),
        "cluster": labels[idx].tolist(),
        "explained_variance": pca.explained_variance_ratio_.tolist(),
    }


if __name__ == "__main__":
    main()
