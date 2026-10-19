"""Engine creation and the connectivity check. Creating an engine never opens a connection."""

from sqlalchemy import Engine, create_engine, text

from app.core.config import Settings


def build_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.sqlalchemy_url,
        pool_pre_ping=True,
        echo=settings.db_echo,
        connect_args={"connect_timeout": settings.db_connect_timeout},
    )


def check_database(engine: Engine) -> None:
    """Open a connection and run ``SELECT 1``. Raises a SQLAlchemyError if unreachable."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
