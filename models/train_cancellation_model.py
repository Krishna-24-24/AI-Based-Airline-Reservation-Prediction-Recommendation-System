"""Train RF classifier vs Logistic Regression baseline. Writes real test-set metrics."""

import os
import sys

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

sys.path.append(".")
from config import MODEL_VERSIONS, utc_now_iso
from ml.evaluation import classification_metrics, write_json
from ml.feature_engineering import CANCELLATION_FEATURES, CANCELLATION_TARGET

DATA_PATH = os.path.join("data", "airline_booking_history.csv")
MODEL_PATH = os.path.join("models", "cancellation_model.pkl")
EVAL_PATH = os.path.join("evaluation", "classification_results.json")
META_PATH = os.path.join("models", "model_metadata.json")


def load_data():
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"{DATA_PATH} not found. Run generate_booking_history.py first.")
    return pd.read_csv(DATA_PATH)


def main():
    df = load_data()
    X = df[CANCELLATION_FEATURES]
    y = df[CANCELLATION_TARGET]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    rf = RandomForestClassifier(
        n_estimators=150, max_depth=8, min_samples_leaf=6,
        class_weight="balanced", random_state=42, n_jobs=-1,
    )
    rf.fit(X_train, y_train)
    lr = LogisticRegression(max_iter=5000, class_weight="balanced")
    lr.fit(X_train, y_train)

    rf_proba = rf.predict_proba(X_test)[:, 1]
    lr_proba = lr.predict_proba(X_test)[:, 1]
    rf_pred = (rf_proba >= 0.5).astype(int)
    lr_pred = lr.predict(X_test)

    rf_imp = pd.Series(rf.feature_importances_, index=CANCELLATION_FEATURES).sort_values(ascending=False)
    rf_metrics = classification_metrics(y_test, rf_pred, rf_proba, rf_imp.round(4).to_dict())
    lr_metrics = classification_metrics(y_test, lr_pred, lr_proba)

    print("\n=== Random Forest Classifier (primary) ===")
    for k in ("accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc"):
        print(f"{k:10s}: {rf_metrics[k]:.4f}")
    print("confusion:", rf_metrics["confusion_matrix"])
    print("\n=== Logistic Regression (baseline) ===")
    for k in ("accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc"):
        print(f"{k:10s}: {lr_metrics[k]:.4f}")

    if lr_metrics["f1"] > rf_metrics["f1"] + 0.03:
        best, name, metrics = lr, "LogisticRegression", lr_metrics
    else:
        best, name, metrics = rf, "RandomForestClassifier", rf_metrics

    os.makedirs("models", exist_ok=True)
    bundle = {
        "model": best,
        "model_type": name,
        "features": CANCELLATION_FEATURES,
        "model_version": MODEL_VERSIONS["cancellation"],
        "trained_at": utc_now_iso(),
        "dataset_size": int(len(df)),
        "metrics": metrics,
        "comparison": {"random_forest": rf_metrics, "logistic_regression": lr_metrics},
    }
    joblib.dump(bundle, MODEL_PATH)
    write_json(EVAL_PATH, {
        "model_name": name,
        "model_version": MODEL_VERSIONS["cancellation"],
        "dataset_size": int(len(df)),
        "train_size": int(len(X_train)),
        "test_size": int(len(X_test)),
        "primary": rf_metrics,
        "baseline": lr_metrics,
        "selected": name,
        "feature_availability": (
            "All cancellation features are known at booking time. "
            "previous_* counts exclude the current booking and later rows."
        ),
    })
    _merge_metadata({
        "cancellation": {
            "model_name": name,
            "model_version": MODEL_VERSIONS["cancellation"],
            "training_date": utc_now_iso(),
            "dataset_size": int(len(df)),
            "features": CANCELLATION_FEATURES,
            "metrics": {k: metrics[k] for k in ("accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc")},
        }
    })
    print(f"\nSaved {MODEL_PATH} and {EVAL_PATH}")


def _merge_metadata(update):
    import json
    meta = {}
    if os.path.exists(META_PATH):
        with open(META_PATH, encoding="utf-8") as f:
            meta = json.load(f)
    meta.update(update)
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


if __name__ == "__main__":
    main()
