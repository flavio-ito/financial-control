from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Callable, Dict, Optional
import hashlib
import json
import os
import sqlite3
import tempfile
import uuid
import zipfile

from app import __version__
from app.config import DEFAULT_CURRENCY

BACKUP_FORMAT_VERSION = 1


class BackupError(ValueError):
    pass


class MaintenanceGate:
    def __init__(self):
        self.lock = RLock()
        self.active = False


@dataclass(frozen=True)
class ValidatedBackup:
    path: Path
    manifest: Dict[str, object]


def database_revision(database_path: Path) -> str:
    with sqlite3.connect(str(database_path)) as connection:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        return str(row[0]) if row else "base"


def sqlite_snapshot(database_path: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(database_path)) as source, sqlite3.connect(str(destination)) as target:
        source.backup(target)
    return destination


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_finbackup(database_path: Path, destination: Path, app_version: str = __version__) -> ValidatedBackup:
    if destination.suffix.lower() != ".finbackup":
        raise BackupError("O destino deve usar a extensão .finbackup.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(destination.parent)) as temporary_name:
        temporary = Path(temporary_name)
        snapshot = sqlite_snapshot(database_path, temporary / "database.sqlite3")
        manifest = {
            "backup_format_version": BACKUP_FORMAT_VERSION,
            "app_version": app_version,
            "alembic_revision": database_revision(snapshot),
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "currency": DEFAULT_CURRENCY,
            "database_sha256": sha256_file(snapshot),
        }
        archive_tmp = destination.parent / (".{}.{}.tmp".format(destination.name, uuid.uuid4().hex))
        try:
            with zipfile.ZipFile(str(archive_tmp), "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(str(snapshot), "database.sqlite3")
                archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
            validate_finbackup(archive_tmp, expected_revision=manifest["alembic_revision"])
            os.replace(str(archive_tmp), str(destination))
        finally:
            if archive_tmp.exists():
                archive_tmp.unlink()
    _record_backup_success(database_path, destination.name, manifest)
    return ValidatedBackup(destination, manifest)


def _record_backup_success(database_path: Path, destination_name: str, manifest: Dict[str, object]) -> None:
    """Record only promoted/validated backups; old schemas may not have the table yet."""
    with sqlite3.connect(str(database_path)) as connection:
        exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='backup_runs'").fetchone()
        if not exists:
            return
        connection.execute(
            "INSERT INTO backup_runs(id,created_at,destination,status,checksum,app_version,alembic_revision,backup_format_version,error_message) VALUES (?,?,?,?,?,?,?,?,NULL)",
            (
                str(uuid.uuid4()),
                datetime.now(timezone.utc).isoformat(),
                destination_name,
                "succeeded",
                manifest["database_sha256"],
                manifest["app_version"],
                manifest["alembic_revision"],
                manifest["backup_format_version"],
            ),
        )


def validate_finbackup(path: Path, expected_revision: Optional[str] = None) -> ValidatedBackup:
    if path.suffix.lower() not in (".finbackup", ".tmp"):
        raise BackupError("Arquivo deve usar a extensão .finbackup.")
    try:
        with zipfile.ZipFile(str(path), "r") as archive:
            names = set(archive.namelist())
            if names != {"database.sqlite3", "manifest.json"}:
                raise BackupError("Conteúdo do backup é inválido.")
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            database_bytes = archive.read("database.sqlite3")
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BackupError("Arquivo de backup corrompido ou ilegível.") from error
    required = {"backup_format_version", "app_version", "alembic_revision", "created_at_utc", "currency", "database_sha256"}
    if not required.issubset(manifest):
        raise BackupError("Manifesto de backup incompleto.")
    if manifest["backup_format_version"] != BACKUP_FORMAT_VERSION or manifest["currency"] != DEFAULT_CURRENCY:
        raise BackupError("Formato ou moeda do backup incompatível.")
    if hashlib.sha256(database_bytes).hexdigest() != manifest["database_sha256"]:
        raise BackupError("Checksum SHA-256 do backup não confere.")
    if expected_revision is not None and manifest["alembic_revision"] != expected_revision:
        raise BackupError("Versão de banco incompatível; use uma versão compatível do aplicativo.")
    return ValidatedBackup(path, manifest)


def verify_database(database_path: Path, expected_revision: str) -> None:
    try:
        with sqlite3.connect(str(database_path)) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            foreign_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
            revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    except sqlite3.Error as error:
        raise BackupError("Banco candidato não pôde ser validado.") from error
    if not integrity or integrity[0] != "ok" or foreign_errors:
        raise BackupError("Banco candidato falhou em integrity_check/foreign_key_check.")
    if not revision or revision[0] != expected_revision:
        raise BackupError("Revision Alembic do banco candidato é incompatível.")


def ensure_daily_backup(database_path: Path, backup_directory: Path) -> ValidatedBackup:
    backup_directory.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).date().isoformat()
    destination = backup_directory / "daily-{}.finbackup".format(today)
    result = validate_finbackup(destination, database_revision(database_path)) if destination.exists() else create_finbackup(database_path, destination)
    daily = sorted(backup_directory.glob("daily-*.finbackup"), reverse=True)
    for expired in daily[30:]:
        expired.unlink()
    return result


def restore_finbackup(database, backup_path: Path, data_directory: Path, inject_failure: Optional[Callable[[str], None]] = None) -> Dict[str, object]:
    current_revision = database_revision(database.path)
    validated = validate_finbackup(backup_path, expected_revision=current_revision)
    recovery_dir = data_directory / "backups" / "pre-restore"
    recovery_dir.mkdir(parents=True, exist_ok=True)
    safety = recovery_dir / "before-restore-{}.finbackup".format(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    create_finbackup(database.path, safety)
    previous = data_directory / (".database-before-restore-{}.sqlite3".format(uuid.uuid4().hex))
    candidate = data_directory / (".database-candidate-{}.sqlite3".format(uuid.uuid4().hex))
    replaced = False
    try:
        with zipfile.ZipFile(str(backup_path), "r") as archive:
            with candidate.open("wb") as stream:
                stream.write(archive.read("database.sqlite3"))
        verify_database(candidate, current_revision)
        if inject_failure:
            inject_failure("validated")
        database.dispose()
        os.replace(str(database.path), str(previous))
        replaced = True
        os.replace(str(candidate), str(database.path))
        if inject_failure:
            inject_failure("replaced")
        verify_database(database.path, current_revision)
        with database.engine.connect() as connection:
            if connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() != 1:
                raise BackupError("Foreign keys não foram reativadas.")
        previous.unlink()
        return {"manifest": validated.manifest, "safety_backup": safety.name}
    except Exception:
        database.dispose()
        if replaced and previous.exists():
            if database.path.exists():
                failed = data_directory / (".failed-restore-{}.sqlite3".format(uuid.uuid4().hex))
                os.replace(str(database.path), str(failed))
            os.replace(str(previous), str(database.path))
            verify_database(database.path, current_revision)
        raise
    finally:
        if candidate.exists():
            candidate.unlink()
