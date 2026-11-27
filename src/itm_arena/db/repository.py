"""Repositories: the only place that talks to the database.

These read and write rows and nothing else. 
Who may solve a quiz, when an account is locked, and when three reports hide a quiz are service-level rules
(issues #5, #7 and #15), not repository rules.

Repositories flush but never commit, so a caller can wrap several calls in one transaction with session_scope.
"""

from collections.abc import Sequence

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from itm_arena.db.models import Question, Quiz, User, Attempt, AttemptAnswer, Report
from itm_arena.domain.types import AnswerKey, QuestionView, QuizDraft, GradeResult, SubmittedAnswer


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_nickname_key(self, nickname_key: str) -> User | None:
        """Look a user up by the normalised nickname used for uniqueness."""
        return self._session.scalar(
            select(User).where(User.nickname_key == nickname_key)
        )

    # register
    def add(
        self,
        *,
        nickname: str,
        nickname_key: str,
        pin_hash: str,
        pin_salt: str,
    ) -> User:
        user = User(
            nickname=nickname,
            nickname_key=nickname_key,
            pin_hash=pin_hash,
            pin_salt=pin_salt,
        )
        self._session.add(user)
        self._session.flush()
        return user


class QuizRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_owner(self, owner_id: int) -> Quiz | None:
        """The owner's only quiz, hidden or not, or None if they have none."""
        return self._session.scalar(select(Quiz).where(Quiz.owner_id == owner_id))

    def create_with_questions(
        self, *, owner_id: int, title: str, draft: QuizDraft
    ) -> Quiz:
        """Save a quiz and all of its questions as one unit of work.

        Positions are assigned from the order of the draft, starting at 1. The
        draft is expected to be valid already; validation is issue #3.
        """
        quiz = Quiz(owner_id=owner_id, title=title)
        self._session.add(quiz)
        self._session.flush()

        for position, question in enumerate(draft.questions, start=1):
            first, second, third, fourth = question.choices
            self._session.add(
                Question(
                    quiz_id=quiz.id,
                    position=position,
                    text=question.text,
                    choice_1=first,
                    choice_2=second,
                    choice_3=third,
                    choice_4=fourth,
                    answer_index=question.answer_index,
                )
            )
        self._session.flush()
        return quiz

    def list_question_views(self, quiz_id: int) -> list[QuestionView]:
        """Questions as the solver sees them, without the correct answers."""
        statement = (
            select(Question)
            .where(Question.quiz_id == quiz_id)
            .order_by(Question.position)
        )
        return [
            QuestionView(
                question_id=question.id,
                position=question.position,
                text=question.text,
                choices=question.choices,
            )
            for question in self._session.scalars(statement)
        ]

    def list_answer_keys(self, quiz_id: int) -> list[AnswerKey]:
        """Correct answers for grading (#4). Never sent to the browser."""
        statement = (
            select(Question.id, Question.answer_index)
            .where(Question.quiz_id == quiz_id)
            .order_by(Question.position)
        )
        return [
            AnswerKey(question_id=question_id, answer_index=answer_index)
            for question_id, answer_index in self._session.execute(statement).all()
        ]


class AttemptRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_for_solver(self, quiz_id: int, solver_id: int) -> Attempt | None:
        return self._session.scalar(
            select(Attempt).where(
                Attempt.quiz_id == quiz_id, Attempt.solver_id == solver_id
            )
        )

    def has_attempted(self, quiz_id: int, solver_id: int) -> bool:
        """A friendly check for the UI. The UNIQUE constraint is what enforces it."""
        return self.get_for_solver(quiz_id, solver_id) is not None

    def add_with_answers(
        self,
        *,
        quiz_id: int,
        solver_id: int,
        answers: Sequence[SubmittedAnswer],
        result: GradeResult,
    ) -> Attempt:
        """Save an attempt and its answers as one unit of work.

        The score and the per-question flags come from grading (#4). The UNIQUE
        constraint on (quiz_id, solver_id) is what actually stops a second
        attempt, even if two submissions arrive at the same time.
        """
        attempt = Attempt(quiz_id=quiz_id, solver_id=solver_id, score=result.score)
        self._session.add(attempt)
        self._session.flush()

        for answer in answers:
            self._session.add(
                AttemptAnswer(
                    attempt_id=attempt.id,
                    question_id=answer.question_id,
                    selected_index=answer.selected_index,
                    is_correct=result.correct_by_question[answer.question_id],
                )
            )
        self._session.flush()
        return attempt

    def list_answers(self, attempt_id: int) -> list[AttemptAnswer]:
        """Stored answers for the result screen (#12), in question order."""
        statement = (
            select(AttemptAnswer)
            .join(Question, Question.id == AttemptAnswer.question_id)
            .where(AttemptAnswer.attempt_id == attempt_id)
            .order_by(Question.position)
        )
        return list(self._session.scalars(statement))


class ReportRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def exists(self, quiz_id: int, reporter_id: int) -> bool:
        """A friendly check for the UI. The UNIQUE constraint is what enforces it."""
        statement = select(Report.id).where(
            Report.quiz_id == quiz_id, Report.reporter_id == reporter_id
        )
        return self._session.scalar(statement) is not None

    def count(self, quiz_id: int) -> int:
        """How many different people have reported this quiz."""
        statement = select(func.count(Report.id)).where(Report.quiz_id == quiz_id)
        return self._session.scalar(statement) or 0

    def add(self, *, quiz: Quiz, reporter_id: int) -> int:
        """Record one report and return the quiz's new report count.

        The insert goes first, so a second report from the same person is
        rejected by the UNIQUE constraint before the counter moves. The
        counter is then raised by the database itself, so two reports that
        arrive together each add one. Deciding to hide the quiz is issue #15.
        """
        self._session.add(Report(quiz_id=quiz.id, reporter_id=reporter_id))
        self._session.flush()

        quiz.report_count = Quiz.report_count + 1
        self._session.flush()
        return quiz.report_count
