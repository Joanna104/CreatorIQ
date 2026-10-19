from typing import Annotated

import pytest
from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.db.session import build_engine, check_database


def test_building_an_engine_does_not_connect(unreachable_settings):
    engine = build_engine(unreachable_settings)  # would raise if it tried to connect
    assert engine.url.drivername == "postgresql+psycopg"
    engine.dispose()


def test_check_database_succeeds_when_the_database_answers(sqlite_engine):
    check_database(sqlite_engine)  # SQLite stand-in for SELECT 1


def test_check_database_raises_when_unreachable(unreachable_settings):
    engine = build_engine(unreachable_settings)
    with pytest.raises(OperationalError):
        check_database(engine)
    engine.dispose()


def test_get_session_yields_a_session_and_closes_it(make_client, settings, sqlite_engine):
    seen: list[Session] = []

    def add_route(app):
        @app.get("/_t/session")
        def use_session(session: Annotated[Session, Depends(get_session)]):
            seen.append(session)
            return {"one": session.execute(text("SELECT 1")).scalar()}

    response = make_client(settings, engine=sqlite_engine, extra_routes=add_route).get(
        "/_t/session"
    )
    assert response.json() == {"one": 1}
    assert len(seen) == 1
    assert not seen[0].in_transaction()  # closed after the request
