
"""Request and response schemas for creator profiles."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CreatorProfileCreate(BaseModel):
    """Fields required to create a creator profile."""

    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    platform: Literal["YouTube", "Instagram", "TikTok", "Other"]
    experience_level: Literal["Beginner", "Intermediate", "Advanced"]


class CreatorProfileRead(BaseModel):
    """Public representation of a creator profile."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    platform: str
    experience_level: str
    created_at: datetime
