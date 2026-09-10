def test_bootstrap_is_one_shot_and_cookie_is_hardened(app_client):
    client, token, _path, _database = app_client
    first = client.post(
        "/api/v1/session/bootstrap", json={"token": token}, headers={"Origin": "http://127.0.0.1"}
    )
    assert first.status_code == 200
    cookie = first.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    second = client.post(
        "/api/v1/session/bootstrap", json={"token": token}, headers={"Origin": "http://127.0.0.1"}
    )
    assert second.status_code == 401
    assert second.json()["detail"]["code"] == "INVALID_BOOTSTRAP"


def test_reload_gets_csrf_without_persistent_browser_secret(authenticated):
    client, csrf, _path, _database = authenticated
    response = client.get("/api/v1/session/csrf")
    assert response.status_code == 200
    assert response.json()["csrf_token"] == csrf


def test_mutation_requires_session(app_client):
    client, _token, _path, _database = app_client
    assert client.post("/api/v1/application/shutdown").status_code == 401


def test_mutation_requires_origin_and_csrf(authenticated):
    client, csrf, _path, _database = authenticated
    assert client.post("/api/v1/application/shutdown").status_code == 403
    assert client.post(
        "/api/v1/application/shutdown",
        headers={"Origin": "http://evil.example", "X-CSRF-Token": csrf},
    ).status_code == 403
    assert client.post(
        "/api/v1/application/shutdown",
        headers={"Origin": "http://127.0.0.1", "X-CSRF-Token": csrf},
    ).status_code == 202


def test_invalid_host_is_rejected(app_client):
    client, _token, _path, _database = app_client
    response = client.get("/api/v1/health", headers={"Host": "192.168.1.25"})
    assert response.status_code == 400


def test_get_cannot_perform_mutation(authenticated):
    client, _csrf, _path, _database = authenticated
    assert client.get("/api/v1/application/shutdown").status_code in (404, 405)
