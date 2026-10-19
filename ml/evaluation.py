"""Helpers to persist real evaluation metrics (never hand-written)."""

import json
import os
from datetime import datetime

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_recall_curve,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)


def _json_safe(obj):
    if isinstance(obj, (np.floating, np.float32, np.float64)):
        return float(obj)
    if isinstance(obj, (np.integer, np.int32, np.int64)):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(x) for x in obj]
    return obj


def write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = dict(payload)
    payload["evaluated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_json_safe(payload), f, indent=2)
    return path


def classification_metrics(y_true, y_pred, y_proba=None, feature_importance=None):
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    out = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "true_positives": int(tp),
        "true_negatives": int(tn),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "confusion_matrix": cm.tolist(),
        "n_test": int(len(y_true)),
    }
    if y_proba is not None:
        out["roc_auc"] = float(roc_auc_score(y_true, y_proba))
        out["pr_auc"] = float(average_precision_score(y_true, y_proba))
        fpr, tpr, _ = roc_curve(y_true, y_proba)
        prec, rec, _ = precision_recall_curve(y_true, y_proba)
        # downsample for UI
        out["roc_curve"] = {"fpr": fpr[:: max(1, len(fpr)//100)].tolist(), "tpr": tpr[:: max(1, len(tpr)//100)].tolist()}
        out["pr_curve"] = {"precision": prec[:: max(1, len(prec)//100)].tolist(), "recall": rec[:: max(1, len(rec)//100)].tolist()}
    if feature_importance is not None:
        out["feature_importance"] = feature_importance
    return out


def regression_metrics(y_true, y_pred, feature_importance=None):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mae = float(mean_absolute_error(y_true, y_pred))
    mse = float(mean_squared_error(y_true, y_pred))
    rmse = float(np.sqrt(mse))
    r2 = float(r2_score(y_true, y_pred))
    mask = np.abs(y_true) > 1e-6
    mape = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100) if mask.any() else None
    sample_n = min(250, len(y_true))
    idx = np.linspace(0, len(y_true) - 1, sample_n).astype(int)
    out = {
        "mae": mae,
        "mse": mse,
        "rmse": rmse,
        "r2": r2,
        "mape": mape,
        "n_test": int(len(y_true)),
        "actual_vs_pred": {"actual": y_true[idx].tolist(), "predicted": y_pred[idx].tolist()},
        "residuals": (y_true[idx] - y_pred[idx]).tolist(),
    }
    if feature_importance is not None:
        out["feature_importance"] = feature_importance
    return out
