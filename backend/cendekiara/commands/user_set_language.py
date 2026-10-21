"""REFERENCE COMMAND — copy this file's shape for every new command."""

from __future__ import annotations

from pydantic import Field

from cendekiara.core import store
from cendekiara.core.context import Context
from cendekiara.core.models import Lang, Model, UserProfile
from cendekiara.core.registry import Command, command


class UserSetLanguageIn(Model):
    lang: Lang = Field(description="Interface language: 'id' or 'en'")


class UserSetLanguageOut(Model):
    lang: Lang
    previous: Lang


@command("user.set_language", summary="Set the signed-in user's interface language")
class UserSetLanguage(Command[UserSetLanguageIn, UserSetLanguageOut]):
    def run(self, args: UserSetLanguageIn, ctx: Context) -> UserSetLanguageOut:
        # Own data only: the uid comes from the verified token, never from args.
        uid = ctx.actor.require_uid()
        profile = store.load(ctx.store, "users", uid, UserProfile)  # raises not_found
        previous = profile.lang
        ctx.store.update("users", uid, {"lang": args.lang})
        ctx.log.info("language changed for %s: %s -> %s", uid, previous, args.lang)
        return UserSetLanguageOut(lang=args.lang, previous=previous)
