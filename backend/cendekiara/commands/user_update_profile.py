"""Update the profile of the signed-in user. Only the caller's own document."""

from __future__ import annotations

from pydantic import Field

from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.models import Lang, Model, UserProfile
from cendekiara.core.registry import Command, command


class UserUpdateProfileIn(Model):
    """The fields to change; a field that is not given stays as it is."""

    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    nickname: str | None = Field(default=None, min_length=1, max_length=40)
    lang: Lang | None = None
    leaderboard_opt_out: bool | None = None


class UserUpdateProfileOut(Model):
    """The profile after the change."""

    uid: str
    email: str | None = None
    display_name: str | None = None
    nickname: str | None = None
    lang: Lang = "id"
    leaderboard_opt_out: bool = False
    is_admin: bool = False


@command("user.update_profile", summary="Update the profile of the signed-in user")
class UserUpdateProfile(Command[UserUpdateProfileIn, UserUpdateProfileOut]):
    def run(self, args: UserUpdateProfileIn, ctx: Context) -> UserUpdateProfileOut:
        # Own data only: the uid comes from the verified token, never from args.
        uid = ctx.actor.require_uid()
        doc = ctx.store.get("users", uid)
        if doc is not None and doc.get("uid") != uid:
            raise AppError("not_found", f"users/{uid} not found")
        profile = UserProfile.from_doc(doc) if doc is not None else UserProfile(uid=uid)
        self._apply(args, profile)
        merged = {**(doc or {}), **profile.to_doc()}
        ctx.store.set("users", uid, merged)
        ctx.log.info("profile updated for %s", uid)
        return UserUpdateProfileOut(
            uid=profile.uid,
            email=profile.email,
            display_name=profile.display_name,
            nickname=profile.nickname,
            lang=profile.lang,
            leaderboard_opt_out=profile.leaderboard_opt_out,
            is_admin=ctx.actor.is_admin,
        )

    @staticmethod
    def _apply(args: UserUpdateProfileIn, profile: UserProfile) -> None:
        """Copy the given fields into the profile; None means "not given"."""
        if args.display_name is not None:
            profile.display_name = args.display_name
        if args.nickname is not None:
            profile.nickname = args.nickname
        if args.lang is not None:
            profile.lang = args.lang
        if args.leaderboard_opt_out is not None:
            profile.leaderboard_opt_out = args.leaderboard_opt_out
