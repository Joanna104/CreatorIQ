import pytest
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.core.config import Settings, get_settings

FAKE_PASSWORD = "not-a-real-password"


def _settings(**overrides) -> Settings:
    base = {
        "postgres_user": "u",
        "postgres_password": FAKE_PASSWORD,
        "postgres_db": "d",
    }
    return Settings(_env_file=None, **{**base, **overrides})


def test_defaults():
    s = _settings()
    assert s.app_env == "development"
    assert s.log_level == "INFO"
    assert s.postgres_host == "localhost"
    assert s.postgres_port == 5432
    assert s.db_connect_timeout == 3
    assert s.db_echo is False


def test_builds_url_from_postgres_parts():
    url = _settings(postgres_host="db.internal", postgres_port=6543).sqlalchemy_url
    assert url.drivername == "postgresql+psycopg"
    assert (url.username, url.host, url.port, url.database) == ("u", "db.internal", 6543, "d")
    assert url.password == FAKE_PASSWORD


def test_password_with_special_characters_round_trips():
    tricky = "p@ss/w:rd#?%&=+ "
    url = _settings(postgres_password=tricky).sqlalchemy_url
    rendered = url.render_as_string(hide_password=False)
    assert make_url(rendered).password == tricky


@pytest.mark.parametrize("missing", ["postgres_user", "postgres_password", "postgres_db"])
def test_missing_database_settings_fail_fast(missing):
    with pytest.raises(ValidationError) as exc_info:
        _settings(**{missing: None})
    assert missing.upper() in str(exc_info.value)


def test_empty_password_is_treated_as_missing():
    with pytest.raises(ValidationError) as exc_info:
        _settings(postgres_password="")
    assert "POSTGRES_PASSWORD" in str(exc_info.value)


def test_database_url_overrides_postgres_parts():
    s = Settings(_env_file=None, database_url="postgresql+psycopg://a:b@h:1234/x")
    url = s.sqlalchemy_url
    assert (url.username, url.password, url.host, url.port, url.database) == (
        "a",
        "b",
        "h",
        1234,
        "x",
    )


def test_database_url_alone_is_enough():
    # No POSTGRES_* values needed when DATABASE_URL is set.
    assert Settings(_env_file=None, database_url="postgresql://a:b@h/x").sqlalchemy_url.host == "h"


def test_plain_postgresql_scheme_is_normalised_to_psycopg3():
    s = Settings(_env_file=None, database_url="postgresql://a:b@h/x")
    assert s.sqlalchemy_url.drivername == "postgresql+psycopg"


@pytest.mark.parametrize(
    "bad_url",
    [
        "mysql://a:SECRETVALUE@h/x",
        "postgresql+psycopg2://a:SECRETVALUE@h/x",
        "not a url SECRETVALUE",
    ],
)
def test_invalid_database_url_is_rejected_without_echoing_it(bad_url):
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, database_url=bad_url)
    assert "SECRETVALUE" not in str(exc_info.value)


def test_secrets_do_not_appear_in_repr_or_str():
    s = _settings(database_url=f"postgresql://a:{FAKE_PASSWORD}@h/x")
    assert FAKE_PASSWORD not in repr(s)
    assert FAKE_PASSWORD not in str(s)
    assert FAKE_PASSWORD not in repr(_settings())


def test_validation_errors_never_contain_the_password():
    with pytest.raises(ValidationError) as exc_info:
        _settings(postgres_user=None)  # password is set, user is missing
    assert FAKE_PASSWORD not in str(exc_info.value)


def test_invalid_app_env_is_rejected():
    with pytest.raises(ValidationError):
        _settings(app_env="staging")


def test_log_level_is_case_insensitive():
    assert _settings(log_level="debug").log_level == "DEBUG"


@pytest.mark.parametrize("port", [0, 70000])
def test_port_range_is_validated(port):
    with pytest.raises(ValidationError):
        _settings(postgres_port=port)


def test_reads_environment_variables(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "env_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", FAKE_PASSWORD)
    monkeypatch.setenv("POSTGRES_DB", "env_db")
    monkeypatch.setenv("APP_ENV", "test")
    s = Settings(_env_file=None)
    assert (s.postgres_user, s.postgres_db, s.app_env) == ("env_user", "env_db", "test")


def test_reads_env_file_and_ignores_unknown_keys(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "POSTGRES_USER=file_user\n"
        f"POSTGRES_PASSWORD={FAKE_PASSWORD}\n"
        "POSTGRES_DB=file_db\n"
        "TEST_DATABASE_URL=postgresql://x:y@h/z_test\n"  # unrelated key must not break loading
    )
    s = Settings(_env_file=env_file)
    assert (s.postgres_user, s.postgres_db) == ("file_user", "file_db")


def test_blank_value_in_env_file_counts_as_unset(tmp_path):
    # This is exactly what a freshly copied .env.example looks like.
    env_file = tmp_path / ".env"
    env_file.write_text("POSTGRES_USER=u\nPOSTGRES_PASSWORD=\nPOSTGRES_DB=d\n")
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=env_file)
    assert "POSTGRES_PASSWORD" in str(exc_info.value)


def test_environment_overrides_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"POSTGRES_USER=file_user\nPOSTGRES_PASSWORD={FAKE_PASSWORD}\nPOSTGRES_DB=d\n"
    )
    monkeypatch.setenv("POSTGRES_USER", "env_user")
    assert Settings(_env_file=env_file).postgres_user == "env_user"


def test_get_settings_is_cached(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", FAKE_PASSWORD)
    monkeypatch.setenv("POSTGRES_DB", "d")
    assert get_settings() is get_settings()
    get_settings.cache_clear()
    monkeypatch.setenv("POSTGRES_DB", "other")
    assert get_settings().postgres_db == "other"
