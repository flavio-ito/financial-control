import sqlite3
from threading import Thread

from sqlalchemy import text

from app.config import APP_ID, data_directory
from app.storage.database import Database, financial_write_lock
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


def test_financial_write_lock_can_be_finalized_on_another_worker_thread():
    acquired = []
    released = []

    acquire_thread = Thread(target=lambda: (financial_write_lock.acquire(), acquired.append(True)))
    acquire_thread.start()
    acquire_thread.join(timeout=1)

    release_thread = Thread(target=lambda: (financial_write_lock.release(), released.append(True)))
    release_thread.start()
    release_thread.join(timeout=1)

    assert acquired == [True]
    assert released == [True]
    assert not financial_write_lock.locked()


def test_spa_fallback_never_captures_api(app_client):
    client, _token, _path, _database = app_client
    assert client.get("/movimentacoes/2026-09").text == "<html>SPA</html>"
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert "SPA" not in response.text


def test_root_logo_is_served_as_png_instead_of_spa_fallback(app_client):
    client, _token, _path, _database = app_client
    static_dir = client.app.state.data_directory.parent / "static"
    # The fixture's configured static directory is a sibling of the data directory.
    (static_dir / "capy_logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    response = client.get("/capy_logo.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == b"\x89PNG\r\n\x1a\n"


def test_database_passes_integrity_checks(app_client):
    _client, _token, path, _database = app_client
    with sqlite3.connect(str(path)) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
