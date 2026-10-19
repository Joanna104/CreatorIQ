"""Migration tests.

* The first group needs no database and always runs.
* The ``integration`` group needs a real PostgreSQL: set TEST_DATABASE_URL (shell or .env) to
  a DISPOSABLE database whose name ends in "_test". Those tests create and drop the
  app/ds/synthetic schemas in it. Without the variable they are skipped.
"""

import io

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from app.core.config import Settings, get_settings
from app.db.schemas import ALL_SCHEMAS
from app.main import create_app
from tests.conftest import PROJECT_ROOT, get_test_database_url


def _alembic_config() -> Config:
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.attributes["configure_logger"] = False  # keep pytest's log capture intact
    return cfg


# --------------------------------------------------------------------------- no database needed


def test_single_linear_history_with_one_head():
    script = ScriptDirectory.from_config(_alembic_config())
    assert script.get_heads() == ["0001"]
    assert script.get_base() == "0001"


def test_offline_sql_creates_the_three_schemas_and_documents_the_rule(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:x@localhost/db")
    cfg = _alembic_config()
    cfg.output_buffer = io.StringIO()
    command.upgrade(cfg, "head", sql=True)  # generates SQL; never connects
    sql = cfg.output_buffer.getvalue()
    for schema in ALL_SCHEMAS:
        assert f'CREATE SCHEMA IF NOT EXISTS "{schema}"' in sql
    assert "CREATE TABLE" not in sql.replace("CREATE TABLE alembic_version", "")
    assert "SYNTHETIC DATA ONLY" in sql
    assert "never be used for model training" in sql


# --------------------------------------------------------------------- real PostgreSQL (opt-in)


def _schemas_present(engine) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = ANY(:n)"),
            {"n": list(ALL_SCHEMAS)},
        )
        return {row[0] for row in rows}


def _schema_comment(engine, schema: str) -> str:
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT obj_description(oid, 'pg_namespace') FROM pg_namespace WHERE nspname = :n"
            ),
            {"n": schema},
        ).scalar_one()


def _wipe(engine) -> None:
    with engine.begin() as conn:
        for schema in ALL_SCHEMAS:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        conn.execute(text("DROP TABLE IF EXISTS public.alembic_version"))


@pytest.fixture
def pg(monkeypatch):
    raw = get_test_database_url()
    if not raw:
        pytest.skip("TEST_DATABASE_URL is not set (see README: 'Running the tests').")
    url = make_url(raw).set(drivername="postgresql+psycopg")
    if not (url.database or "").endswith("_test"):
        pytest.fail(
            "TEST_DATABASE_URL must point to a disposable database whose name ends in '_test'."
        )
    monkeypatch.setenv("DATABASE_URL", url.render_as_string(hide_password=False))
    get_settings.cache_clear()
    engine = create_engine(url)
    _wipe(engine)
    yield engine, url
    _wipe(engine)
    engine.dispose()


@pytest.mark.integration
def test_upgrade_creates_three_empty_schemas(pg):
    engine, _ = pg
    assert _schemas_present(engine) == set()
    command.upgrade(_alembic_config(), "head")
    assert _schemas_present(engine) == set(ALL_SCHEMAS)
    with engine.connect() as conn:
        tables = conn.execute(
            text("SELECT count(*) FROM information_schema.tables WHERE table_schema = ANY(:n)"),
            {"n": list(ALL_SCHEMAS)},
        ).scalar_one()
    assert tables == 0


@pytest.mark.integration
def test_schema_comments_record_the_synthetic_data_rule(pg):
    engine, _ = pg
    command.upgrade(_alembic_config(), "head")
    synthetic = _schema_comment(engine, "synthetic")
    assert "SYNTHETIC DATA ONLY" in synthetic and "never be used for model training" in synthetic
    assert "REAL observational datasets only" in _schema_comment(engine, "ds")
    assert _schema_comment(engine, "app").startswith("CreatorIQ application data")


@pytest.mark.integration
def test_upgrade_is_idempotent(pg):
    engine, _ = pg
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    command.upgrade(cfg, "head")  # already at head: no error, no change
    assert _schemas_present(engine) == set(ALL_SCHEMAS)


@pytest.mark.integration
def test_downgrade_removes_schemas_and_upgrade_restores_them(pg):
    engine, _ = pg
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    assert _schemas_present(engine) == set()
    command.upgrade(cfg, "head")
    assert _schemas_present(engine) == set(ALL_SCHEMAS)


@pytest.mark.integration
def test_downgrade_refuses_to_destroy_a_schema_that_has_data(pg):
    engine, _ = pg
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE ds.precious (id integer)"))
    with pytest.raises(DBAPIError):
        command.downgrade(cfg, "base")
    # failure is atomic: nothing was dropped, and the table is intact
    assert _schemas_present(engine) == set(ALL_SCHEMAS)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM ds.precious")).scalar_one() == 0


@pytest.mark.integration
def test_models_and_database_are_in_sync(pg):
    command.upgrade(_alembic_config(), "head")
    command.check(_alembic_config())  # raises if autogenerate would produce changes


@pytest.mark.integration
def test_health_db_reports_up_against_real_postgresql(pg):
    _, url = pg
    app_settings = Settings(_env_file=None, database_url=url.render_as_string(hide_password=False))
    with TestClient(create_app(app_settings)) as client:
        response = client.get("/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}


@pytest.mark.integration
def test_health_db_reports_503_when_real_postgresql_rejects_the_login(pg):
    _, url = pg
    wrong = url.set(password="definitely-wrong-password")
    app_settings = Settings(
        _env_file=None, database_url=wrong.render_as_string(hide_password=False)
    )
    with TestClient(create_app(app_settings), raise_server_exceptions=False) as client:
        response = client.get("/health/db")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    assert "definitely-wrong-password" not in response.text
