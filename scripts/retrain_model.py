"""
ResQ — Demand Model Retraining Pipeline
=========================================
Reads newly reported incidents (confidence_score > 0) from the DB,
extracts features, appends to the base training dataset, and retrains
the LightGBM demand model.

Run this periodically via cron (e.g., daily at 2 AM) to organically
upgrade the model as real data arrives.

Run:
    python scripts/retrain_model.py
"""

import sys
import os
import logging
import pandas as pd
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.db.models import Incident
from app.ml.demand_model import DemandModel, FEATURE_COLS, _get_data_dir
from app.core.logger import get_logger, log_event

logger = get_logger(__name__)

def extract_features(db_incidents) -> pd.DataFrame:
    """Convert SQLAlchemy models to pandas DataFrame with extracted features."""
    records = []
    for inc in db_incidents:
        dt = inc.timestamp
        hour = dt.hour
        dow = dt.weekday()
        month = dt.month
        year = dt.year
        
        is_monsoon = int(month in [6, 7, 8, 9])
        is_rush = int(hour in [7, 8, 9, 17, 18, 19, 20])
        is_night = int(hour in [22, 23, 0, 1, 2, 3])
        is_weekend = int(dow >= 5)

        # In a real system, weather & traffic would be fetched from a historical API.
        # For now, we use synthetic defaults if real data is missing.
        records.append({
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
            "temperature_c": 26.0,  # Mock weather
            "rainfall_mm_hr": 0.0,
            "humidity_pct": 55.0,
            "visibility_km": 8.0,
            "is_heavy_rain": 0,
            "is_low_visibility": 0,
            "traffic_congestion_idx": 0.3, # Mock traffic
            "ward_risk_weight": 2.0,       # Default risk
            "year": year,
            "severity": inc.severity,
            "label": 1,
            "confidence_score": float(inc.confidence_score),
        })
    return pd.DataFrame(records)

def retrain_pipeline():
    db = SessionLocal()
    try:
        log_event(logger, logging.INFO, "Starting demand model retrain pipeline")
        
        # 1. Fetch real incidents (confidence_score > 0)
        real_incidents = db.query(Incident).filter(Incident.confidence_score > 0.0).all()
        log_event(logger, logging.INFO, "Fetched real incidents", count=len(real_incidents))
        
        if not real_incidents:
            log_event(logger, logging.INFO, "No real incidents found to retrain on. Exiting.")
            return

        # 2. Extract features
        new_df = extract_features(real_incidents)
        
        # 3. Load base synthetic dataset
        csv_path = os.path.join(_get_data_dir(), "bengaluru_incidents_features.csv")
        base_df = pd.read_csv(csv_path)
        
        # Ensure base bool cols are ints
        bool_cols = ["is_weekend", "is_rush_hour", "is_night", "is_monsoon_season",
                      "is_heavy_rain", "is_low_visibility"]
        for col in bool_cols:
            base_df[col] = base_df[col].astype(int)
            
        # 4. Combine data
        combined_df = pd.concat([base_df, new_df], ignore_index=True)
        
        # We save this combined dataset temporarily so the DemandModel can train on it
        temp_csv = os.path.join(_get_data_dir(), "temp_combined_features.csv")
        combined_df.to_csv(temp_csv, index=False)
        
        # 5. Retrain model
        log_event(logger, logging.INFO, "Retraining LightGBM model", total_samples=len(combined_df))
        model = DemandModel()
        metrics = model.train(csv_path=temp_csv)
        model.save()
        
        # Cleanup temp file
        os.remove(temp_csv)
        
        log_event(logger, logging.INFO, "Retraining complete", metrics=metrics)
        print("\nSUCCESS: Retraining complete!")
        print(f"Metrics: {metrics}")
        
    except Exception as e:
        log_event(logger, logging.ERROR, "Retraining pipeline failed", error=str(e))
        raise
    finally:
        db.close()

if __name__ == "__main__":
    retrain_pipeline()
