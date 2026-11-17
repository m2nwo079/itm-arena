"""Engine, session factory and table creation.

Only SQLite is set up here, which covers local demo mode and the tests. The
deployed PostgreSQL (Neon) connection is wired up separately in issue #14.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from itm_arena.db.models import Base

IN_MEMORY_URL = "sqlite+pysqlite:///:memory:"


def create_sqlite_engine(url: str = IN_MEMORY_URL, *, echo: bool = False) -> Engine:
    """Create an engine for a SQLite file or an in-memory database."""
    options: dict[str, object] = {}
    if ":memory:" in url:
        # Each new connection to :memory: would get its own empty database, so
        # the engine has to hand out one shared connection instead
        options["poolclass"] = StaticPool
        options["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, echo=echo, **options)
    _enable_sqlite_foreign_keys(engine)
    return engine


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """Turn on foreign key checks, which SQLite leaves off by default."""

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_tables(engine: Engine) -> None:
    """Create every table that does not exist yet.

    We have no migration tool: create_all never alters a table that is already
    there, so a change to an existing table needs a reviewed SQL script under
    db/changes/ (see CONTRIBUTING.md).
    """
    Base.metadata.create_all(engine)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Run a block of work in one transaction.

    Repositories only flush, so a quiz and its ten questions, or an attempt and
    its ten answers, are committed together or not at all.
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
