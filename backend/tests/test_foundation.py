import sqlite3

from sqlalchemy import text

from app.config import APP_ID, data_directory
from app.storage.database import Database
from app.storage.migrations import current_revision, head_revision, migrate


def test_app_id_and_explicit_data_directory(tmp_path):
    target = data_directory(str(tmp_path / "outside-repository"))
    assert APP_ID == "br.com.local.financas"
    assert target == (tmp_path / "outside-repository").resolve()


def test_migration_is_idempotent_and_persists_after_restart(tmp_path):
    path = tmp_path / "database.sqlite3"
    assert migrate(path, tmp_path / "backups") is True
    first = Database(path)
    with first.session() as session:
        session.execute(
            text("INSERT INTO settings(locale,currency,timezone,setup_step,revision) VALUES ('pt-BR','BRL','America/Sao_Paulo',2,1)")
        )
    first.dispose()

    assert migrate(path, tmp_path / "backups") is False
    reopened = Database(path)
    with reopened.session() as session:
        assert session.execute(text("SELECT setup_step FROM settings")).scalar_one() == 2
        assert session.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        assert session.execute(text("PRAGMA busy_timeout")).scalar_one() == 5000
    reopened.dispose()
    assert current_revision(path) == head_revision(path)


def test_foreign_keys_are_enabled_on_every_connection(tmp_path):
    database = Database(tmp_path / "database.sqlite3")
    with database.engine.connect() as first, database.engine.connect() as second:
        assert first.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        assert second.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    database.dispose()


def test_spa_fallback_never_captures_api(app_client):
    client, _token, _path, _database = app_client
    assert client.get("/planejamento/2026-09").text == "<html>SPA</html>"
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert "SPA" not in response.text


def test_database_passes_integrity_checks(app_client):
    _client, _token, path, _database = app_client
    with sqlite3.connect(str(path)) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
