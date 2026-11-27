"""tests for repository.py in db"""

import pytest
from sqlalchemy import func, select, inspect
from sqlalchemy.exc import IntegrityError

from itm_arena.db.models import Attempt, AttemptAnswer, Quiz
from itm_arena.db.repository import AttemptRepository, QuizRepository, UserRepository, ReportRepository
from itm_arena.db.session import (
    create_session_factory,
    create_sqlite_engine,
    create_tables,
    session_scope,
)
from itm_arena.domain.grading import grade_submission
from itm_arena.domain.types import (
    GradeResult,
    QuestionDraft,
    QuizDraft,
    SubmittedAnswer,
)


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


### Test helper
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

def add_quiz(session, nickname="mina", answer_index=0):
    owner = add_user(session, nickname)
    return QuizRepository(session).create_with_questions(
        owner_id=owner.id, title=f"{nickname}'s quiz", draft=make_draft(answer_index)
    )


def submission(session, quiz, selected_index=0):
    """Ten answers for a quiz, all choosing the same index."""
    views = QuizRepository(session).list_question_views(quiz.id)
    return [
        SubmittedAnswer(question_id=view.question_id, selected_index=selected_index)
        for view in views
    ]


### about UserRepository

def test_add_gives_the_user_an_id(session):
    assert add_user(session).id is not None


def test_get_by_nickname_key_finds_the_user(session):
    add_user(session, "mina")
    users = UserRepository(session)
    assert users.get_by_nickname_key("mina").nickname == "mina"
    assert users.get_by_nickname_key("jun") is None


### about QuizRepository

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


### about AttemptRepository

def test_add_with_answers_stores_the_attempt_and_ten_answers(session):
    quiz = add_quiz(session)
    solver = add_user(session, "jun")
    answers = submission(session, quiz)
    result = GradeResult(score=10, correct_by_question={a.question_id: True for a in answers})

    attempt = AttemptRepository(session).add_with_answers(
        quiz_id=quiz.id, solver_id=solver.id, answers=answers, result=result
    )

    assert attempt.score == 10
    assert session.scalar(
        select(func.count(AttemptAnswer.id)).where(AttemptAnswer.attempt_id == attempt.id)
    ) == 10


def test_has_attempted_flips_after_the_attempt_is_saved(session):
    quiz = add_quiz(session)
    solver = add_user(session, "jun")
    attempts = AttemptRepository(session)
    assert attempts.has_attempted(quiz.id, solver.id) is False

    answers = submission(session, quiz)
    attempts.add_with_answers(
        quiz_id=quiz.id, solver_id=solver.id, answers=answers,
        result=GradeResult(score=0, correct_by_question={a.question_id: False for a in answers}),
    )
    assert attempts.has_attempted(quiz.id, solver.id) is True


def test_a_second_attempt_by_the_same_solver_is_rejected(session):
    quiz = add_quiz(session)
    solver = add_user(session, "jun")
    attempts = AttemptRepository(session)
    answers = submission(session, quiz)
    result = GradeResult(score=5, correct_by_question={a.question_id: True for a in answers})

    attempts.add_with_answers(
        quiz_id=quiz.id, solver_id=solver.id, answers=answers, result=result
    )
    with pytest.raises(IntegrityError):
        attempts.add_with_answers(
            quiz_id=quiz.id, solver_id=solver.id, answers=answers, result=result
        )
    session.rollback()


def test_grading_and_storing_work_together(session):
    quiz = add_quiz(session, answer_index=2)
    solver = add_user(session, "jun")
    quizzes = QuizRepository(session)

    views = quizzes.list_question_views(quiz.id)
    # the first eight are right, the last two are wrong
    answers = [
        SubmittedAnswer(question_id=v.question_id, selected_index=2 if i < 8 else 0)
        for i, v in enumerate(views)
    ]
    result = grade_submission(quizzes.list_answer_keys(quiz.id), answers)

    attempts = AttemptRepository(session)
    attempt = attempts.add_with_answers(
        quiz_id=quiz.id, solver_id=solver.id, answers=answers, result=result
    )

    assert attempt.score == 8
    stored = attempts.list_answers(attempt.id)
    assert [row.is_correct for row in stored] == [True] * 8 + [False] * 2


def test_one_bad_answer_rolls_back_the_whole_attempt(factory):
    with session_scope(factory) as session:
        quiz = add_quiz(session)
        solver = add_user(session, "jun")

    with factory() as session:
        answers = submission(session, quiz, selected_index=0)
        broken = answers[:-1] + [
            SubmittedAnswer(question_id=answers[-1].question_id, selected_index=4)
        ]
        result = GradeResult(score=9, correct_by_question={a.question_id: True for a in broken})

        with pytest.raises(IntegrityError):
            with session_scope(factory) as scoped:
                AttemptRepository(scoped).add_with_answers(
                    quiz_id=quiz.id, solver_id=solver.id, answers=broken, result=result
                )

    with factory() as session:
        assert session.scalars(select(Attempt)).all() == []
        assert session.scalars(select(AttemptAnswer)).all() == []


### about ReportRepository

def test_reports_table_is_created(engine):
    assert "reports" in inspect(engine).get_table_names()


def test_the_same_person_cannot_report_a_quiz_twice(session):
    quiz = add_quiz(session, "mina")
    reporter = add_user(session, "jun")
    reports = ReportRepository(session)

    reports.add(quiz=quiz, reporter_id=reporter.id)
    with pytest.raises(IntegrityError):
        reports.add(quiz=quiz, reporter_id=reporter.id)
    session.rollback()


def test_one_person_can_report_two_different_quizzes(session):
    first = add_quiz(session, "mina")
    second = add_quiz(session, "hana")
    reporter = add_user(session, "jun")
    reports = ReportRepository(session)

    reports.add(quiz=first, reporter_id=reporter.id)
    reports.add(quiz=second, reporter_id=reporter.id)
    assert reports.count(first.id) == 1
    assert reports.count(second.id) == 1


def test_count_grows_with_each_different_reporter(session):
    quiz = add_quiz(session, "mina")
    reports = ReportRepository(session)
    assert reports.count(quiz.id) == 0

    for nickname in ["jun", "hana", "suk"]:
        reporter = add_user(session, nickname)
        reports.add(quiz=quiz, reporter_id=reporter.id)
    assert reports.count(quiz.id) == 3


def test_exists_flips_after_the_report_is_recorded(session):
    quiz = add_quiz(session, "mina")
    reporter = add_user(session, "jun")
    reports = ReportRepository(session)
    assert reports.exists(quiz.id, reporter.id) is False

    reports.add(quiz=quiz, reporter_id=reporter.id)
    assert reports.exists(quiz.id, reporter.id) is True


def test_the_reporter_must_exist(session):
    quiz = add_quiz(session, "mina")
    with pytest.raises(IntegrityError):
        ReportRepository(session).add(quiz=quiz, reporter_id=999)
    session.rollback()


def test_add_returns_the_new_count(session):
    quiz = add_quiz(session)
    reports = ReportRepository(session)
    assert reports.add(quiz=quiz, reporter_id=add_user(session, "jun").id) == 1
    assert reports.add(quiz=quiz, reporter_id=add_user(session, "hana").id) == 2
    assert reports.add(quiz=quiz, reporter_id=add_user(session, "suk").id) == 3


def test_report_count_matches_the_reports_table(session):
    quiz = add_quiz(session)
    reports = ReportRepository(session)
    for nickname in ["jun", "hana"]:
        reports.add(quiz=quiz, reporter_id=add_user(session, nickname).id)
    assert quiz.report_count == reports.count(quiz.id) == 2


def test_a_rejected_duplicate_leaves_the_counter_alone(factory):
    with session_scope(factory) as session:
        quiz = add_quiz(session)
        reporter = add_user(session, "jun")
        ReportRepository(session).add(quiz=quiz, reporter_id=reporter.id)
    quiz_id, reporter_id = quiz.id, reporter.id

    with pytest.raises(IntegrityError):
        with session_scope(factory) as session:
            ReportRepository(session).add(
                quiz=session.get(Quiz, quiz_id), reporter_id=reporter_id
            )

    with factory() as session:
        assert session.get(Quiz, quiz_id).report_count == 1
        assert ReportRepository(session).count(quiz_id) == 1
