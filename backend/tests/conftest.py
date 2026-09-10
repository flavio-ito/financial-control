from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.security import SessionSecurity
from app.main import create_app
from app.storage.database import Database
from app.storage.migrations import migrate


@pytest.fixture
def app_client(tmp_path):
    database_path = tmp_path / "data" / "database.sqlite3"
    migrate(database_path, tmp_path / "pre-migration")
    database = Database(database_path)
    security = SessionSecurity()
    token = security.issue_bootstrap()
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html>SPA</html>", encoding="utf-8")
    app = create_app(database=database, security=security, static_directory=static_dir)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield client, token, database_path, database
    database.dispose()


@pytest.fixture
def authenticated(app_client):
    client, token, database_path, database = app_client
    response = client.post(
        "/api/v1/session/bootstrap",
        json={"token": token},
        headers={"Origin": "http://127.0.0.1"},
    )
    assert response.status_code == 200
    return client, response.json()["csrf_token"], database_path, database


@pytest.fixture
def domain_db(tmp_path):
    path = tmp_path / "database.sqlite3"
    migrate(path, tmp_path / "backups")
    database = Database(path)
    yield database
    database.dispose()
