"""Schema and repository tests against an in-memory SQLite database."""

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from itm_arena.db.models import Attempt, AttemptAnswer, Question, Report, User
from itm_arena.db.repository import (
    AttemptRepository,
    QuizRepository,
    ReportRepository,
    UserRepository,
)
from itm_arena.db.session import create_session_factory, create_sqlite_engine, create_tables
from itm_arena.domain.types import QuestionDraft, QuizDraft, SubmittedAnswer

EXPECTED_TABLES = {
    "users",
    "quizzes",
    "questions",
    "attempts",
    "attempt_answers",
    "reports",
}


@pytest.fixture
def engine():
    engine = create_sqlite_engine()
    create_tables(engine)
    return engine


@pytest.fixture
def session(engine):
    factory = create_session_factory(engine)
    with factory() as session:
        yield session


def make_user(session, nickname: str) -> User:
    return UserRepository(session).add(
        nickname=nickname,
        nickname_key=nickname.casefold(),
        pin_hash="hash",
        pin_salt="salt",
    )


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


def test_create_tables_creates_every_table(engine):
    assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())


def test_nickname_key_is_unique(session):
    make_user(session, "mina")
    with pytest.raises(IntegrityError):
        make_user(session, "Mina")
    session.rollback()


def test_one_quiz_per_owner(session):
    owner = make_user(session, "mina")
    quizzes = QuizRepository(session)
    quizzes.create_with_questions(
        owner_id=owner.id, title="mina's quiz", draft=make_draft()
    )
    with pytest.raises(IntegrityError):
        quizzes.create_with_questions(
            owner_id=owner.id, title="mina's second quiz", draft=make_draft()
        )
    session.rollback()


def test_question_position_is_unique_within_a_quiz(session):
    owner = make_user(session, "mina")
    quiz = QuizRepository(session).create_with_questions(
        owner_id=owner.id, title="mina's quiz", draft=make_draft()
    )
    session.add(
        Question(
            quiz_id=quiz.id,
            position=1,
            text="Another question at position 1",
            choice_1="a",
            choice_2="b",
            choice_3="c",
            choice_4="d",
            answer_index=0,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_one_attempt_per_solver(session):
    owner = make_user(session, "mina")
    solver = make_user(session, "jun")
    quiz = QuizRepository(session).create_with_questions(
        owner_id=owner.id, title="mina's quiz", draft=make_draft()
    )
    session.add(Attempt(quiz_id=quiz.id, solver_id=solver.id, score=7))
    session.flush()
    session.add(Attempt(quiz_id=quiz.id, solver_id=solver.id, score=9))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_one_answer_per_question_within_an_attempt(session):
    owner = make_user(session, "mina")
    solver = make_user(session, "jun")
    quiz = QuizRepository(session).create_with_questions(
        owner_id=owner.id, title="mina's quiz", draft=make_draft()
    )
    question = QuizRepository(session).list_questions(quiz.id)[0]
    attempt = Attempt(quiz_id=quiz.id, solver_id=solver.id, score=1)
    session.add(attempt)
    session.flush()
    session.add(
        AttemptAnswer(
            attempt_id=attempt.id,
            question_id=question.id,
            selected_index=0,
            is_correct=True,
        )
    )
    session.flush()
    session.add(
        AttemptAnswer(
            attempt_id=attempt.id,
            question_id=question.id,
            selected_index=1,
            is_correct=False,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_the_same_person_cannot_report_a_quiz_twice(session):
    owner = make_user(session, "mina")
    reporter = make_user(session, "jun")
    quiz = QuizRepository(session).create_with_questions(
        owner_id=owner.id, title="mina's quiz", draft=make_draft()
    )
    reports = ReportRepository(session)
    assert reports.add(quiz=quiz, reporter_id=reporter.id) == 1
    session.add(Report(quiz_id=quiz.id, reporter_id=reporter.id))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_position_outside_one_to_ten_is_rejected(session):
    owner = make_user(session, "mina")
    quiz = QuizRepository(session).create_with_questions(
        owner_id=owner.id, title="mina's quiz", draft=make_draft()
    )
    session.add(
        Question(
            quiz_id=quiz.id,
            position=11,
            text="One question too many",
            choice_1="a",
            choice_2="b",
            choice_3="c",
            choice_4="d",
            answer_index=0,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_create_with_questions_stores_ten_questions_in_order(session):
    owner = make_user(session, "mina")
    quiz = QuizRepository(session).create_with_questions(
        owner_id=owner.id, title="mina's quiz", draft=make_draft()
    )
    questions = QuizRepository(session).list_questions(quiz.id)
    assert [question.position for question in questions] == list(range(1, 11))
    assert questions[0].choices == ["choice 1-1", "choice 1-2", "choice 1-3", "choice 1-4"]


def test_question_views_do_not_expose_the_answer(session):
    owner = make_user(session, "mina")
    quiz = QuizRepository(session).create_with_questions(
        owner_id=owner.id, title="mina's quiz", draft=make_draft(answer_index=2)
    )
    views = QuizRepository(session).list_question_views(quiz.id)
    assert len(views) == 10
    assert not any("answer" in vars(view) for view in views)


def test_answer_keys_match_the_draft(session):
    owner = make_user(session, "mina")
    quiz = QuizRepository(session).create_with_questions(
        owner_id=owner.id, title="mina's quiz", draft=make_draft(answer_index=3)
    )
    keys = QuizRepository(session).list_answer_keys(quiz.id)
    assert len(keys) == 10
    assert {key.answer_index for key in keys} == {3}


def test_only_visible_quizzes_are_listed(session):
    quizzes = QuizRepository(session)
    first = quizzes.create_with_questions(
        owner_id=make_user(session, "mina").id, title="mina's quiz", draft=make_draft()
    )
    second = quizzes.create_with_questions(
        owner_id=make_user(session, "jun").id, title="jun's quiz", draft=make_draft()
    )
    assert {quiz.id for quiz in quizzes.list_visible()} == {first.id, second.id}

    quizzes.set_hidden_by_owner(first, True)
    quizzes.set_hidden_by_reports(second, True)
    assert quizzes.list_visible() == []
    assert first.is_visible is False

    # The owner can show their own quiz again; a reported one stays hidden
    quizzes.set_hidden_by_owner(first, False)
    assert {quiz.id for quiz in quizzes.list_visible()} == {first.id}


def test_scores_are_returned_as_nickname_and_score_pairs(session):
    owner = make_user(session, "mina")
    quiz = QuizRepository(session).create_with_questions(
        owner_id=owner.id, title="mina's quiz", draft=make_draft()
    )
    question_ids = [
        question.id for question in QuizRepository(session).list_questions(quiz.id)
    ]
    attempts = AttemptRepository(session)
    for nickname, score in [("jun", 10), ("hana", 8)]:
        solver = make_user(session, nickname)
        answers = [
            SubmittedAnswer(question_id=question_id, selected_index=0)
            for question_id in question_ids
        ]
        attempts.add_with_answers(
            quiz_id=quiz.id,
            solver_id=solver.id,
            score=score,
            answers=answers,
            correct_by_question={question_id: True for question_id in question_ids},
        )
        assert attempts.has_attempted(quiz.id, solver.id) is True
        assert attempts.list_solved_quiz_ids(solver.id) == {quiz.id}

    assert sorted(attempts.list_scores(quiz.id)) == [("hana", 8), ("jun", 10)]
