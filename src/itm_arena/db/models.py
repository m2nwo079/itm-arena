"""SQLAlchemy models for ITM Arena.

The rules that keep the game fair are expressed as database constraints, not
only as checks in Python, so that two simultaneous requests cannot both
succeed:

- one quiz per user          -> UNIQUE (quizzes.owner_id)
- ten questions in order     -> UNIQUE (questions.quiz_id, position)
- one attempt per player     -> UNIQUE (attempts.quiz_id, solver_id)
- one answer per question    -> UNIQUE (attempt_answers.attempt_id, question_id)
- no duplicate reports       -> UNIQUE (reports.quiz_id, reporter_id)
- unique nicknames           -> UNIQUE (users.nickname_key)

Index conventions follow the shared types in itm_arena.domain.types:
`position` is one-based (1 to 10) and `answer_index` / `selected_index` are
zero-based (0 to 3).
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Question and choice counts are fixed for every quiz
QUESTION_COUNT = 10
CHOICE_COUNT = 4

# Column widths come from the input rules in issue #3
NICKNAME_MAX_LENGTH = 12
QUESTION_TEXT_MAX_LENGTH = 100
CHOICE_MAX_LENGTH = 50
TITLE_MAX_LENGTH = 64


def utcnow() -> datetime:
    """Current time in UTC.

    SQLite has no timezone-aware column type and returns naive datetimes, so
    every stored timestamp is UTC by convention and must be read as UTC.
    """
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # Nicknames are unique and cannot be changed
        UniqueConstraint("nickname_key", name="uq_users_nickname_key"),
        CheckConstraint(
            "failed_attempts >= 0", name="ck_users_failed_attempts_non_negative"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # The nickname as the user typed it, shown in lists and rankings
    nickname: Mapped[str] = mapped_column(String(NICKNAME_MAX_LENGTH), nullable=False)
    # Normalised form of the nickname, used for the uniqueness check
    nickname_key: Mapped[str] = mapped_column(
        String(NICKNAME_MAX_LENGTH), nullable=False
    )
    # PBKDF2 hash of the PIN and its per-user salt, both hex encoded
    pin_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    pin_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    # Consecutive failed logins; reset to 0 on a successful login
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Locked out until this time; NULL means not locked
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    quiz: Mapped["Quiz | None"] = relationship(back_populates="owner")


class Quiz(Base):
    __tablename__ = "quizzes"
    __table_args__ = (
        # One quiz per user, including a quiz the owner has hidden
        UniqueConstraint("owner_id", name="uq_quizzes_owner_id"),
        CheckConstraint(
            "report_count >= 0", name="ck_quizzes_report_count_non_negative"
        ),
        # The quiz list is newest first
        Index("ix_quizzes_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    # Always "<nickname>'s quiz"; nobody can publish a quiz about someone else
    title: Mapped[str] = mapped_column(String(TITLE_MAX_LENGTH), nullable=False)
    # Kept alongside the reports table so the list does not have to count rows
    report_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Hidden by its owner, who can also show it again
    hidden_by_owner: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # Hidden after three reports; the owner cannot undo this one
    hidden_by_reports: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    owner: Mapped["User"] = relationship(back_populates="quiz")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="quiz", order_by="Question.position"
    )

    @property
    def is_visible(self) -> bool:
        """A quiz is visible only when neither kind of hiding applies."""
        return not self.hidden_by_owner and not self.hidden_by_reports


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        # Exactly one question per position, so the ten positions cannot clash
        UniqueConstraint("quiz_id", "position", name="uq_questions_quiz_id_position"),
        CheckConstraint(
            f"position >= 1 AND position <= {QUESTION_COUNT}",
            name="ck_questions_position_range",
        ),
        CheckConstraint(
            f"answer_index >= 0 AND answer_index <= {CHOICE_COUNT - 1}",
            name="ck_questions_answer_index_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id"), nullable=False)
    # One-based position, 1 to 10
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(String(QUESTION_TEXT_MAX_LENGTH), nullable=False)
    choice_1: Mapped[str] = mapped_column(String(CHOICE_MAX_LENGTH), nullable=False)
    choice_2: Mapped[str] = mapped_column(String(CHOICE_MAX_LENGTH), nullable=False)
    choice_3: Mapped[str] = mapped_column(String(CHOICE_MAX_LENGTH), nullable=False)
    choice_4: Mapped[str] = mapped_column(String(CHOICE_MAX_LENGTH), nullable=False)
    # Zero-based index of the correct choice, 0 to 3. Never sent to a player
    # before they submit.
    answer_index: Mapped[int] = mapped_column(Integer, nullable=False)

    quiz: Mapped["Quiz"] = relationship(back_populates="questions")

    @property
    def choices(self) -> list[str]:
        """The four choices in display order."""
        return [self.choice_1, self.choice_2, self.choice_3, self.choice_4]


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (
        # One attempt per player per quiz
        UniqueConstraint("quiz_id", "solver_id", name="uq_attempts_quiz_id_solver_id"),
        CheckConstraint(
            f"score >= 0 AND score <= {QUESTION_COUNT}", name="ck_attempts_score_range"
        ),
        # "Quizzes I have already solved" in the quiz list
        Index("ix_attempts_solver_id", "solver_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id"), nullable=False)
    solver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    # Number of correct answers, 0 to 10
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    solver: Mapped["User"] = relationship()
    answers: Mapped[list["AttemptAnswer"]] = relationship(back_populates="attempt")


class AttemptAnswer(Base):
    __tablename__ = "attempt_answers"
    __table_args__ = (
        # One answer per question within an attempt
        UniqueConstraint(
            "attempt_id",
            "question_id",
            name="uq_attempt_answers_attempt_id_question_id",
        ),
        CheckConstraint(
            f"selected_index >= 0 AND selected_index <= {CHOICE_COUNT - 1}",
            name="ck_attempt_answers_selected_index_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    # Zero-based index the player chose, 0 to 3
    selected_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # Stored so the result screen stays correct even if grading changes later
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)

    attempt: Mapped["Attempt"] = relationship(back_populates="answers")


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        # The same person cannot report the same quiz twice
        UniqueConstraint(
            "quiz_id", "reporter_id", name="uq_reports_quiz_id_reporter_id"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id"), nullable=False)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
