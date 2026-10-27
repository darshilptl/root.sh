"""Train LightGBM + Logistic Regression on train split, evaluate on heldout.

Per AGENTS.md Rule 3: Never train/tune/build features on heldout.
Per AGENTS.md Rule 12: Report only results from eval runs stored in the DB.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src/root.sh/ to path for imports (directory name has a dot)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import joblib
import lightgbm as lgbm
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from db.models import Run, SessionLocal, init_db
from features import extract_features
from intent import classify_intent

DATASET_PATH = Path("data/dataset/records.jsonl")
MODEL_PATH = Path("src/root.sh/model/model.pkl")
DB_PATH = Path("data/decisions.db")


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load train and heldout splits from records.jsonl."""
    rows = []
    with open(DATASET_PATH) as f:
        for line in f:
            rows.append(json.loads(line))

    df = pd.DataFrame(rows)

    train = df[df["split"] == "train"].copy()
    heldout = df[df["split"] == "heldout"].copy()

    print(f"Train: {len(train)} rows, {train['family_id'].nunique()} families")
    print(f"Heldout: {len(heldout)} rows, {heldout['family_id'].nunique()} families")
    print(f"Train label dist: {train['label'].value_counts().to_dict()}")
    print(f"Heldout label dist: {heldout['label'].value_counts().to_dict()}")

    return train, heldout


def extract_features_df(df: pd.DataFrame) -> pd.DataFrame:
    """Extract features and intent class for each row."""
    records = []
    for _, row in df.iterrows():
        user_request = row["user_request"]
        proposed_action = row["proposed_action"]
        source = row["source"]

        # Intent class from request (rule-based)
        intent_class = classify_intent(user_request)

        # Six features
        feats = extract_features(user_request, proposed_action, source, intent_class)

        record = {
            "id": row["id"],
            "family_id": row["family_id"],
            "label": 1 if row["label"] == "risky" else 0,
            **feats,
        }
        records.append(record)

    return pd.DataFrame(records)


def train_and_evaluate() -> dict:
    """Train models, evaluate on heldout, save results to SQLite."""
    # Load data
    train_df, heldout_df = load_data()

    # Extract features
    X_train = extract_features_df(train_df)
    X_heldout = extract_features_df(heldout_df)

    y_train = X_train["label"].values
    y_heldout = X_heldout["label"].values

    feature_cols = [
        "source_trusted", "intent_match", "target_in_request",
        "reversibility", "scope", "privilege",
    ]

    X_train_features = X_train[feature_cols].values
    X_heldout_features = X_heldout[feature_cols].values

    print(f"\nTraining features shape: {X_train_features.shape}")
    print(f"Heldout features shape: {X_heldout_features.shape}")

    # Train LightGBM
    print("\n=== Training LightGBM ===")
    lgbm_model = lgbm.LGBMClassifier(
        num_leaves=15,
        min_child_samples=10,
        learning_rate=0.05,
        n_estimators=100,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbose=-1,
    )
    lgbm_model.fit(X_train_features, y_train)

    lgbm_pred = lgbm_model.predict(X_heldout_features)
    lgbm_prob = lgbm_model.predict_proba(X_heldout_features)[:, 1]

    lgbm_metrics = {
        "model": "lightgbm",
        "accuracy": accuracy_score(y_heldout, lgbm_pred),
        "precision": precision_score(y_heldout, lgbm_pred),
        "recall": recall_score(y_heldout, lgbm_pred),
        "f1": f1_score(y_heldout, lgbm_pred),
        "auc_roc": roc_auc_score(y_heldout, lgbm_prob),
    }

    print(f"LightGBM results: {lgbm_metrics}")

    # Train Logistic Regression
    print("\n=== Training Logistic Regression ===")
    lr_model = LogisticRegression(
        random_state=42,
        max_iter=1000,
    )
    lr_model.fit(X_train_features, y_train)

    lr_pred = lr_model.predict(X_heldout_features)
    lr_prob = lr_model.predict_proba(X_heldout_features)[:, 1]

    lr_metrics = {
        "model": "logistic_regression",
        "accuracy": accuracy_score(y_heldout, lr_pred),
        "precision": precision_score(y_heldout, lr_pred),
        "recall": recall_score(y_heldout, lr_pred),
        "f1": f1_score(y_heldout, lr_pred),
        "auc_roc": roc_auc_score(y_heldout, lr_prob),
    }

    print(f"Logistic Regression results: {lr_metrics}")

    # Per-provenance breakdown for LightGBM
    print("\n=== Per-provenance breakdown (LightGBM) ===")
    provenance_results = {}
    for prov in ["seed", "generated", "nl2bash"]:
        prov_mask = heldout_df["provenance"] == prov
        if prov_mask.sum() == 0:
            continue
        prov_y = y_heldout[prov_mask.values]
        prov_prob = lgbm_prob[prov_mask.values]
        prov_pred = lgbm_pred[prov_mask.values]
        provenance_results[prov] = {
            "accuracy": accuracy_score(prov_y, prov_pred),
            "precision": precision_score(prov_y, prov_pred, zero_division=0),
            "recall": recall_score(prov_y, prov_pred, zero_division=0),
            "f1": f1_score(prov_y, prov_pred, zero_division=0),
            "n_rows": int(prov_mask.sum()),
        }
        print(f"  {prov}: {provenance_results[prov]}")

    # Per-pattern breakdown for LightGBM
    print("\n=== Per-pattern breakdown (LightGBM) ===")
    pattern_results = {}
    for pattern in ["env-poison", "param-escape", "file-injection",
                     "halluc-destructive", "agent-deviation",
                     "priv-escalation", "exfil-remote-exec"]:
        pat_mask = heldout_df["family_id"].str.startswith(pattern)
        if pat_mask.sum() == 0:
            continue
        pat_y = y_heldout[pat_mask.values]
        pat_prob = lgbm_prob[pat_mask.values]
        pat_pred = lgbm_pred[pat_mask.values]
        pattern_results[pattern] = {
            "accuracy": accuracy_score(pat_y, pat_pred),
            "precision": precision_score(pat_y, pat_pred, zero_division=0),
            "recall": recall_score(pat_y, pat_pred, zero_division=0),
            "f1": f1_score(pat_y, pat_pred, zero_division=0),
            "n_rows": int(pat_mask.sum()),
        }
        print(f"  {pattern}: {pattern_results[pattern]}")

    # Save model
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(lgbm_model, MODEL_PATH)
    print(f"\nModel saved to {MODEL_PATH}")

    # Save results to SQLite
    init_db()
    session = SessionLocal()

    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    # Save LightGBM run
    lgbm_run = Run(
        id=f"{run_id}_lightgbm",
        model_name="lightgbm",
        split="heldout",
        accuracy=lgbm_metrics["accuracy"],
        precision=lgbm_metrics["precision"],
        recall=lgbm_metrics["recall"],
        f1=lgbm_metrics["f1"],
        auc_roc=lgbm_metrics["auc_roc"],
    )
    session.add(lgbm_run)

    # Save Logistic Regression run
    lr_run = Run(
        id=f"{run_id}_logistic_regression",
        model_name="logistic_regression",
        split="heldout",
        accuracy=lr_metrics["accuracy"],
        precision=lr_metrics["precision"],
        recall=lr_metrics["recall"],
        f1=lr_metrics["f1"],
        auc_roc=lr_metrics["auc_roc"],
    )
    session.add(lr_run)

    session.commit()
    session.close()

    print(f"\nResults saved to SQLite (run_id: {run_id})")

    return {
        "lightgbm": lgbm_metrics,
        "logistic_regression": lr_metrics,
        "provenance": provenance_results,
        "pattern": pattern_results,
        "run_id": run_id,
    }


if __name__ == "__main__":
    results = train_and_evaluate()
    print("\n=== Phase 6 Complete ===")
    print(f"LightGBM F1: {results['lightgbm']['f1']:.4f}")
    print(f"Logistic Regression F1: {results['logistic_regression']['f1']:.4f}")
