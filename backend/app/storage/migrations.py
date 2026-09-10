from pathlib import Path
from datetime import datetime, timezone

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine

from app.maintenance.backup import create_finbackup


def alembic_config(database_path: Path) -> Config:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", "sqlite:///{}".format(database_path.as_posix()))
    return config


def current_revision(database_path: Path):
    if not database_path.exists():
        return None
    engine = create_engine("sqlite:///{}".format(database_path.as_posix()), future=True)
    try:
        with engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()


def head_revision(database_path: Path) -> str:
    config = alembic_config(database_path)
    from alembic.script import ScriptDirectory

    return ScriptDirectory.from_config(config).get_current_head()


def migrate(database_path: Path, pre_migration_directory: Path) -> bool:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    before = current_revision(database_path)
    head = head_revision(database_path)
    if before == head:
        return False
    if database_path.exists() and database_path.stat().st_size:
        pre_migration_directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        target = pre_migration_directory / "database-before-{}-{}.finbackup".format(head, timestamp)
        create_finbackup(database_path, target)
    command.upgrade(alembic_config(database_path), "head")
    return True
