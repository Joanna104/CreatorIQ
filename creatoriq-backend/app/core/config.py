"""Application settings, read from environment variables (and an optional ``.env`` file).

Nothing secret has a default value. The database is configured either with a full
``DATABASE_URL`` or with the ``POSTGRES_*`` parts; startup fails fast with a clear message
if neither is complete.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

# Drivers we accept. psycopg (v3) is the one installed from requirements.txt.
_ACCEPTED_DRIVERS = {"postgresql", "postgresql+psycopg"}
_DRIVER = "postgresql+psycopg"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        # "POSTGRES_PASSWORD=" (empty) is treated as "not set".
        env_ignore_empty=True,
        # Validation errors must never echo input values, which can contain passwords.
        hide_input_in_errors=True,
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    database_url: SecretStr | None = None
    postgres_user: str | None = None
    postgres_password: SecretStr | None = None
    postgres_host: str = "localhost"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str | None = None

    db_connect_timeout: int = Field(default=3, ge=1, le=60)
    db_echo: bool = False

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _check_database_configuration(self) -> Settings:
        if self.database_url is not None:
            try:
                url = make_url(self.database_url.get_secret_value())
            except ArgumentError:
                # Deliberately do not include the value: it may contain a password.
                raise ValueError("DATABASE_URL is not a valid database URL") from None
            if url.drivername not in _ACCEPTED_DRIVERS:
                raise ValueError(
                    "DATABASE_URL must start with postgresql:// or postgresql+psycopg://"
                )
            return self

        password = self.postgres_password.get_secret_value() if self.postgres_password else ""
        missing = [
            name
            for name, value in (
                ("POSTGRES_USER", self.postgres_user),
                ("POSTGRES_PASSWORD", password),
                ("POSTGRES_DB", self.postgres_db),
            )
            if not value
        ]
        if missing:
            raise ValueError(
                "Database is not configured. Set DATABASE_URL, or set all of POSTGRES_USER, "
                f"POSTGRES_PASSWORD and POSTGRES_DB (missing: {', '.join(missing)}). "
                "See .env.example."
            )
        return self

    @property
    def sqlalchemy_url(self) -> URL:
        """The database URL as a SQLAlchemy ``URL`` (password is escaped correctly)."""
        if self.database_url is not None:
            return make_url(self.database_url.get_secret_value()).set(drivername=_DRIVER)
        assert self.postgres_password is not None  # guaranteed by the validator above
        return URL.create(
            drivername=_DRIVER,
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
