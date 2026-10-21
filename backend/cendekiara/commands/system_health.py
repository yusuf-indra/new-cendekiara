"""Health check: is the service up? Public, readonly, and it never writes."""

from __future__ import annotations

from cendekiara import __version__
from cendekiara.core import clock
from cendekiara.core.config import settings
from cendekiara.core.context import Context
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class SystemHealthIn(Model):
    """No arguments."""


class SystemHealthOut(Model):
    ok: bool
    time: str
    version: str
    env: str | None = None
    site: str | None = None
    store: str | None = None


@command("system.health", summary="Health check: the service is up", readonly=True, public=True)
class SystemHealth(Command[SystemHealthIn, SystemHealthOut]):
    def run(self, args: SystemHealthIn, ctx: Context) -> SystemHealthOut:
        # Guests only learn that the service is up; the profile is for signed-in actors.
        signed_in = ctx.actor.uid is not None
        return SystemHealthOut(
            ok=self._probe(ctx),
            time=clock.now_iso(),
            version=__version__,
            env=settings.app_env if signed_in else None,
            site=ctx.site if signed_in else None,
            store=settings.store if signed_in else None,
        )

    @staticmethod
    def _probe(ctx: Context) -> bool:
        """Read-only probe of the store: one read, never a write."""
        try:
            ctx.store.get("_health", "probe")
        except Exception:
            ctx.log.warning("store probe failed", exc_info=True)
            return False
        return True
