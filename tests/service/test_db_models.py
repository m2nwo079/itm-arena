"""Schema tests for the database tables, against an in-memory SQLite database.

Every test tries to break one constraint on purpose. If a test stops raising
IntegrityError, the constraint is missing from the table, not just unused.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from itm_arena.db.models import Base, User, Quiz, Question, Attempt, AttemptAnswer
from itm_arena.db.repository import UserRepository, QuizRepository
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

def make_quiz(owner_id, **overrides):
    return Quiz(owner_id=owner_id, title="mina's quiz", **overrides)


def add_user(session, nickname="mina"):
    owner = make_user(nickname, nickname)
    session.add(owner)
    session.flush()
    return owner


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

def test_quizzes_table_is_created(engine):
    assert "quizzes" in inspect(engine).get_table_names()


def test_one_quiz_per_owner(session):
    owner = add_user(session)
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
    owner = add_user(session)
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
        first = add_user(session, "mina")
        second = add_user(session, "jun")
        session.add(make_quiz(first.id))
        session.add(make_quiz(second.id))

    with factory() as session:
        assert len(session.scalars(select(Quiz)).all()) == 2


### about Question 

def make_question(quiz_id, position, **kwargs):
    values = dict(
        quiz_id=quiz_id, position=position, text=f"Question {position}",
        choice_1="a", choice_2="b", choice_3="c", choice_4="d", answer_index=0,
    )
    values.update(kwargs)
    return Question(**values)


def add_quiz(session, nickname="mina"):
    owner = make_user(nickname, nickname)
    session.add(owner)
    session.flush()
    quiz = make_quiz(owner.id)
    session.add(quiz)
    session.flush()
    return quiz


def test_questions_table_is_created(engine):
    assert "questions" in inspect(engine).get_table_names()


def test_one_question_per_position_in_a_quiz(session):
    quiz = add_quiz(session)
    session.add(make_question(quiz.id, 1))
    session.flush()

    session.add(make_question(quiz.id, 1))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_two_quizzes_can_both_have_position_one(session):
    first = add_quiz(session, "mina")
    second = add_quiz(session, "jun")
    session.add(make_question(first.id, 1))
    session.add(make_question(second.id, 1))
    session.flush()


def test_position_outside_one_to_ten_is_rejected(session):
    quiz = add_quiz(session)
    session.add(make_question(quiz.id, 11))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_answer_index_outside_zero_to_three_is_rejected(session):
    quiz = add_quiz(session)
    session.add(make_question(quiz.id, 1, answer_index=4))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_choices_are_returned_in_display_order(session):
    quiz = add_quiz(session)
    question = make_question(quiz.id, 1, choice_1="w", choice_2="x", choice_3="y", choice_4="z")
    session.add(question)
    session.flush()
    assert question.choices == ["w", "x", "y", "z"]


### about attempt and attempt_answer

def test_both_attempt_tables_are_created(engine):
    names = inspect(engine).get_table_names()
    assert "attempts" in names
    assert "attempt_answers" in names


def test_one_attempt_per_solver_per_quiz(session):
    quiz = add_quiz(session, "mina")
    solver = add_user(session, "jun")
    session.add(Attempt(quiz_id=quiz.id, solver_id=solver.id, score=7))
    session.flush()

    session.add(Attempt(quiz_id=quiz.id, solver_id=solver.id, score=9))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_a_solver_can_attempt_two_different_quizzes(session):
    first = add_quiz(session, "mina")
    second = add_quiz(session, "hana")
    solver = add_user(session, "jun")
    session.add(Attempt(quiz_id=first.id, solver_id=solver.id, score=7))
    session.add(Attempt(quiz_id=second.id, solver_id=solver.id, score=5))
    session.flush()


def test_score_outside_zero_to_ten_is_rejected(session):
    quiz = add_quiz(session, "mina")
    solver = add_user(session, "jun")
    session.add(Attempt(quiz_id=quiz.id, solver_id=solver.id, score=11))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_one_answer_per_question_within_an_attempt(session):
    quiz = add_quiz(session, "mina")
    solver = add_user(session, "jun")
    question = make_question(quiz.id, 1)
    session.add(question)
    session.flush()
    attempt = Attempt(quiz_id=quiz.id, solver_id=solver.id, score=1)
    session.add(attempt)
    session.flush()

    session.add(AttemptAnswer(
        attempt_id=attempt.id, question_id=question.id,
        selected_index=0, is_correct=True,
    ))
    session.flush()

    session.add(AttemptAnswer(
        attempt_id=attempt.id, question_id=question.id,
        selected_index=1, is_correct=False,
    ))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_selected_index_outside_zero_to_three_is_rejected(session):
    quiz = add_quiz(session, "mina")
    solver = add_user(session, "jun")
    question = make_question(quiz.id, 1)
    session.add(question)
    session.flush()
    attempt = Attempt(quiz_id=quiz.id, solver_id=solver.id, score=0)
    session.add(attempt)
    session.flush()

    session.add(AttemptAnswer(
        attempt_id=attempt.id, question_id=question.id,
        selected_index=4, is_correct=False,
    ))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


### about timestamps

def test_timestamps_come_back_as_aware_utc(session):
    user = add_user(session)
    locked = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
    user.locked_until = locked
    session.flush()
    session.expire_all()

    stored = session.get(User, user.id)
    assert stored.locked_until == locked
    assert stored.locked_until.tzinfo is not None
    assert stored.created_at.tzinfo is not None
    # The lockout check in #5 compares against an aware "now"; on a naive value
    # this line would raise TypeError on SQLite
    assert datetime.now(timezone.utc) > stored.created_at


def test_a_naive_timestamp_is_read_back_as_utc(session):
    user = add_user(session)
    naive = datetime(2026, 11, 17, 12, 0)
    user.locked_until = naive
    session.flush()
    session.expire_all()

    stored = session.get(User, user.id)
    assert stored.locked_until == naive.replace(tzinfo=timezone.utc)
