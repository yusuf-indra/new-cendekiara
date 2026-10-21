"""Base model and the shared document models stored in Firestore."""

from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

Lang = Literal["id", "en"]


class Model(BaseModel):
    """Base for every command input/output and stored document: strict, camelCase in JSON."""

    model_config = ConfigDict(extra="forbid", alias_generator=to_camel, populate_by_name=True)

    def to_doc(self) -> dict[str, object]:
        """Serialise for the store (camelCase keys, no None values)."""
        return self.model_dump(by_alias=True, exclude_none=True, mode="json")

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> Self:
        """Read a stored document, ignoring the fields this model does not know.

        Documents grow (a new field in another phase must not break every
        reader), but a known field with a wrong type is still an error.
        """
        known: set[str] = set()
        for name, field in cls.model_fields.items():
            known.add(name)
            if field.alias:
                known.add(field.alias)
        return cls.model_validate({k: v for k, v in doc.items() if k in known})


class UserProfile(Model):
    """`users/{uid}`: profile and settings a student edits."""

    uid: str
    email: str | None = None
    display_name: str | None = None
    nickname: str | None = None
    lang: Lang = "id"
    leaderboard_opt_out: bool = False


class ApiToken(Model):
    """`api_tokens/{tokenHash}`: an admin API token, stored as its hash only."""

    id: str
    label: str
    created_by: str
    # The email of the owner: it is re-checked on every use of the token.
    created_by_email: str | None = None
    created_at: str
    last_used_at: str | None = None
    revoked_at: str | None = None
