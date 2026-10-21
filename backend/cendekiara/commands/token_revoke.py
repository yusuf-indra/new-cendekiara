"""Revoke an admin API token, by id or by label."""

from __future__ import annotations

from cendekiara.core import clock
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command

COLLECTION = "api_tokens"


class TokenRevokeIn(Model):
    """The id of the token, or its label when there is only one."""

    id: str | None = None
    label: str | None = None


class TokenRevokeOut(Model):
    id: str
    label: str
    revoked_at: str


@command(
    "token.revoke",
    summary="Revoke an admin API token",
    admin_only=True,
    allow_jobs=False,
)
class TokenRevoke(Command[TokenRevokeIn, TokenRevokeOut]):
    def run(self, args: TokenRevokeIn, ctx: Context) -> TokenRevokeOut:
        ctx.actor.require_uid()
        token_id = self._find(ctx, args)
        doc = ctx.store.get(COLLECTION, token_id) or {}
        revoked_at = doc.get("revokedAt") or clock.now_iso()
        ctx.store.update(COLLECTION, token_id, {"revokedAt": revoked_at})
        ctx.log.info("api token revoked by %s (id %s)", ctx.actor.uid, token_id)
        return TokenRevokeOut(id=token_id, label=str(doc.get("label", "")), revoked_at=revoked_at)

    @staticmethod
    def _find(ctx: Context, args: TokenRevokeIn) -> str:
        """The id of the token to revoke; unknown tokens are 'not_found'."""
        if args.id:
            if ctx.store.get(COLLECTION, args.id) is None:
                raise AppError("not_found", "No such API token")
            return args.id
        if args.label:
            rows = [
                doc
                for doc in ctx.store.list(COLLECTION, {"label": args.label}, limit=1000)
                if isinstance(doc.get("id"), str)
            ]
            if not rows:
                raise AppError("not_found", "No API token with that label")
            rows.sort(key=lambda doc: str(doc.get("createdAt", "")))
            return str(rows[-1]["id"])
        raise AppError("invalid_args", "Give the id or the label of the token")
