"""The CLI: the discovery payload, running a command, errors as JSON on stderr."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from cendekiara.cli import app, decode_arg_value

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
