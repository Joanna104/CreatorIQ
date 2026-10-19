"""Shared fixtures. Tests are hermetic: they never read a developer's real .env or shell
configuration, and only the explicitly opt-in integration tests ever touch PostgreSQL."""

import os
from pathlib import Path

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.core.config import Settings, get_settings
from app.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_ENV_PREFIXES = ("POSTGRES_", "DATABASE_URL", "APP_ENV", "LOG_LEVEL", "DB_")


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch, tmp_path):
    """No config env vars, no .env file (cwd is an empty temp dir), fresh settings cache."""
    for key in list(os.environ):
        if key.upper().startswith(_CONFIG_ENV_PREFIXES):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def get_test_database_url() -> str | None:
    """TEST_DATABASE_URL from the shell, or from the project's .env file."""
    value = os.environ.get("TEST_DATABASE_URL") or dotenv_values(PROJECT_ROOT / ".env").get(
        "TEST_DATABASE_URL"
    )
    return value or None


@pytest.fixture
def settings() -> Settings:
    # Obviously fake values; nothing here can connect anywhere real.
    return Settings(
        _env_file=None,
        postgres_user="unit_test_user",
        postgres_password="not-a-real-password",
        postgres_db="unit_test_db",
        postgres_host="127.0.0.1",
        postgres_port=5432,
    )


@pytest.fixture
def unreachable_settings(settings: Settings) -> Settings:
    """Points at 127.0.0.1:1, where nothing listens, so connections fail immediately."""
    return settings.model_copy(update={"postgres_port": 1, "db_connect_timeout": 1})


@pytest.fixture
def sqlite_engine():
    """In-memory SQLite, used only as a stand-in that answers ``SELECT 1``."""
    engine = create_engine("sqlite://")
    yield engine
    engine.dispose()


@pytest.fixture
def make_client():
    """Build a TestClient around create_app(); unhandled errors become 500 responses."""

    def _make(app_settings: Settings, engine=None, extra_routes=None) -> TestClient:
        app = create_app(app_settings, engine=engine)
        if extra_routes is not None:
            extra_routes(app)
        return TestClient(app, raise_server_exceptions=False)

    return _make
