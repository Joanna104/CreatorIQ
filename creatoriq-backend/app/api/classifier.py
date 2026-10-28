
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.classifier_service import (
    classify_content,
    check_skincare_relevance,
)

router = APIRouter(prefix="/classifier", tags=["Classifier"])


class ContentRequest(BaseModel):
    text: str


@router.post("/predict")
def predict_content(request: ContentRequest):
    try:
        return {
            "content_classification": classify_content(request.text),
            "skincare_relevance": check_skincare_relevance(request.text),
        }
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Classification failed: {exc}")
