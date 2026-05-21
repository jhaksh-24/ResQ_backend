import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from app.ml.demand_model import DemandModel

def test_train_model():
    predictor = DemandModel()
    
    # Make enough rows so train_test_split has enough for stratify
    fake_data = pd.DataFrame({
        "latitude": [12.9] * 10,
        "longitude": [77.6] * 10,
        "hour_of_day": [10] * 10,
        "day_of_week": [1] * 10,
        "month": [5] * 10,
        "is_holiday": [0] * 10,
        "weather_condition": [1] * 10,
        "severity": [1] * 10,
        "ward_risk_weight": [0.5] * 10,
        "label": [1] * 10,
        "confidence_score": [1.0] * 10,
        "is_weekend": [0] * 10,
        "is_rush_hour": [1] * 10,
        "is_night": [0] * 10,
        "is_monsoon_season": [0] * 10,
        "is_heavy_rain": [0] * 10,
        "is_low_visibility": [0] * 10
    })
    
    with patch("pandas.read_csv", return_value=fake_data):
        with patch("builtins.open") as mock_open:
            with patch("pickle.dump") as mock_dump:
                predictor.train("fake_path.csv")
                predictor.save("fake_path.pkl")
                mock_dump.assert_called_once()

def test_predict_demand():
    predictor = DemandModel()
    # Mock load
    predictor.model = MagicMock()
    # predict_proba returns [N, classes] where classes=2
    predictor.model.predict_proba.return_value = np.array([[0.3, 0.7]])
    
    # Needs a dict matching FEATURE_COLS
    features = {"hour_sin": 1.0}
    prediction = predictor.predict(features)
    assert prediction == 0.7
    predictor.model.predict_proba.assert_called_once()

def test_predict_batch():
    predictor = DemandModel()
    predictor.model = MagicMock()
    predictor.model.predict_proba.return_value = np.array([[0.3, 0.7], [0.4, 0.6]])
    
    # Create fake DataFrame with required columns
    from app.ml.demand_model import FEATURE_COLS
    fake_df = pd.DataFrame([{col: 0 for col in FEATURE_COLS} for _ in range(2)])
    
    preds = predictor.predict_batch(fake_df)
    assert len(preds) == 2
    assert preds[0] == 0.7
