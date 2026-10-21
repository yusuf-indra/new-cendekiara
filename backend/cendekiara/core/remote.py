"""Run a command on another server through its API, with an admin API token.

The remote CLI needs nothing but a token and a URL: no store, no auth mode
and no cloud credentials (docs/03-commands.md).
"""

from __future__ import annotations

from typing import Any

import httpx

from cendekiara.core.errors import AppError

DEFAULT_TIMEOUT = 30.0


def make_client(timeout: float = DEFAULT_TIMEOUT) -> httpx.Client:
    """The HTTP client of the remote CLI."""
    return httpx.Client(timeout=timeout)


def command_url(base_url: str, name: str) -> str:
    """The URL of one command: <base>/api/commands/<name>."""
    return f"{base_url.rstrip('/')}/api/commands/{name}"


def run_remote(
    name: str,
    args: dict[str, Any],
    base_url: str,
    token: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """POST the command to the server and return its result.

    The error code of the server is re-raised; a transport failure becomes
    'remote_error'.
    """
    url = command_url(base_url, name)
    headers = {"Authorization": f"Bearer {token}"}
    http = client or make_client(timeout)
    try:
        response = http.post(url, json=args, headers=headers, timeout=timeout)
    except httpx.HTTPError as exc:
        raise AppError("remote_error", f"Could not reach {url}: {exc}") from exc
    finally:
        if client is None:
            http.close()
    return _payload(response)


def _payload(response: httpx.Response) -> dict[str, Any]:
    """The result of the command, or the error the server reported."""
    if response.status_code >= 400:
        raise _server_error(response)
    try:
        data = response.json()
    except ValueError as exc:
        raise AppError("remote_error", "The server did not answer with JSON") from exc
    if not isinstance(data, dict):
        raise AppError("remote_error", "The server did not answer with a JSON object")
    return data


def _server_error(response: httpx.Response) -> AppError:
    """The error of the server, with the code it reported."""
    code = "remote_error"
    message = f"The server answered {response.status_code}"
    hint: str | None = None
    body: Any = None
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            code = str(error.get("code") or code)
            message = str(error.get("message") or message)
            raw_hint = error.get("hint")
            hint = raw_hint if isinstance(raw_hint, str) else None
    return AppError(code, message, hint)
