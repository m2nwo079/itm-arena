# SQLAlchemy models

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NICKNAME_MAX_LENGTH = 12


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