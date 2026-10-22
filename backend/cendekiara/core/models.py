"""Base model and the shared document models stored in Firestore."""

from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field
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


class AttemptResultSection(Model):
    """Per-section result of an attempt: counts, marks, score and time."""

    correct: int = 0
    wrong: int = 0
    blank: int = 0
    marks: float = 0.0
    score: float | None = None
    time_sec: float = 0.0


class AttemptResult(Model):
    """`attempts/{attemptId}.result`: the score of a submitted attempt.

    The score is always an estimate (docs/10-security.md, legal limits).
    """

    score: float | None = None
    score_type: str | None = None
    correct: int = 0
    wrong: int = 0
    blank: int = 0
    wrong_penalty: float = 0.0
    sections: dict[str, AttemptResultSection] = Field(default_factory=dict)


class Attempt(Model):
    """`attempts/{attemptId}`: a running, paused or submitted attempt."""

    id: str
    uid: str
    mode: Literal["exam", "practice"] = "exam"
    test_id: str | None = None
    exam: str | None = None
    # The assembled package the attempt was taken with, so later edits of the
    # items never change an old result (docs/02-data-model.md).
    package_snapshot: dict[str, Any] | None = None
    status: Literal["in_progress", "paused", "submitted"] = "in_progress"
    answers: dict[str, list[str] | str] = Field(default_factory=dict)
    timings: dict[str, float] = Field(default_factory=dict)
    flags: list[str] = Field(default_factory=list)
    deadline_at: str | None = None
    started_at: str
    updated_at: str | None = None
    paused_at: str | None = None
    submitted_at: str | None = None
    free: bool = False
    wrong_penalty: float = 0.0
    duration_sec: int | None = None
    result: AttemptResult | None = None
