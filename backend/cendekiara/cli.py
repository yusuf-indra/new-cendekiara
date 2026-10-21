"""`cendekiara` CLI: list the commands, run one on this machine or on a server.

`--remote <url>` runs the command through the API of another server with an
admin API token (`CENDEKIARA_TOKEN`); it needs no local store or credentials.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, NoReturn

import typer
from pydantic import ValidationError

from cendekiara.core import clock, plugins, registry, remote
from cendekiara.core.context import Actor, Context
from cendekiara.core.errors import AppError
from cendekiara.core.logging import setup_logging
from cendekiara.core.store import build_store

if TYPE_CHECKING:
    from cendekiara.core.config import Settings

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Cendekiara backend CLI.")
commands_app = typer.Typer(no_args_is_help=True, help="Inspect the command registry.")
app.add_typer(commands_app, name="commands")
jobs_app = typer.Typer(no_args_is_help=True, help="Run a job file.")
app.add_typer(jobs_app, name="jobs")


def decode_arg_value(raw: str) -> Any:
    """`key=value` values are JSON when they can be (3, true, [1,2]), else plain strings."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _fail(error: AppError) -> NoReturn:
    """Print the error as JSON on stderr and leave with a non-zero exit code."""
    typer.echo(json.dumps({"error": error.to_dict()}, ensure_ascii=False), err=True)
    raise typer.Exit(code=1)


def _load_settings() -> Settings:
    """Load the settings; refuse to start when the profile is not safe."""
    try:
        from cendekiara.core.config import Settings

        return Settings()
    except ValidationError as exc:
        typer.echo(f"Error: invalid settings: {_format_validation_error(exc)}", err=True)
        raise typer.Exit(code=1) from exc


def _format_validation_error(exc: ValidationError) -> str:
    """One line per broken field: 'store: APP_ENV=prod requires STORE=firestore'."""
    parts: list[str] = []
    for err in exc.errors():
        where = ".".join(str(item) for item in err["loc"])
        message = str(err["msg"])
        parts.append(f"{where}: {message}" if where else message)
    return "; ".join(parts)


def _parse_args(items: list[str]) -> dict[str, Any]:
    """Turn `--arg key=value` pairs into the arguments of a command."""
    args: dict[str, Any] = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key.strip():
            raise AppError("invalid_args", f"Bad --arg {item!r}: expected key=value")
        args[key.strip()] = decode_arg_value(value)
    return args


def _execute(name: str, args: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Run one command as the system actor and return its output as a JSON-ready dict."""
    store = build_store(settings.store)
    ctx = Context(Actor.system(), store, site=settings.site, via="cli")
    result = registry.execute(name, args, ctx)
    return result.model_dump(by_alias=True, mode="json")


@commands_app.command("list")
def list_commands(
    json_output: Annotated[bool, typer.Option("--json", help="Print the raw discovery payload.")] = False,
) -> None:
    """List every command with its flags and schemas."""
    _load_settings()
    registry.load_all()
    plugins.load_all()
    payload = [info.schema() for info in registry.all_commands()]
    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    for info in payload:
        flags = [flag for flag in ("public", "readonly", "adminOnly", "queued") if info[flag]]
        typer.echo(f"{info['name']:<24} {','.join(flags) or '-':<22} {info['summary']}")


@app.command("run")
def run_command(
    name: Annotated[str, typer.Argument(help="Command name, e.g. system.health")],
    arg: Annotated[
        list[str] | None,
        typer.Option("--arg", "-a", help="Argument as key=value; repeatable."),
    ] = None,
    remote_url: Annotated[
        str | None,
        typer.Option("--remote", help="Base URL of a server: run the command through its API."),
    ] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Log at the configured level.")] = False,
) -> None:
    """Run one command here or on a server; the result is JSON on stdout."""
    if remote_url:
        _run_remote(name, arg or [], remote_url)
        return
    settings = _load_settings()
    setup_logging(settings.log_level if verbose else "WARNING")
    registry.load_all()
    plugins.load_all()
    try:
        args = _parse_args(arg or [])
        payload = _execute(name, args, settings)
    except AppError as exc:
        _fail(exc)
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


def _run_remote(name: str, items: list[str], base_url: str) -> None:
    """Run a command through the API of another server, with an admin API token."""
    token = _remote_token()
    if not token:
        typer.echo("Error: CENDEKIARA_TOKEN is not set", err=True)
        raise typer.Exit(code=1)
    try:
        args = _parse_args(items)
        payload = remote.run_remote(name, args, base_url, token)
    except AppError as exc:
        _fail(exc)
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


def _remote_token() -> str | None:
    """The admin API token of the remote CLI (never logged)."""
    from cendekiara.core.config import RemoteConfig

    return RemoteConfig().cendekiara_token


@jobs_app.command("run")
def run_job_file(
    file: Annotated[str, typer.Argument(help="Path to a JSON file: {steps: [{command, args}]}")],
) -> None:
    """Run a job file's steps as the system actor; JSON on stdout, exit 0/1."""
    try:
        settings = _load_settings()
        setup_logging("WARNING")
        registry.load_all()
        plugins.load_all()
        store = build_store(settings.store)
        steps = _read_steps(file)
    except AppError as exc:
        _fail(exc)
    results: list[dict[str, Any]] = []
    ok = True
    for step in steps:
        command_name = step.get("command")
        args = step.get("args", {})
        started = clock.now()
        if not isinstance(command_name, str) or not isinstance(args, dict):
            results.append(
                {
                    "command": command_name,
                    "ok": False,
                    "error": {
                        "code": "invalid_args",
                        "message": "A step needs a 'command' and an 'args' object",
                        "hint": None,
                    },
                    "seconds": 0.0,
                }
            )
            ok = False
            continue
        ctx = Context(Actor.system(), store, site=settings.site, via="cli")
        try:
            result = registry.execute(command_name, args, ctx)
            results.append(
                {
                    "command": command_name,
                    "ok": True,
                    "result": result.model_dump(by_alias=True, mode="json"),
                    "seconds": round((clock.now() - started).total_seconds(), 3),
                }
            )
        except AppError as exc:
            ok = False
            results.append(
                {
                    "command": command_name,
                    "ok": False,
                    "error": exc.to_dict(),
                    "seconds": round((clock.now() - started).total_seconds(), 3),
                }
            )
    typer.echo(json.dumps({"id": clock.now_iso(), "ok": ok, "steps": results}, indent=2, ensure_ascii=False))
    raise typer.Exit(code=0 if ok else 1)


def _read_steps(path: str) -> list[dict[str, Any]]:
    """Read the ``{steps: [{command, args}]}`` job file."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AppError("invalid_args", f"Cannot read the job file: {exc}") from exc
    steps = data.get("steps") if isinstance(data, dict) else None
    if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps):
        raise AppError("invalid_args", "The job file must be {steps: [{command, args}]}")
    return steps


if __name__ == "__main__":  # pragma: no cover
    app()
