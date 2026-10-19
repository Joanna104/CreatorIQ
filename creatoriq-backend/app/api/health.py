"""Liveness and database-connectivity endpoints."""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from app import __version__
from app.api.deps import get_engine
from app.core.errors import AppError, ErrorResponse
from app.db.session import check_database

logger = logging.getLogger(__name__)

SERVICE_NAME = "creatoriq-backend"

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


class DatabaseHealthResponse(BaseModel):
    status: Literal["ok"]
    database: Literal["up"]


@router.get("/health", response_model=HealthResponse, summary="Liveness (no database access)")
def health() -> HealthResponse:
    return HealthResponse(status="ok", service=SERVICE_NAME, version=__version__)


@router.get(
    "/health/db",
    response_model=DatabaseHealthResponse,
    responses={503: {"model": ErrorResponse, "description": "Database is not reachable"}},
    summary="Database connectivity",
)
def health_db(engine: Annotated[Engine, Depends(get_engine)]) -> DatabaseHealthResponse:
    try:
        check_database(engine)
    except SQLAlchemyError as exc:
        # Log only the error class; the response never contains connection details.
        logger.warning(
            "Database health check failed (%s)", type(getattr(exc, "orig", exc)).__name__
        )
        raise AppError(
            "Database is not reachable.", status_code=503, code="database_unavailable"
        ) from exc
    return DatabaseHealthResponse(status="ok", database="up")
