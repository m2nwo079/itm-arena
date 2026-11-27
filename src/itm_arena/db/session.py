"""Engine, session factory and table creation.

Only SQLite is set up here, which covers local demo mode and the tests. The
deployed PostgreSQL (Neon) connection is wired up separately in issue #14.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from itm_arena.db.models import Base

IN_MEMORY_URL = "sqlite+pysqlite:///:memory:"


def create_sqlite_engine(url: str = IN_MEMORY_URL, *, echo: bool = False) -> Engine:
    """Create an engine for a SQLite file or an in-memory database."""
    engine = create_engine(url, echo=echo)
    _enable_sqlite_foreign_keys(engine)
    return engine


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """Turn on foreign key checks, which SQLite leaves off by default."""

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_tables(engine: Engine) -> None:
    """Create every table that does not exist yet.

    We have no migration tool: create_all never alters a table that is already
    there, so a change to an existing table needs a reviewed SQL script.
    """
    Base.metadata.create_all(engine)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build the factory every caller uses to open a session.

    expire_on_commit is off so objects stay readable after the transaction
    ends; otherwise every attribute access after a commit would emit a new
    SELECT, and the UI reads rows after the service layer commits.

    In simple words: this only makes sessions. Turning expire_on_commit off
    keeps the loaded data readable after the transaction is over.
    """
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager   # lets this function be used with a "with" block
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Run a block of work in one transaction.

    Repositories only flush, so a quiz and its ten questions, or an attempt
    and its ten answers, are committed together or not at all.

    In simple words: if you stop halfway while writing a quiz or sending
    answers, nothing is left behind. Either all ten questions are saved or
    none of them are. The repositories only flush and never commit, so this
    "with" block commits once when the code ends normally, and rolls back
    when an error happens.
    """
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()