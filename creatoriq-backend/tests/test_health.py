import re
from unittest import mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app import __version__
from app.main import create_app

# Anything that would reveal how we connect must never reach a client.
LEAKABLE = ["127.0.0.1", "not-a-real-password", "unit_test_user", "unit_test_db", "psycopg"]


def test_health_ok(make_client, settings):
    response = make_client(settings).get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "creatoriq-backend",
        "version": __version__,
    }


def test_health_does_not_touch_the_database(make_client, unreachable_settings):
    # Liveness must stay green even when the database is down.
    assert make_client(unreachable_settings).get("/health").status_code == 200


def test_health_db_up(make_client, settings, sqlite_engine):
    # SQLite stands in for PostgreSQL here: this checks the endpoint's success path only.
    # The real PostgreSQL check is in test_migrations.py (integration, opt-in).
    response = make_client(settings, engine=sqlite_engine).get("/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}


def test_health_db_returns_503_when_database_is_unreachable(make_client, unreachable_settings):
    response = make_client(unreachable_settings).get("/health/db")
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "database_unavailable"
    assert error["message"] == "Database is not reachable."
    assert error["request_id"] == response.headers["X-Request-ID"]
    for secret in LEAKABLE:
        assert secret not in response.text


def test_health_db_503_for_any_sqlalchemy_error(make_client, settings, sqlite_engine):
    failing = OperationalError("SELECT 1", {}, Exception("connection lost to 10.0.0.5"))
    with mock.patch("app.api.health.check_database", side_effect=failing):
        response = make_client(settings, engine=sqlite_engine).get("/health/db")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    assert "10.0.0.5" not in response.text


def test_health_db_unexpected_errors_are_500_not_503(make_client, settings, sqlite_engine):
    with mock.patch("app.api.health.check_database", side_effect=ValueError("bug")):
        response = make_client(settings, engine=sqlite_engine).get("/health/db")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"


def test_every_response_has_a_request_id(make_client, settings):
    response = make_client(settings).get("/health")
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["X-Request-ID"])


def test_valid_client_request_id_is_echoed(make_client, settings):
    response = make_client(settings).get("/health", headers={"X-Request-ID": "client-id-12345"})
    assert response.headers["X-Request-ID"] == "client-id-12345"


@pytest.mark.parametrize("bad", ["short", "has spaces in it!!", "x" * 65, "line\tbreak-12345"])
def test_unsafe_client_request_id_is_replaced(make_client, settings, bad):
    response = make_client(settings).get("/health", headers={"X-Request-ID": bad})
    assert response.headers["X-Request-ID"] != bad
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["X-Request-ID"])


def test_engine_is_disposed_on_shutdown(settings, sqlite_engine):
    app = create_app(settings, engine=sqlite_engine)
    with mock.patch.object(sqlite_engine, "dispose") as dispose:
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
            dispose.assert_not_called()
        dispose.assert_called_once()


def test_create_app_reads_settings_from_the_environment(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "not-a-real-password")
    monkeypatch.setenv("POSTGRES_DB", "d")
    app = create_app()  # no arguments: exactly how `uvicorn --factory` calls it
    assert TestClient(app).get("/health").status_code == 200


def test_create_app_fails_fast_without_database_configuration():
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="Database is not configured"):
        create_app()
