"""Schema tests for the users table, against an in-memory SQLite database."""

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from itm_arena.db.models import Base, User, Quiz
from itm_arena.db.session import (
    create_session_factory,
    create_sqlite_engine,
    create_tables,
    session_scope,
)

# A fixture builds whatever a test needs, and runs again for every test.
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

# Test helper that builds a fake user.
def make_user(nickname: str, nickname_key: str, **overrides) -> User:
    return User(
        nickname=nickname,
        nickname_key=nickname_key,
        pin_hash="hash",
        pin_salt="salt",
        **overrides,
    )

### about Users

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


### about Quiz

def make_quiz(owner_id, **overrides):
    return Quiz(owner_id=owner_id, title="mina's quiz", **overrides)


def add_owner(session, nickname="mina"):
    owner = make_user(nickname, nickname)
    session.add(owner)
    session.flush()
    return owner


def test_quizzes_table_is_created(engine):
    assert "quizzes" in inspect(engine).get_table_names()


def test_one_quiz_per_owner(session):
    owner = add_owner(session)
    session.add(make_quiz(owner.id))
    session.flush()

    session.add(make_quiz(owner.id))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_quiz_owner_must_exist(session):
    session.add(make_quiz(999))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_a_quiz_is_visible_until_it_is_hidden(session):
    owner = add_owner(session)
    quiz = make_quiz(owner.id)
    session.add(quiz)
    session.flush()
    assert quiz.is_visible is True

    quiz.hidden_by_owner = True
    assert quiz.is_visible is False

    quiz.hidden_by_owner = False
    quiz.hidden_by_reports = True
    assert quiz.is_visible is False


def test_two_users_can_each_have_a_quiz(factory):
    with session_scope(factory) as session:
        first = add_owner(session, "mina")
        second = add_owner(session, "jun")
        session.add(make_quiz(first.id))
        session.add(make_quiz(second.id))

    with factory() as session:
        assert len(session.scalars(select(Quiz)).all()) == 2