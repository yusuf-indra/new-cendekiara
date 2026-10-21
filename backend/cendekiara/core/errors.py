"""The one exception type commands raise; API, CLI and job runner all render it."""

from __future__ import annotations

# Stable error codes and the HTTP status the API answers with.
HTTP_STATUS: dict[str, int] = {
    "invalid_args": 422,
    "unknown_command": 404,
    "not_found": 404,  # also used for data owned by someone else (never 403)
    "login_required": 401,
    "admin_only": 404,  # hide admin commands from non-admins
    "conflict": 409,
    "deadline_passed": 409,
    "quota_exceeded": 402,
}


class AppError(Exception):
    """A user-facing error with a stable machine code."""

    def __init__(self, code: str, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint

    @property
    def http_status(self) -> int:
        return HTTP_STATUS.get(self.code, 400)

    def to_dict(self) -> dict[str, str | None]:
        return {"code": self.code, "message": self.message, "hint": self.hint}
