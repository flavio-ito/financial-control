from datetime import date
from pathlib import Path
from contextlib import closing
import json
import sqlite3
import zipfile

import pytest

from app.maintenance.backup import BackupError, create_finbackup, restore_finbackup, validate_finbackup
from app.storage.models import Account


def account_names(database):
    with database.session() as session:
        return [item.name for item in session.query(Account).order_by(Account.name).all()]


def add_account(database, name):
    with database.session() as session:
        session.add(Account(name=name, reference_date=date(2026, 8, 31), reference_balance_minor=10000))


def assert_database_healthy(path: Path):
    with closing(sqlite3.connect(str(path))) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_finbackup_round_trip_and_manifest_privacy(domain_db, tmp_path):
    add_account(domain_db, "Antes")
    archive = tmp_path / "export.finbackup"
    result = create_finbackup(domain_db.path, archive)
    manifest_text = json.dumps(result.manifest)
    assert str(tmp_path) not in manifest_text
    assert "token" not in manifest_text.lower()
    add_account(domain_db, "Depois")
    restored = restore_finbackup(domain_db, archive, domain_db.path.parent)
    assert account_names(domain_db) == ["Antes"]
    assert restored["manifest"]["currency"] == "BRL"
    assert_database_healthy(domain_db.path)
    assert list((domain_db.path.parent / "backups" / "pre-restore").glob("*.finbackup"))


def test_corrupt_or_incompatible_backup_is_rejected_without_touching_current_database(domain_db, tmp_path):
    add_account(domain_db, "Preservada")
    valid = tmp_path / "valid.finbackup"
    create_finbackup(domain_db.path, valid)
    corrupt = tmp_path / "corrupt.finbackup"
    with zipfile.ZipFile(str(valid), "r") as source, zipfile.ZipFile(str(corrupt), "w") as target:
        target.writestr("database.sqlite3", source.read("database.sqlite3") + b"corruption")
        target.writestr("manifest.json", source.read("manifest.json"))
    with pytest.raises(BackupError, match="Checksum"):
        restore_finbackup(domain_db, corrupt, domain_db.path.parent)
    assert account_names(domain_db) == ["Preservada"]

    incompatible = tmp_path / "future.finbackup"
    with zipfile.ZipFile(str(valid), "r") as source, zipfile.ZipFile(str(incompatible), "w") as target:
        manifest = json.loads(source.read("manifest.json").decode("utf-8"))
        manifest["alembic_revision"] = "9999_future"
        target.writestr("database.sqlite3", source.read("database.sqlite3"))
        target.writestr("manifest.json", json.dumps(manifest))
    with pytest.raises(BackupError, match="incompatível"):
        restore_finbackup(domain_db, incompatible, domain_db.path.parent)
    assert account_names(domain_db) == ["Preservada"]


def test_restore_rolls_back_if_failure_happens_after_database_replacement(domain_db, tmp_path):
    add_account(domain_db, "No backup")
    archive = tmp_path / "point.finbackup"
    create_finbackup(domain_db.path, archive)
    add_account(domain_db, "Atual")

    def fail(stage):
        if stage == "replaced":
            raise RuntimeError("falha injetada")

    with pytest.raises(RuntimeError, match="injetada"):
        restore_finbackup(domain_db, archive, domain_db.path.parent, inject_failure=fail)
    assert account_names(domain_db) == ["Atual", "No backup"]
    assert_database_healthy(domain_db.path)


def test_backup_api_requires_preview_and_explicit_confirmation(authenticated):
    client, csrf, _path, _database = authenticated
    headers = {"Origin": "http://127.0.0.1", "X-CSRF-Token": csrf}
    created = client.post("/api/v1/accounts", json={"name": "Original", "reference_date": "2026-08-31", "reference_balance_minor": 1000}, headers=headers)
    assert created.status_code == 200
    exported = client.post("/api/v1/backups/export", headers=headers)
    assert exported.status_code == 200
    assert exported.content.startswith(b"PK")
    client.post("/api/v1/accounts", json={"name": "Posterior", "reference_date": "2026-08-31", "reference_balance_minor": 2000}, headers=headers)

    preview = client.post("/api/v1/backups/restore/preview", files={"backup": ("test.finbackup", exported.content, "application/zip")}, headers=headers)
    assert preview.status_code == 200
    assert "substituirá todos os dados" in preview.json()["warning"]
    before = client.get("/api/v1/accounts").json()["total"]
    assert before == 2
    confirmed = client.post("/api/v1/backups/restore/confirm", json={"restore_token": preview.json()["restore_token"]}, headers=headers)
    assert confirmed.status_code == 200
    assert client.get("/api/v1/accounts").json()["total"] == 1
    reused = client.post("/api/v1/backups/restore/confirm", json={"restore_token": preview.json()["restore_token"]}, headers=headers)
    assert reused.status_code == 422
