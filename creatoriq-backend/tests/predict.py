from pathlib import Path
import joblib
import numpy as np
import pandas as pd

MODEL_PATH = Path(__file__).resolve().parent / (
    "creatoriq_model_v2_corrected.pkl"
)

_artifact = joblib.load(MODEL_PATH)
_model = _artifact["model"]
_FEATURES = _artifact["features"]

def predict_views(input_data):
    """Return an experimental day-7 views point estimate."""

    if isinstance(input_data, dict):
        X = pd.DataFrame([input_data])
    elif isinstance(input_data, pd.DataFrame):
        X = input_data.copy()
    else:
        raise TypeError("Provide a dictionary or DataFrame")

    missing = set(_FEATURES) - set(X.columns)
    if missing:
        raise ValueError(
            f"Missing features: {sorted(missing)}"
        )

    X = X[_FEATURES].copy()

    pred_log = _model.predict(X)
    pred_views = np.expm1(
        np.clip(pred_log, 0, 30)
    )

    return pred_views
