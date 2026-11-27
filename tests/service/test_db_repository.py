"""tests for repository.py in db"""

import pytest
from sqlalchemy.exc import IntegrityError

from itm_arena.db.repository import QuizRepository, UserRepository
from itm_arena.db.session import (
    create_session_factory,
    create_sqlite_engine,
    create_tables,
)
from itm_arena.domain.types import QuestionDraft, QuizDraft


@pytest.fixture
def engine():
    engine = create_sqlite_engine()
    create_tables(engine)
    return engine


@pytest.fixture
def session(engine):
    with create_session_factory(engine)() as session:
        yield session


def make_draft(answer_index: int = 0) -> QuizDraft:
    return QuizDraft(
        questions=[
            QuestionDraft(
                text=f"Question {number}",
                choices=[f"choice {number}-{choice}" for choice in range(1, 5)],
                answer_index=answer_index,
            )
            for number in range(1, 11)
        ]
    )


def add_user(session, nickname="mina"):
    return UserRepository(session).add(
        nickname=nickname, nickname_key=nickname, pin_hash="hash", pin_salt="salt"
    )


def test_add_gives_the_user_an_id(session):
    assert add_user(session).id is not None


def test_get_by_nickname_key_finds_the_user(session):
    add_user(session, "mina")
    users = UserRepository(session)
    assert users.get_by_nickname_key("mina").nickname == "mina"
    assert users.get_by_nickname_key("jun") is None


def test_create_with_questions_stores_ten_questions_in_order(session):
    owner = add_user(session)
    quizzes = QuizRepository(session)
    quiz = quizzes.create_with_questions(
        owner_id=owner.id, title="mina's quiz", draft=make_draft()
    )

    views = quizzes.list_question_views(quiz.id)
    assert [view.position for view in views] == list(range(1, 11))
    assert views[0].choices == [
        "choice 1-1", "choice 1-2", "choice 1-3", "choice 1-4",
    ]


def test_get_by_owner_returns_the_quiz(session):
    owner = add_user(session)
    quizzes = QuizRepository(session)
    assert quizzes.get_by_owner(owner.id) is None

    quiz = quizzes.create_with_questions(
        owner_id=owner.id, title="mina's quiz", draft=make_draft()
    )
    assert quizzes.get_by_owner(owner.id).id == quiz.id


def test_a_second_quiz_for_the_same_owner_is_rejected(session):
    owner = add_user(session)
    quizzes = QuizRepository(session)
    quizzes.create_with_questions(
        owner_id=owner.id, title="mina's quiz", draft=make_draft()
    )
    with pytest.raises(IntegrityError):
        quizzes.create_with_questions(
            owner_id=owner.id, title="mina's second quiz", draft=make_draft()
        )
    session.rollback()


def test_question_views_never_carry_the_answer(session):
    owner = add_user(session)
    quizzes = QuizRepository(session)
    quiz = quizzes.create_with_questions(
        owner_id=owner.id, title="mina's quiz", draft=make_draft(answer_index=2)
    )

    views = quizzes.list_question_views(quiz.id)
    assert len(views) == 10
    assert not any("answer" in vars(view) for view in views)


def test_answer_keys_match_the_draft(session):
    owner = add_user(session)
    quizzes = QuizRepository(session)
    quiz = quizzes.create_with_questions(
        owner_id=owner.id, title="mina's quiz", draft=make_draft(answer_index=3)
    )

    keys = quizzes.list_answer_keys(quiz.id)
    assert len(keys) == 10
    assert {key.answer_index for key in keys} == {3}