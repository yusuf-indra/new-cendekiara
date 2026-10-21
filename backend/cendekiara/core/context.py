"""Context passed to every command: who is asking, the store, services, logger."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from cendekiara.core.errors import AppError

if TYPE_CHECKING:
    from cendekiara.core.config import Settings
    from cendekiara.core.store import Store

Via = Literal["web", "app", "cli", "job", "command", "remote"]


@dataclass(frozen=True)
class Actor:
    """The signed-in user (uid None = anonymous, only for public commands)."""

    uid: str | None
    is_admin: bool = False
    email: str | None = None

    @classmethod
    def system(cls) -> Actor:
        """Used by the CLI and the worker on the server: full rights."""
        return cls(uid="system", is_admin=True)

    def require_uid(self) -> str:
        """The uid of a signed-in user, or AppError('login_required')."""
        if self.uid is None:
            raise AppError("login_required", "Please sign in")
        return self.uid


@dataclass
class Context:
    actor: Actor
    store: Store
    site: str = "id"  # see docs/09-seo-and-sites.md
    via: Via = "web"
    job_id: str | None = None
    log: logging.Logger = field(default_factory=lambda: logging.getLogger("cendekiara.command"))
    settings: Settings | None = None  # None means the process settings

    def run(self, name: str, args: dict[str, Any]) -> Any:
        """Run another command so it is validated and checked like any other."""
        from cendekiara.core import registry

        child = Context(self.actor, self.store, self.site, "command", self.job_id, self.log, self.settings)
        return registry.execute(name, args, child)
