"""Schema tests for the users table, against an in-memory SQLite database."""

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from itm_arena.db.models import Base, User
from itm_arena.db.session import (
    create_session_factory,
    create_sqlite_engine,
    create_tables,
    session_scope,
)

# fixture = 테스트에 필요한 준비물 만들어주는 느낌.
@pytest.fixture
def engine():
    engine = create_sqlite_engine()
    create_tables(engine)
    return engine


@pytest.fixture
def factory(engine):
    return create_session_factory(engine)


@pytest.fixture
def session(factory):
    with factory() as session:
        yield session

# 테스트 헬퍼, 가짜 유저 만들어줌
def make_user(nickname: str, nickname_key: str, **overrides) -> User:
    return User(
        nickname=nickname,
        nickname_key=nickname_key,
        pin_hash="hash",
        pin_salt="salt",
        **overrides,
    )


def test_users_table_is_created(engine):
    assert "users" in inspect(engine).get_table_names()

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

def test_session_scope_commits_on_success(factory):
    with session_scope(factory) as session:
        session.add(make_user("mina", "mina"))

    with factory() as session:
        assert len(session.scalars(select(User)).all()) == 1

# rollback test
def test_session_scope_rolls_back_every_row_on_failure(factory):
    with pytest.raises(IntegrityError):
        with session_scope(factory) as session:
            session.add(make_user("mina", "mina"))
            session.add(make_user("Mina", "mina"))

    with factory() as session:
        assert session.scalars(select(User)).all() == []