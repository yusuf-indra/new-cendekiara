"""Command registry: the single place every action (and app read) is declared and run."""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar, TypeVar, cast

from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.models import Model

In = TypeVar("In", bound=Model)
Out = TypeVar("Out", bound=Model)


class Command[In: Model, Out: Model]:
    """Subclass, implement `run`, register with @command. Nothing else."""

    name: ClassVar[str]
    input_model: ClassVar[type[Model]]
    output_model: ClassVar[type[Model]]

    def run(self, args: In, ctx: Context) -> Out:
        raise NotImplementedError


@dataclass(frozen=True)
class CommandInfo:
    name: str
    summary: str
    queued: bool  # long work: returns a job id, the worker runs it
    admin_only: bool
    allow_jobs: bool  # may run from a job file / remote CLI
    readonly: bool  # also served at GET /api/commands/{name}
    public: bool  # no login needed (readonly only)
    cache_seconds: int  # CDN cache for public GETs
    cls: type[Command[Any, Any]]

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "summary": self.summary,
            "queued": self.queued,
            "adminOnly": self.admin_only,
            "allowJobs": self.allow_jobs,
            "readonly": self.readonly,
            "public": self.public,
            "inputSchema": self.cls.input_model.model_json_schema(by_alias=True),
            "outputSchema": self.cls.output_model.model_json_schema(by_alias=True),
        }


_REGISTRY: dict[str, CommandInfo] = {}


def command(
    name: str,
    *,
    summary: str,
    queued: bool = False,
    admin_only: bool = False,
    allow_jobs: bool = True,
    readonly: bool = False,
    public: bool = False,
    cache_seconds: int = 0,
) -> Callable[[type[Command[In, Out]]], type[Command[In, Out]]]:
    """Register a command class under `domain.action`."""
    if public and (not readonly or admin_only):
        raise RuntimeError(f"{name}: public commands must be readonly and not admin_only")

    def wrap(cls: type[Command[In, Out]]) -> type[Command[In, Out]]:
        if name in _REGISTRY:
            raise RuntimeError(f"duplicate command: {name}")
        base = cls.__orig_bases__[0]  # type: ignore[attr-defined]
        cls.input_model, cls.output_model = base.__args__
        cls.name = name
        _REGISTRY[name] = CommandInfo(
            name, summary, queued, admin_only, allow_jobs, readonly, public, cache_seconds, cls
        )
        return cls

    return wrap


def load_all() -> None:
    """Import every module in cendekiara.commands so their @command decorators run."""
    import cendekiara.commands as pkg

    for mod in pkgutil.iter_modules(pkg.__path__):
        importlib.import_module(f"{pkg.__name__}.{mod.name}")


def get(name: str) -> CommandInfo:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise AppError("unknown_command", f"No command named {name!r}") from None


def all_commands() -> list[CommandInfo]:
    return sorted(_REGISTRY.values(), key=lambda c: c.name)


def check_access(info: CommandInfo, ctx: Context) -> None:
    """Login, admin and job rules. Applied to every call, whoever calls."""
    if not info.public and ctx.actor.uid is None:
        raise AppError("login_required", "Please sign in")
    if info.admin_only and not ctx.actor.is_admin:
        raise AppError("admin_only", f"No command named {info.name!r}")
    if ctx.via == "job" and not info.allow_jobs:
        raise AppError("invalid_args", f"{info.name} cannot run from a job")


def execute(name: str, raw_args: dict[str, Any], ctx: Context) -> Model:
    """Validate raw args and run a command inline (the worker calls this too)."""
    info = get(name)
    check_access(info, ctx)
    try:
        args = info.cls.input_model.model_validate(raw_args)
    except ValueError as exc:
        raise AppError("invalid_args", str(exc), hint=f"See the schema of {name}") from exc
    result = info.cls().run(args, ctx)
    ctx.log.info("command finished: %s (via %s)", name, ctx.via)
    return cast(Model, result)
