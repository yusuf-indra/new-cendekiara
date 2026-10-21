"""Base model and the shared document models stored in Firestore."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

Lang = Literal["id", "en"]


class Model(BaseModel):
    """Base for every command input/output and stored document: strict, camelCase in JSON."""

    model_config = ConfigDict(extra="forbid", alias_generator=to_camel, populate_by_name=True)

    def to_doc(self) -> dict[str, object]:
        """Serialise for the store (camelCase keys, no None values)."""
        return self.model_dump(by_alias=True, exclude_none=True, mode="json")


class UserProfile(Model):
    """`users/{uid}`: profile and settings a student edits."""

    uid: str
    email: str | None = None
    display_name: str | None = None
    nickname: str | None = None
    lang: Lang = "id"
    leaderboard_opt_out: bool = False
