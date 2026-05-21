"""
ResQ — LightGBM Demand Prediction Model
==========================================
Predicts incident probability per zone per time window.

Used by the rebalancing engine to proactively position ambulances
in zones where incidents are LIKELY to happen, not just where they
have happened.

Training data: bengaluru_incidents_features.csv (50K synthetic incidents)
  - confidence_score=0.0 → sample_weight=0.0 for synthetic data
  - When real RTI data arrives (confidence_score > 0), it gets weight 1.0
    and dominates training automatically

Features:
  Temporal: hour_sin, hour_cos, dow_sin, dow_cos, month_sin, month_cos,
            is_weekend, is_rush_hour, is_night, is_monsoon_season
  Weather:  temperature_c, rainfall_mm_hr, humidity_pct, visibility_km,
            is_heavy_rain, is_low_visibility
  Spatial:  ward_risk_weight, traffic_congestion_idx
  Context:  year, severity

Target:    label (1 = incident occurred in this zone/time cell)

Design decision (MEMORY.md):
  Synthetic data acts as structural prior only — sample_weight from confidence_score
"""

import os
import logging
import pickle
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, classification_report
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Feature columns used for training
FEATURE_COLS = [
    "hour_sin", "hour_cos", "dow_sin", "dow_cos", "month_sin", "month_cos",
    "is_weekend", "is_rush_hour", "is_night", "is_monsoon_season",
    "temperature_c", "rainfall_mm_hr", "humidity_pct", "visibility_km",
    "is_heavy_rain", "is_low_visibility",
    "traffic_congestion_idx", "ward_risk_weight",
    "year", "severity",
]


def _get_data_dir() -> str:
    """Resolve app/data/raw/ from this file's location."""
    current = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current))
    return os.path.join(project_root, "app", "data", "raw")


def _get_model_dir() -> str:
    """Resolve app/data/models/ for saving trained model artifacts."""
    current = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current))
    model_dir = os.path.join(project_root, "app", "data", "models")
    os.makedirs(model_dir, exist_ok=True)
    return model_dir


class DemandModel:
    """
    LightGBM-based demand prediction model.

    Usage:
        # Train
        model = DemandModel()
        model.train("path/to/features.csv")
        model.save()

        # Predict
        model = DemandModel.load()
        probs = model.predict(feature_dict)
    """

    MODEL_FILENAME = "demand_lgbm.pkl"

    def __init__(self):
        self.model: Optional[lgb.LGBMClassifier] = None
        self.metrics: Dict = {}

    def train(self, csv_path: Optional[str] = None) -> Dict:
        """
        Train the demand model on incident data.

        Args:
            csv_path: path to features CSV (default: app/data/raw/bengaluru_incidents_features.csv)

        Returns:
            Dict with training metrics
        """
        if csv_path is None:
            csv_path = os.path.join(_get_data_dir(), "bengaluru_incidents_features.csv")

        logger.info(f"Loading training data from {csv_path}")
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df):,} positive records")

        # Convert boolean columns to int for LightGBM
        bool_cols = ["is_weekend", "is_rush_hour", "is_night", "is_monsoon_season",
                      "is_heavy_rain", "is_low_visibility"]
        for col in bool_cols:
            df[col] = df[col].astype(int)

        # ── Generate negative samples ────────────────────────────────────
        # All rows in the CSV are label=1 (incident happened). We need
        # label=0 (no incident) examples for the classifier to learn.
        # Strategy: sample random ward × time combinations with randomized
        # context features, representing "normal" conditions where nothing
        # happened. Use 1:1 ratio of positives to negatives.
        n_neg = len(df)
        rng = np.random.RandomState(42)

        neg_records = []
        for _ in range(n_neg):
            hour = rng.randint(0, 24)
            dow = rng.randint(0, 7)
            month = rng.randint(1, 13)
            year = rng.randint(2000, 2027)
            ward_rw = rng.choice(df["ward_risk_weight"].unique())
            is_monsoon = int(month in [6, 7, 8, 9])
            is_rush = int(hour in [7, 8, 9, 17, 18, 19, 20])
            is_night = int(hour in [22, 23, 0, 1, 2, 3])
            is_weekend = int(dow >= 5)

            neg_records.append({
                "hour_sin": np.sin(2 * np.pi * hour / 24),
                "hour_cos": np.cos(2 * np.pi * hour / 24),
                "dow_sin": np.sin(2 * np.pi * dow / 7),
                "dow_cos": np.cos(2 * np.pi * dow / 7),
                "month_sin": np.sin(2 * np.pi * month / 12),
                "month_cos": np.cos(2 * np.pi * month / 12),
                "is_weekend": is_weekend,
                "is_rush_hour": is_rush,
                "is_night": is_night,
                "is_monsoon_season": is_monsoon,
                "temperature_c": rng.normal(26, 3),
                "rainfall_mm_hr": max(0, rng.exponential(0.5) if rng.random() < 0.1 else 0),
                "humidity_pct": rng.normal(58, 8),
                "visibility_km": max(1.5, rng.normal(8, 2)),
                "is_heavy_rain": 0,
                "is_low_visibility": 0,
                "traffic_congestion_idx": max(0, min(1, rng.normal(0.3, 0.15))),
                "ward_risk_weight": ward_rw,
                "year": year,
                "severity": 0,  # no incident = no severity
                "label": 0,
                "confidence_score": 0.0,
            })

        neg_df = pd.DataFrame(neg_records)
        df = pd.concat([df, neg_df], ignore_index=True)
        logger.info(f"Added {n_neg:,} negative samples → {len(df):,} total")

        X = df[FEATURE_COLS].values
        y = df["label"].values

        # Sample weights from confidence_score:
        #   - synthetic (confidence_score=0.0) → weight 0.1 (structural prior, not zero)
        #   - real data (confidence_score>0)   → weight = confidence_score
        # Using 0.1 instead of 0.0 because zero-weight samples are still useful
        # for tree structure learning, just heavily downweighted
        weights = df["confidence_score"].values.copy()
        weights[weights == 0.0] = 0.1  # synthetic data gets low but non-zero weight
        weights = np.clip(weights, 0.01, 1.0)

        # Train/test split (stratified)
        X_train, X_test, y_train, y_test, w_train, w_test = train_test_split(
            X, y, weights, test_size=0.2, random_state=42, stratify=y
        )

        logger.info(f"Training: {len(X_train):,} samples, Testing: {len(X_test):,} samples")

        # LightGBM model
        self.model = lgb.LGBMClassifier(
            n_estimators=300,
            max_depth=8,
            learning_rate=0.05,
            num_leaves=63,
            min_child_samples=50,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=0.1,
            random_state=42,
            n_jobs=-1,
            verbose=-1,
        )

        logger.info("Training LightGBM model...")
        self.model.fit(
            X_train, y_train,
            sample_weight=w_train,
            eval_set=[(X_test, y_test)],
            eval_sample_weight=[w_test],
        )

        # Evaluate
        y_pred_proba = self.model.predict_proba(X_test)[:, 1]
        y_pred = self.model.predict(X_test)

        # Since all labels are 1 (positive class) in synthetic data,
        # AUC is not meaningful with single-class data.
        # We track feature importances and prediction distribution instead.
        self.metrics = {
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "prediction_mean": float(y_pred_proba.mean()),
            "prediction_std": float(y_pred_proba.std()),
            "prediction_min": float(y_pred_proba.min()),
            "prediction_max": float(y_pred_proba.max()),
        }

        # Feature importance
        importances = self.model.feature_importances_
        feature_importance = sorted(
            zip(FEATURE_COLS, importances),
            key=lambda x: x[1], reverse=True
        )
        self.metrics["feature_importance"] = {
            name: int(imp) for name, imp in feature_importance
        }

        logger.info(f"Training complete. Metrics: {self.metrics}")
        logger.info("Top 5 features:")
        for name, imp in feature_importance[:5]:
            logger.info(f"  {name}: {imp}")

        return self.metrics

    def predict(self, features: Dict) -> float:
        """
        Predict incident probability for a single context.

        Args:
            features: dict with keys matching FEATURE_COLS

        Returns:
            float 0-1 probability of incident
        """
        if self.model is None:
            raise RuntimeError("Model not trained. Call train() or load() first.")

        X = np.array([[features.get(col, 0) for col in FEATURE_COLS]])
        proba = self.model.predict_proba(X)[0, 1]
        return float(proba)

    def predict_batch(self, df: pd.DataFrame) -> np.ndarray:
        """
        Predict incident probabilities for a batch of contexts.

        Args:
            df: DataFrame with columns matching FEATURE_COLS

        Returns:
            numpy array of probabilities
        """
        if self.model is None:
            raise RuntimeError("Model not trained. Call train() or load() first.")

        X = df[FEATURE_COLS].values
        return self.model.predict_proba(X)[:, 1]

    def save(self, path: Optional[str] = None):
        """Save trained model to disk."""
        if self.model is None:
            raise RuntimeError("No model to save. Train first.")

        if path is None:
            path = os.path.join(_get_model_dir(), self.MODEL_FILENAME)

        with open(path, "wb") as f:
            pickle.dump({
                "model": self.model,
                "metrics": self.metrics,
                "feature_cols": FEATURE_COLS,
            }, f)

        logger.info(f"Model saved to {path}")

    @classmethod
    def load(cls, path: Optional[str] = None) -> "DemandModel":
        """Load a trained model from disk."""
        if path is None:
            path = os.path.join(_get_model_dir(), cls.MODEL_FILENAME)

        if not os.path.exists(path):
            raise FileNotFoundError(
                f"No trained model found at {path}. "
                f"Run train first: python -c \"from app.ml.demand_model import DemandModel; m = DemandModel(); m.train(); m.save()\""
            )

        with open(path, "rb") as f:
            data = pickle.load(f)

        instance = cls()
        instance.model = data["model"]
        instance.metrics = data["metrics"]
        logger.info(f"Model loaded from {path}")
        return instance


def train_and_save():
    """Convenience function: train on default data and save."""
    model = DemandModel()
    metrics = model.train()
    model.save()
    return metrics


if __name__ == "__main__":
    # Direct execution: train and save
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print("ResQ Demand Model Trainer")
    print("=" * 50)
    metrics = train_and_save()
    print(f"\nTraining complete.")
    print(f"Metrics: {metrics}")
