
"""Request and response schemas for content analysis."""

from typing import Literal

from pydantic import BaseModel, Field


class ContentAnalysisRequest(BaseModel):
    idea: str = Field(min_length=10, max_length=1000)
    platform: Literal["YouTube", "Instagram", "TikTok"]
    content_format: Literal["Short video", "Long video", "Carousel", "Image post"]
    target_audience: str = Field(min_length=2, max_length=200)


class ContentAnalysisResponse(BaseModel):
    idea: str
    platform: str
    content_format: str
    target_audience: str
    hook_suggestion: str
    structure: list[str]
    estimated_production_minutes: int
    estimate_note: str
    analysis_type: str
