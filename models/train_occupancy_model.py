"""Train RF regressor vs Linear Regression baseline. Writes real test-set metrics."""

import os
import sys

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split

sys.path.append(".")
from config import MODEL_VERSIONS, utc_now_iso
from ml.evaluation import regression_metrics, write_json
from ml.feature_engineering import OCCUPANCY_FEATURES, OCCUPANCY_TARGET, encode_season_column

DATA_PATH = os.path.join("data", "flight_history.csv")
MODEL_PATH = os.path.join("models", "occupancy_model.pkl")
EVAL_PATH = os.path.join("evaluation", "regression_results.json")
META_PATH = os.path.join("models", "model_metadata.json")


def load_data():
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"{DATA_PATH} not found. Run generate_flight_history.py first.")
    df = pd.read_csv(DATA_PATH)
    return encode_season_column(df, season_col="season")


def main():
    df = load_data()
    X = df[OCCUPANCY_FEATURES]
    y = df[OCCUPANCY_TARGET]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    rf = RandomForestRegressor(
        n_estimators=100, max_depth=8, min_samples_leaf=8, random_state=42, n_jobs=-1,
    )
    rf.fit(X_train, y_train)
    lr = LinearRegression()
    lr.fit(X_train, y_train)

    rf_pred = rf.predict(X_test)
    lr_pred = lr.predict(X_test)
    rf_imp = pd.Series(rf.feature_importances_, index=OCCUPANCY_FEATURES).sort_values(ascending=False)
    rf_metrics = regression_metrics(y_test, rf_pred, rf_imp.round(4).to_dict())
    lr_metrics = regression_metrics(y_test, lr_pred)

    print("\n=== Random Forest Regressor (primary) ===")
    print(f"MAE {rf_metrics['mae']:.3f}  RMSE {rf_metrics['rmse']:.3f}  R2 {rf_metrics['r2']:.4f}  MAPE {rf_metrics['mape']:.2f}%")
    print("\n=== Linear Regression (baseline) ===")
    print(f"MAE {lr_metrics['mae']:.3f}  RMSE {lr_metrics['rmse']:.3f}  R2 {lr_metrics['r2']:.4f}  MAPE {lr_metrics['mape']:.2f}%")

    if lr_metrics["r2"] > rf_metrics["r2"] + 0.01:
        best, name, metrics = lr, "LinearRegression", lr_metrics
    else:
        best, name, metrics = rf, "RandomForestRegressor", rf_metrics

    os.makedirs("models", exist_ok=True)
    joblib.dump({
        "model": best,
        "model_type": name,
        "features": OCCUPANCY_FEATURES,
        "model_version": MODEL_VERSIONS["occupancy"],
        "trained_at": utc_now_iso(),
        "dataset_size": int(len(df)),
        "metrics": metrics,
    }, MODEL_PATH)
    write_json(EVAL_PATH, {
        "model_name": name,
        "model_version": MODEL_VERSIONS["occupancy"],
        "dataset_size": int(len(df)),
        "train_size": int(len(X_train)),
        "test_size": int(len(X_test)),
        "primary": {k: rf_metrics[k] for k in ("mae", "mse", "rmse", "r2", "mape", "n_test", "feature_importance", "actual_vs_pred", "residuals")},
        "baseline": {k: lr_metrics[k] for k in ("mae", "mse", "rmse", "r2", "mape", "n_test")},
        "selected": name,
        "feature_availability": (
            "Occupancy features use current bookings and historical rates from OTHER flights "
            "on the same route (exclude_flight_id). Actual boarded count is never used as an input."
        ),
    })
    import json
    meta = {}
    if os.path.exists(META_PATH):
        with open(META_PATH, encoding="utf-8") as f:
            meta = json.load(f)
    meta["occupancy"] = {
        "model_name": name,
        "model_version": MODEL_VERSIONS["occupancy"],
        "training_date": utc_now_iso(),
        "dataset_size": int(len(df)),
        "features": OCCUPANCY_FEATURES,
        "metrics": {k: metrics[k] for k in ("mae", "rmse", "r2", "mape")},
    }
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"\nSaved {MODEL_PATH} and {EVAL_PATH}")


if __name__ == "__main__":
    main()
