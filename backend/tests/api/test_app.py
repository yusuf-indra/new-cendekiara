"""The API: discovery, running commands, the errors and the cache headers."""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from cendekiara.api.app import cache_control, create_app
from cendekiara.core.config import Settings
from cendekiara.core.registry import get
from cendekiara.core.store import MemoryStore

STUDENT = {"Authorization": "Bearer dev:u-siti"}
ADMIN = {"Authorization": "Bearer dev:admin"}


def test_discovery_is_public_and_lists_the_public_commands(api_client: TestClient) -> None:
    response = api_client.get("/api/commands")
    assert response.status_code == 200
    names = [entry["name"] for entry in response.json()]
    assert "system.health" in names
    assert "user.me" not in names  # a command that needs a login
    assert "token.create" not in names  # an admin command


def test_discovery_for_a_signed_in_user_has_no_admin_commands(api_client: TestClient) -> None:
    response = api_client.get("/api/commands", headers=STUDENT)
    names = [entry["name"] for entry in response.json()]
    assert "user.me" in names
    assert "token.create" not in names


def test_discovery_for_an_admin_has_the_admin_commands(api_client: TestClient) -> None:
    response = api_client.get("/api/commands", headers=ADMIN)
    names = [entry["name"] for entry in response.json()]
    assert "token.create" in names
    assert "token.revoke" in names


def test_post_runs_a_public_command(api_client: TestClient) -> None:
    response = api_client.post("/api/commands/system.health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_post_runs_a_command_of_a_signed_in_user(api_client: TestClient) -> None:
    response = api_client.post("/api/commands/user.me", headers=STUDENT)
    assert response.status_code == 200
    assert response.json()["uid"] == "u-siti"


def test_post_without_a_token_needs_a_login(api_client: TestClient) -> None:
    response = api_client.post("/api/commands/user.me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "login_required"


def test_post_with_a_broken_token_is_invalid_token(api_client: TestClient) -> None:
    response = api_client.post("/api/commands/user.me", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_post_of_an_unknown_command_is_not_found(api_client: TestClient) -> None:
    response = api_client.post("/api/commands/nope.nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "unknown_command"


def test_post_with_a_wrong_argument_is_invalid_args(api_client: TestClient) -> None:
    response = api_client.post("/api/commands/user.set_language", headers=STUDENT, json={"lang": "fr"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_args"


def test_post_with_an_unknown_argument_is_invalid_args(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/commands/user.set_language", headers=STUDENT, json={"lang": "en", "x": 1}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_args"


def test_post_with_a_broken_body_is_invalid_args(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/commands/system.health",
        headers={**STUDENT, "Content-Type": "application/json"},
        content=b"{not json",
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_args"


def test_get_serves_a_readonly_command(api_client: TestClient) -> None:
    response = api_client.get("/api/commands/system.health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_get_of_a_write_command_is_method_not_allowed(api_client: TestClient) -> None:
    response = api_client.get("/api/commands/user.set_language", headers=STUDENT)
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


def test_get_of_an_unknown_command_is_not_found(api_client: TestClient) -> None:
    response = api_client.get("/api/commands/nope.nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "unknown_command"


def test_an_admin_command_looks_absent_to_a_user(api_client: TestClient) -> None:
    response = api_client.post("/api/commands/token.create", headers=STUDENT, json={"label": "laptop"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "admin_only"


def test_an_admin_command_works_for_an_admin(api_client: TestClient) -> None:
    response = api_client.post("/api/commands/token.create", headers=ADMIN, json={"label": "laptop"})
    assert response.status_code == 200
    assert response.json()["token"].startswith("ck_")


def test_the_error_body_has_the_documented_shape(api_client: TestClient) -> None:
    response = api_client.post("/api/commands/nope.nope")
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "hint"}


def test_an_api_token_acts_as_the_admin_who_created_it(api_client: TestClient, mem: MemoryStore) -> None:
    mem.set("users", "admin", {"uid": "admin", "email": "admin@example.com"})
    created = api_client.post("/api/commands/token.create", headers=ADMIN, json={"label": "laptop"})
    token = created.json()["token"]
    response = api_client.get("/api/commands/user.me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["uid"] == "admin"


def test_an_api_token_may_not_create_a_token(api_client: TestClient) -> None:
    created = api_client.post("/api/commands/token.create", headers=ADMIN, json={"label": "laptop"})
    token = created.json()["token"]
    response = api_client.post(
        "/api/commands/token.create",
        headers={"Authorization": f"Bearer {token}"},
        json={"label": "other"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_args"


def test_an_api_token_may_not_revoke_a_token(api_client: TestClient) -> None:
    created = api_client.post("/api/commands/token.create", headers=ADMIN, json={"label": "laptop"})
    data = created.json()
    response = api_client.post(
        "/api/commands/token.revoke",
        headers={"Authorization": f"Bearer {data['token']}"},
        json={"id": data["id"]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_args"


def test_a_revoked_api_token_does_not_work_anymore(api_client: TestClient) -> None:
    created = api_client.post("/api/commands/token.create", headers=ADMIN, json={"label": "laptop"})
    data = created.json()
    api_client.post("/api/commands/token.revoke", headers=ADMIN, json={"id": data["id"]})
    response = api_client.get("/api/commands", headers={"Authorization": f"Bearer {data['token']}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_user_data_is_never_cached(api_client: TestClient) -> None:
    response = api_client.get("/api/commands/user.me", headers=STUDENT)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "Authorization" in response.headers["vary"]


def test_the_health_check_is_never_cached(api_client: TestClient) -> None:
    response = api_client.get("/api/commands/system.health")
    assert response.headers["cache-control"] == "no-store"


def test_a_public_command_may_be_cached() -> None:
    info = replace(get("system.health"), cache_seconds=60)
    assert cache_control(info) == "public, max-age=60"


def test_a_command_of_a_user_is_never_cached() -> None:
    info = replace(get("user.me"), cache_seconds=60)
    assert cache_control(info) == "no-store"


def test_the_api_refuses_to_start_without_an_explicit_app_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    settings = Settings(_env_file=None)  # APP_ENV is not set: the default is used
    assert settings.app_env_explicit is False
    with pytest.raises(RuntimeError, match="APP_ENV"):
        create_app(settings=settings)
