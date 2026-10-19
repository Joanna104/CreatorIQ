"""FastAPI dependencies."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine
from sqlalchemy.orm import Session


def get_engine(request: Request) -> Engine:
    return request.app.state.engine


def get_session(request: Request) -> Iterator[Session]:
    """A database session per request (unused until a later phase adds data endpoints)."""
    with Session(request.app.state.engine, autoflush=False, expire_on_commit=False) as session:
        yield session
