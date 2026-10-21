"""The JSON API: discovery, the command routes and the error rendering.

The routes are thin on purpose: they translate a request into a command call
and translate the result (or the AppError) back (docs/03-commands.md).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from cendekiara import __version__
from cendekiara.core import config, plugins, registry
from cendekiara.core.auth import Authenticator, Identity, bearer_token
from cendekiara.core.config import Settings
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.registry import CommandInfo
from cendekiara.core.store import Store, build_store

log = logging.getLogger(__name__)

API_PREFIX = "/api"
NO_STORE = "no-store"

# The code of an HTTP error that did not come from a command.
_STATUS_CODES = {
    400: "invalid_args",
    401: "login_required",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    422: "invalid_args",
}


def create_app(store: Store | None = None, settings: Settings | None = None) -> FastAPI:
    """The API app. It refuses to start in a profile that is not safe."""
    cfg = settings or config.settings
    _refuse_unsafe_profile(cfg)
    registry.load_all()
    plugins.load_all()

    app = FastAPI(title="Cendekiara API", version=__version__, docs_url=None, redoc_url=None)
    app.state.settings = cfg
    app.state.store = store or build_store(cfg.store)
    app.state.auth = Authenticator(cfg, app.state.store)
    app.add_middleware(ApiOnlyCORSMiddleware, allow_origins=cfg.cors_origins())
    _add_error_handlers(app)
    _add_routes(app)
    if cfg.jobs == "cloudtasks":
        _add_internal_routes(app)
    return app


def _add_error_handlers(app: FastAPI) -> None:
    """Every error of the API has the same body."""

    @app.exception_handler(AppError)
    async def _command_error(request: Request, exc: AppError) -> JSONResponse:
        return _error_response(exc)

    @app.exception_handler(HTTPException)
    async def _http_error(request: Request, exc: HTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "server_error")
        error = AppError(code, str(exc.detail))
        response = JSONResponse(status_code=exc.status_code, content={"error": error.to_dict()})
        response.headers["Cache-Control"] = NO_STORE
        for key, value in (exc.headers or {}).items():
            response.headers[key] = value
        return response


def _add_routes(app: FastAPI) -> None:
    """The routes: discovery and one route per command."""

    @app.get("/api/commands")
    async def list_commands(request: Request) -> JSONResponse:
        """The commands this caller may run, with their schemas."""
        identity = _identity(request)
        payload = [info.schema() for info in registry.all_commands() if _visible(info, identity)]
        return _json(payload, cache=NO_STORE)

    @app.post("/api/commands/{name}")
    async def post_command(name: str, request: Request) -> JSONResponse:
        """Run a command; the body is the arguments of the command."""
        return await _run(app, name, request, read_body=True)

    @app.get("/api/commands/{name}")
    async def get_command(name: str, request: Request) -> JSONResponse:
        """Run a readonly command; the query string is the arguments."""
        return await _run(app, name, request, read_body=False)


def _add_internal_routes(app: FastAPI) -> None:
    """The worker endpoint, mounted only when JOBS=cloudtasks (docs/10-security.md rule 12)."""

    @app.post("/internal/jobs/run")
    async def run_internal_job(request: Request) -> JSONResponse:
        """Run one queued job, guarded by a Google OIDC token (worker only)."""
        from cendekiara.core import jobs

        settings = request.app.state.settings
        token = bearer_token(request.headers.get("authorization"))
        if not token:
            raise AppError("invalid_token", "The worker token is missing")
        jobs.verify_worker_token(token, settings)
        body = await request.json()
        job_id = body.get("jobId") if isinstance(body, dict) else None
        if not isinstance(job_id, str) or not job_id:
            raise AppError("invalid_args", "The jobId is missing")
        jobs.run_job(job_id, request.app.state.store, settings, settings.site)
        return _json({"ok": True}, cache=NO_STORE)


async def _run(app: FastAPI, name: str, request: Request, *, read_body: bool) -> JSONResponse:
    """Run one command for the caller and answer with its result."""
    identity = _identity(request)
    info = registry.get(name)
    ctx = Context(
        identity.actor,
        app.state.store,
        site=app.state.settings.site,
        via=identity.via,
    )
    registry.check_access(info, ctx)
    if not read_body and not info.readonly:
        raise AppError("method_not_allowed", f"{name} is only served with POST")
    args = await _args(request, read_body)
    result = registry.execute(name, args, ctx)
    return _json(result.model_dump(by_alias=True, mode="json"), cache=cache_control(info))


def _refuse_unsafe_profile(cfg: Settings) -> None:
    """No API without an explicit APP_ENV, and no dev auth outside dev."""
    if not cfg.app_env_explicit:
        raise RuntimeError("APP_ENV must be set explicitly (dev or prod) before the API starts")
    if cfg.auth_mode == "dev" and cfg.app_env != "dev":
        raise RuntimeError("AUTH_MODE=dev is only allowed when APP_ENV=dev")


def _identity(request: Request) -> Identity:
    """Who is calling: from the Authorization header, never from the arguments."""
    authenticator: Authenticator = request.app.state.auth
    return authenticator.authenticate(request.headers.get("authorization"))


def _visible(info: CommandInfo, identity: Identity) -> bool:
    """Admin commands look absent to everyone else (docs/10-security.md rule 5)."""
    if identity.actor.is_admin:
        return True
    if info.admin_only:
        return False
    return identity.actor.uid is not None or info.public


async def _args(request: Request, read_body: bool) -> dict[str, Any]:
    """The arguments of a command: the JSON body (POST) or the query string (GET)."""
    if not read_body:
        return dict(request.query_params)
    raw = await request.body()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AppError("invalid_args", "The body is not valid JSON") from exc
    if not isinstance(data, dict):
        raise AppError("invalid_args", "The body must be a JSON object")
    return data


def cache_control(info: CommandInfo) -> str:
    """Public readonly commands may be cached by the CDN; everything else may not."""
    if info.public and info.readonly and info.cache_seconds > 0:
        return f"public, max-age={info.cache_seconds}"
    return NO_STORE


def _json(payload: Any, *, cache: str) -> JSONResponse:
    """A JSON answer that is never cached for a specific user."""
    response = JSONResponse(payload)
    response.headers["Cache-Control"] = cache
    response.headers["Vary"] = "Authorization"
    return response


def _error_response(exc: AppError) -> JSONResponse:
    """Every error of the API has the same shape: {"error": {code, message, hint}}."""
    response = JSONResponse(status_code=exc.http_status, content={"error": exc.to_dict()})
    response.headers["Cache-Control"] = NO_STORE
    return response


class ApiOnlyCORSMiddleware:
    """CORS headers only on /api/* (docs/10-security.md rule 13)."""

    def __init__(self, app: ASGIApp, *, allow_origins: list[str]) -> None:
        self.app = app
        self.cors = CORSMiddleware(
            app,
            allow_origins=allow_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith(API_PREFIX):
            await self.cors(scope, receive, send)
            return
        await self.app(scope, receive, send)


app = create_app()
