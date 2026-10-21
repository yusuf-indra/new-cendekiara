"""Create an admin API token. The token is shown once and stored as a hash only."""

from __future__ import annotations

from pydantic import Field

from cendekiara.core import auth, clock, store
from cendekiara.core.context import Context
from cendekiara.core.models import ApiToken, Model
from cendekiara.core.registry import Command, command


class TokenCreateIn(Model):
    label: str = Field(min_length=1, max_length=64, description="What this token is for.")


class TokenCreateOut(Model):
    """The token is in `token` and is never shown again."""

    token: str
    id: str
    label: str
    created_at: str


@command(
    "token.create",
    summary="Create an admin API token (shown once)",
    admin_only=True,
    allow_jobs=False,
)
class TokenCreate(Command[TokenCreateIn, TokenCreateOut]):
    def run(self, args: TokenCreateIn, ctx: Context) -> TokenCreateOut:
        uid = ctx.actor.require_uid()
        token = auth.generate_token()
        token_id = auth.hash_token(token)
        doc = ApiToken(id=token_id, label=args.label, created_by=uid, created_at=clock.now_iso())
        store.save(ctx.store, "api_tokens", token_id, doc)
        ctx.log.info("api token created by %s (label %s)", uid, args.label)
        return TokenCreateOut(token=token, id=token_id, label=doc.label, created_at=doc.created_at)
