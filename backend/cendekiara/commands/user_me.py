"""The profile of the signed-in user. Readonly: the app shows it on every screen."""

from __future__ import annotations

from cendekiara.core import store
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.models import Lang, Model, UserProfile
from cendekiara.core.registry import Command, command


class UserMeIn(Model):
    """No arguments."""


class UserMeOut(Model):
    """The profile of the caller, plus what the caller may do."""

    uid: str
    email: str | None = None
    display_name: str | None = None
    nickname: str | None = None
    lang: Lang = "id"
    leaderboard_opt_out: bool = False
    is_admin: bool = False


@command("user.me", summary="The profile of the signed-in user", readonly=True)
class UserMe(Command[UserMeIn, UserMeOut]):
    def run(self, args: UserMeIn, ctx: Context) -> UserMeOut:
        # Own data only: the uid comes from the verified token, never from args.
        uid = ctx.actor.require_uid()
        profile = store.load(ctx.store, "users", uid, UserProfile)  # raises not_found
        if profile.uid != uid:
            raise AppError("not_found", f"users/{uid} not found")
        return UserMeOut(
            uid=profile.uid,
            email=profile.email,
            display_name=profile.display_name,
            nickname=profile.nickname,
            lang=profile.lang,
            leaderboard_opt_out=profile.leaderboard_opt_out,
            is_admin=ctx.actor.is_admin,
        )
