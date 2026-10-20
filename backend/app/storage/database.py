from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# FastAPI may enter and finalize a synchronous yield dependency on different
# worker threads.  A Lock can be released by the finalizer in that situation;
# an RLock is owned by the acquiring thread and can leave every later write
# waiting forever.
financial_write_lock = Lock()


def create_sqlite_engine(database_path: Path) -> Engine:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        "sqlite:///{}".format(database_path.as_posix()),
        connect_args={"check_same_thread": False, "timeout": 5},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection, _connection_record):  # type: ignore
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


class Database:
    def __init__(self, database_path: Path):
        self.path = database_path
        self.engine = create_sqlite_engine(database_path)
        self.session_factory = sessionmaker(
            bind=self.engine, autocommit=False, autoflush=False, expire_on_commit=False
        )

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        db = self.session_factory()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def dispose(self) -> None:
        self.engine.dispose()

