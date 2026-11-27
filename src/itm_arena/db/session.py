"""Engine, session factory and table creation.

Only SQLite is set up here, which covers local demo mode and the tests. The
deployed PostgreSQL (Neon) connection is wired up separately in issue #14.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from itm_arena.db.models import Base

IN_MEMORY_URL = "sqlite+pysqlite:///:memory:"


def create_sqlite_engine(url: str = IN_MEMORY_URL, *, echo: bool = False) -> Engine:
    """Create an engine for a SQLite file or an in-memory database."""
    return create_engine(url, echo=echo)


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

    그냥 세션 찍어내는 함수. 트랜잭션 끝나도 데이터 접근할 수 있게 expire_on_commit 을 False 로
    """
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager   # <- 이 함수를 with 로 쓸 수 있게 만들어줌.
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Run a block of work in one transaction.

    Repositories only flush, so a quiz and its ten questions, or an attempt
    and its ten answers, are committed together or not at all.

    즉, 문제 만드는 도중, 문제 답 제출하는 도중에 그만두어도 남는 게 없도록 만드는 거?
    10문제가 전부 다 통과되거나 하나도 안 되거나 둘 중 하나로만 동작해야 함.
    레포지토리에서는 flush 만 하고 commit 을 안 함. 그래서 여기서 with 블록 이용 -> 정상 종료면 commit 한 번
    예외 나면 rollback 하는 방식으로 작동.
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