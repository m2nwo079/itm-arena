"""Schema tests for the users table, against an in-memory SQLite database."""

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from itm_arena.db.models import Base, User


@pytest.fixture
def session():
    # A fresh in-memory database per test, so no test can see another's rows
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def make_user(nickname: str, nickname_key: str, **overrides) -> User:
    return User(
        nickname=nickname,
        nickname_key=nickname_key,
        pin_hash="hash",
        pin_salt="salt",
        **overrides,
    )


def test_users_table_is_created(session):
    assert "users" in inspect(session.get_bind()).get_table_names()


def test_nickname_key_is_unique(session):
    session.add(make_user("mina", "mina"))
    session.flush()

    # A different display name with the same key is still the same account
    session.add(make_user("Mina", "mina"))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_failed_attempts_cannot_be_negative(session):
    session.add(make_user("jun", "jun", failed_attempts=-1))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()