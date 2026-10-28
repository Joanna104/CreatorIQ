
"""Application factory.

Run with:  uvicorn app.main:create_app --factory
(There is deliberately no module-level ``app``, so importing this module has no side effects
and does not require configuration.)
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine

from app import __version__
from app.api.health import router as health_router
from app.api.creators import router as creators_router
from app.api.analysis import router as analysis_router
from app.api.auth import router as auth_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.request_id import RequestIDMiddleware
from app.db.session import build_engine
from app.api.ideas import router as ideas_router
from app.api.classifier import router as classifier_router
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    app.state.engine.dispose()


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
) -> FastAPI:
    """Build the app. Settings and engine can be injected for tests."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="CreatorIQ API",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine or build_engine(settings)
    app.include_router(ideas_router)
    app.include_router(classifier_router)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5500",
            "http://127.0.0.1:5500",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(creators_router)
    app.include_router(analysis_router)
    app.include_router(auth_router)
    return app
