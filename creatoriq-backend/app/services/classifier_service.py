
from pathlib import Path
import joblib

MODEL_DIR = Path(__file__).resolve().parent.parents[1] / "models" / "classifiers"

_content_model = None
_skincare_model = None


def load_model(filename):
    path = MODEL_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Model file not found: {path}")
    return joblib.load(path)


def classify_content(text):
    global _content_model

    if not text or not text.strip():
        raise ValueError("Text cannot be empty.")

    if _content_model is None:
        _content_model = load_model("creatoriq_content_classifier.joblib")

    prediction = _content_model.predict([text])[0]
    result = {"predicted_class": str(prediction)}

    if hasattr(_content_model, "predict_proba"):
        probabilities = _content_model.predict_proba([text])[0]
        result["confidence"] = round(float(max(probabilities)), 4)

    return result


def check_skincare_relevance(text):
    global _skincare_model

    if not text or not text.strip():
        raise ValueError("Text cannot be empty.")

    if _skincare_model is None:
        _skincare_model = load_model("creatoriq_skincare_relevance.joblib")

    prediction = _skincare_model.predict([text])[0]
    result = {"prediction": str(prediction)}

    if hasattr(_skincare_model, "predict_proba"):
        probabilities = _skincare_model.predict_proba([text])[0]
        result["confidence"] = round(float(max(probabilities)), 4)

    return result
