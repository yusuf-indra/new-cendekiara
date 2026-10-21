"""The CLI: the discovery payload, running a command, errors as JSON on stderr."""

from __future__ import annotations

import json

import httpx
import pytest
from typer.testing import CliRunner

from cendekiara.cli import app, decode_arg_value
from cendekiara.core import config, remote

runner = CliRunner()

DISCOVERY_KEYS = {
    "name",
    "summary",
    "queued",
    "adminOnly",
    "allowJobs",
    "readonly",
    "public",
    "inputSchema",
    "outputSchema",
}


def test_commands_list_json_is_the_discovery_payload() -> None:
    result = runner.invoke(app, ["commands", "list", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert "system.health" in [entry["name"] for entry in payload]
    for entry in payload:
        assert set(entry) == DISCOVERY_KEYS


def test_commands_list_text_names_the_commands() -> None:
    result = runner.invoke(app, ["commands", "list"])
    assert result.exit_code == 0
    assert "system.health" in result.stdout


def test_run_prints_the_result_on_stdout() -> None:
    result = runner.invoke(app, ["run", "system.health"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["version"]
    assert "error" not in payload


def test_run_unknown_command_is_an_error_on_stderr() -> None:
    result = runner.invoke(app, ["run", "nope.nope"])
    assert result.exit_code == 1
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "unknown_command"


def test_run_invalid_args_is_an_error_on_stderr() -> None:
    result = runner.invoke(app, ["run", "user.set_language", "--arg", "lang=fr"])
    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "invalid_args"


def test_run_takes_a_valid_arg() -> None:
    # "en" passes validation, so the command fails later, on the missing profile.
    result = runner.invoke(app, ["run", "user.set_language", "--arg", "lang=en"])
    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "not_found"


def test_run_rejects_a_bad_arg_format() -> None:
    result = runner.invoke(app, ["run", "system.health", "--arg", "nonsense"])
    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "invalid_args"


def test_arg_values_are_decoded_as_json_when_possible() -> None:
    assert decode_arg_value("3") == 3
    assert decode_arg_value("true") is True
    assert decode_arg_value("[1, 2]") == [1, 2]
    assert decode_arg_value("en") == "en"
    assert decode_arg_value("") == ""


def _mock_client(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    """The CLI talks to the server through this client."""
    client = httpx.Client(transport=handler)
    monkeypatch.setattr(remote, "make_client", lambda *args, **kwargs: client)


def test_run_remote_calls_the_api(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization", "")
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"ok": True, "version": "0.1.0"})

    _mock_client(monkeypatch, httpx.MockTransport(handler))
    monkeypatch.setenv("CENDEKIARA_TOKEN", "ck_a_token")
    result = runner.invoke(app, ["run", "system.health", "--remote", "https://cendekiara.test"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert seen["url"] == "https://cendekiara.test/api/commands/system.health"
    assert seen["auth"] == "Bearer ck_a_token"
    assert seen["body"] == "{}"


def test_run_remote_sends_the_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"lang": "en"})

    _mock_client(monkeypatch, httpx.MockTransport(handler))
    monkeypatch.setenv("CENDEKIARA_TOKEN", "ck_a_token")
    result = runner.invoke(
        app, ["run", "user.set_language", "--arg", "lang=en", "--remote", "https://cendekiara.test"]
    )
    assert result.exit_code == 0
    assert json.loads(seen["body"]) == {"lang": "en"}


def test_run_remote_without_a_token_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CENDEKIARA_TOKEN", raising=False)
    result = runner.invoke(app, ["run", "system.health", "--remote", "https://cendekiara.test"])
    assert result.exit_code == 1
    assert "CENDEKIARA_TOKEN" in result.stderr


def test_run_remote_reports_the_error_of_the_server(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={"error": {"code": "unknown_command", "message": "No command named 'nope'", "hint": None}},
        )

    _mock_client(monkeypatch, httpx.MockTransport(handler))
    monkeypatch.setenv("CENDEKIARA_TOKEN", "ck_a_token")
    result = runner.invoke(app, ["run", "nope.nope", "--remote", "https://cendekiara.test"])
    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "unknown_command"


def test_run_remote_reports_a_transport_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    _mock_client(monkeypatch, httpx.MockTransport(handler))
    monkeypatch.setenv("CENDEKIARA_TOKEN", "ck_a_token")
    result = runner.invoke(app, ["run", "system.health", "--remote", "https://cendekiara.test"])
    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "remote_error"


def test_run_remote_needs_no_local_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    """The remote CLI has no store and no auth mode: only a token and a URL."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    _mock_client(monkeypatch, httpx.MockTransport(handler))
    monkeypatch.setenv("CENDEKIARA_TOKEN", "ck_a_token")
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("STORE", "memory")
    monkeypatch.setenv("AUTH_MODE", "dev")
    result = runner.invoke(app, ["run", "system.health", "--remote", "https://cendekiara.test"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["ok"] is True


def test_run_remote_never_builds_the_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """The remote CLI talks to a server: it must not read a local profile."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    def boom(*args: object, **kwargs: object) -> object:
        raise AssertionError("the remote CLI must not build the settings")

    _mock_client(monkeypatch, httpx.MockTransport(handler))
    monkeypatch.setenv("CENDEKIARA_TOKEN", "ck_a_token")
    monkeypatch.setattr(config, "Settings", boom)
    result = runner.invoke(app, ["run", "system.health", "--remote", "https://cendekiara.test"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["ok"] is True
