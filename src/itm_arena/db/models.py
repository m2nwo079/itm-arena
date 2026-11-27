# SQLAlchemy models

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Integer, String, UniqueConstraint, Boolean, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NICKNAME_MAX_LENGTH = 12   # User
TITLE_MAX_LENGTH = 64   # Quiz


def utcnow() -> datetime:
    """
    Every stored timestamp is UTC by convention, so SQLite and PostgreSQL
    both hand back values that can be compared without converting.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("nickname_key", name="uq_users_nickname_key"),
        CheckConstraint("failed_attempts >= 0", name="ck_users_failed_attempts_non_negative"),
    )

    # id = PK
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # as user typed, for display.
    nickname: Mapped[str] = mapped_column(String(NICKNAME_MAX_LENGTH), nullable=False)
    # Normalised form, used only for the uniqueness check
    nickname_key: Mapped[str] = mapped_column(String(NICKNAME_MAX_LENGTH), nullable=False)
    
    
    ### handled in issue 5
    pin_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    pin_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    # how many fails occured
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # if fail so many time, locked
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )

    TITLE_MAX_LENGTH = 64


class Quiz(Base):
    __tablename__ = "quizzes"
    __table_args__ = (
        # One quiz per user, including a quiz the owner has hidden
        UniqueConstraint("owner_id", name="uq_quizzes_owner_id"),
        CheckConstraint(
            "report_count >= 0", name="ck_quizzes_report_count_non_negative"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # The quiz belongs to the user who wrote it and cannot be reassigned
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    # Always "<nickname>'s quiz", built by the service when the quiz is created
    title: Mapped[str] = mapped_column(String(TITLE_MAX_LENGTH), nullable=False)
    
    report_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Hidden by its owner, who can also show it again
    hidden_by_owner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Hidden after three reports; the owner cannot undo this one
    hidden_by_reports: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )

    @property
    def is_visible(self) -> bool:
        """A quiz is visible only when neither kind of hiding applies."""
        return not self.hidden_by_owner and not self.hidden_by_reports