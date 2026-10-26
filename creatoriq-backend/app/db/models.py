
"""SQLAlchemy models for CreatorIQ application data."""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.schemas import APP_SCHEMA


class CreatorProfile(Base):
    """A creator's basic profile."""

    __tablename__ = "creator_profiles"
    __table_args__ = {"schema": APP_SCHEMA}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    experience_level: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

class UserAccount(Base):
    """A user's authentication account."""

    __tablename__ = "user_accounts"
    __table_args__ = {"schema": APP_SCHEMA}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
