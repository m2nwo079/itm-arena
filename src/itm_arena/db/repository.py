"""Repositories: the only place that talks to the database.

These read and write rows and nothing else. Who may solve a quiz, when an
account is locked, and when three reports hide a quiz are service-level rules
(issues #5, #7 and #15), not repository rules.

Repositories flush but never commit, so a caller can wrap several calls in one
transaction with session_scope.
"""

from collections.abc import Mapping, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from itm_arena.db.models import Attempt, AttemptAnswer, Question, Quiz, Report, User
from itm_arena.domain.types import AnswerKey, QuestionView, QuizDraft, SubmittedAnswer


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: int) -> User | None:
        return self._session.get(User, user_id)

    def get_by_nickname_key(self, nickname_key: str) -> User | None:
        """Look a user up by the normalised nickname used for uniqueness."""
        return self._session.scalar(
            select(User).where(User.nickname_key == nickname_key)
        )

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

    def set_login_state(self, user: User, *, failed_attempts: int, locked_until) -> None:
        """Store the result of a login attempt; the policy lives in #5."""
        user.failed_attempts = failed_attempts
        user.locked_until = locked_until
        self._session.flush()


class QuizRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, quiz_id: int) -> Quiz | None:
        return self._session.get(Quiz, quiz_id)

    def get_by_owner(self, owner_id: int) -> Quiz | None:
        """The owner's only quiz, hidden or not, or None if they have none."""
        return self._session.scalar(select(Quiz).where(Quiz.owner_id == owner_id))

    def list_visible(self) -> list[Quiz]:
        """Visible quizzes, newest first."""
        statement = (
            select(Quiz)
            .where(Quiz.hidden_by_owner.is_(False), Quiz.hidden_by_reports.is_(False))
            .order_by(Quiz.created_at.desc(), Quiz.id.desc())
        )
        return list(self._session.scalars(statement))

    def create_with_questions(
        self, *, owner_id: int, title: str, draft: QuizDraft
    ) -> Quiz:
        """Save a quiz and all of its questions as one unit of work.

        Positions are assigned from the order of the draft, starting at 1. The
        draft is expected to be valid already; validation is issue #3.
        """
        quiz = Quiz(owner_id=owner_id, title=title)
        self._session.add(quiz)
        for position, question in enumerate(draft.questions, start=1):
            first, second, third, fourth = question.choices
            self._session.add(
                Question(
                    quiz=quiz,
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

    def list_questions(self, quiz_id: int) -> list[Question]:
        statement = (
            select(Question)
            .where(Question.quiz_id == quiz_id)
            .order_by(Question.position)
        )
        return list(self._session.scalars(statement))

    def list_question_views(self, quiz_id: int) -> list[QuestionView]:
        """Questions as the solver sees them, without the correct answers."""
        return [
            QuestionView(
                question_id=question.id,
                position=question.position,
                text=question.text,
                choices=question.choices,
            )
            for question in self.list_questions(quiz_id)
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

    def set_hidden_by_owner(self, quiz: Quiz, hidden: bool) -> None:
        quiz.hidden_by_owner = hidden
        self._session.flush()

    def set_hidden_by_reports(self, quiz: Quiz, hidden: bool) -> None:
        """Hide a reported quiz. Its owner cannot undo this (#15)."""
        quiz.hidden_by_reports = hidden
        self._session.flush()


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
        return self.get_for_solver(quiz_id, solver_id) is not None

    def add_with_answers(
        self,
        *,
        quiz_id: int,
        solver_id: int,
        score: int,
        answers: Sequence[SubmittedAnswer],
        correct_by_question: Mapping[int, bool],
    ) -> Attempt:
        """Save an attempt and its answers as one unit of work.

        `score` and `correct_by_question` come from grading (#4); the unique
        constraint on (quiz_id, solver_id) is what actually stops a second
        attempt, even if two submissions arrive at the same time.
        """
        attempt = Attempt(quiz_id=quiz_id, solver_id=solver_id, score=score)
        self._session.add(attempt)
        for answer in answers:
            self._session.add(
                AttemptAnswer(
                    attempt=attempt,
                    question_id=answer.question_id,
                    selected_index=answer.selected_index,
                    is_correct=correct_by_question[answer.question_id],
                )
            )
        self._session.flush()
        return attempt

    def list_answers(self, attempt_id: int) -> list[AttemptAnswer]:
        """Stored answers for the result screen (#12)."""
        statement = (
            select(AttemptAnswer)
            .join(Question, Question.id == AttemptAnswer.question_id)
            .where(AttemptAnswer.attempt_id == attempt_id)
            .order_by(Question.position)
        )
        return list(self._session.scalars(statement))

    def list_scores(self, quiz_id: int) -> list[tuple[str, int]]:
        """(nickname, score) pairs for one quiz, ready for ranking (#6)."""
        statement = (
            select(User.nickname, Attempt.score)
            .join(User, User.id == Attempt.solver_id)
            .where(Attempt.quiz_id == quiz_id)
        )
        return [(nickname, score) for nickname, score in self._session.execute(statement).all()]

    def list_solved_quiz_ids(self, solver_id: int) -> set[int]:
        """Quizzes this user has already solved, marked in the list (#10)."""
        statement = select(Attempt.quiz_id).where(Attempt.solver_id == solver_id)
        return set(self._session.scalars(statement))


class ReportRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def exists(self, quiz_id: int, reporter_id: int) -> bool:
        statement = select(Report.id).where(
            Report.quiz_id == quiz_id, Report.reporter_id == reporter_id
        )
        return self._session.scalar(statement) is not None

    def count(self, quiz_id: int) -> int:
        statement = select(func.count(Report.id)).where(Report.quiz_id == quiz_id)
        return self._session.scalar(statement) or 0

    def add(self, *, quiz: Quiz, reporter_id: int) -> int:
        """Record one report and return the quiz's new report count.

        The unique constraint on (quiz_id, reporter_id) rejects a second report
        from the same person. Deciding to hide the quiz is issue #15.
        """
        self._session.add(Report(quiz_id=quiz.id, reporter_id=reporter_id))
        self._session.flush()
        quiz.report_count = self.count(quiz.id)
        self._session.flush()
        return quiz.report_count
