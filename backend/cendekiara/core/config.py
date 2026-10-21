"""Settings for the whole backend. The only place environment variables are read.

Dev shortcuts (memory store, dev auth) are refused unless `APP_ENV=dev`
(see docs/10-security.md rule 11).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

AppEnv = Literal["dev", "prod"]
Site = Literal["id", "global"]
StoreName = Literal["memory", "firestore"]
AuthMode = Literal["firebase", "dev"]
JobsMode = Literal["inline", "cloudtasks"]
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


class Settings(BaseSettings):
    """Environment-driven settings; every field has a safe dev default."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: AppEnv = "dev"
    site: Site = "id"
    store: StoreName = "memory"
    auth_mode: AuthMode = "dev"
    jobs: JobsMode = "inline"
    admin_emails: Annotated[list[str], NoDecode] = Field(default_factory=list)
    log_level: str = "INFO"

    @field_validator("admin_emails", mode="before")
    @classmethod
    def _split_admin_emails(cls, value: object) -> object:
        """ADMIN_EMAILS is a comma-separated list of emails in the environment."""
        if isinstance(value, str):
            parts: list[str] = value.split(",")
        elif isinstance(value, (list, tuple)):
            parts = [str(part) for part in value]
        else:
            return value
        return [part.strip().lower() for part in parts if part.strip()]

    @field_validator("log_level")
    @classmethod
    def _check_log_level(cls, value: str) -> str:
        level = value.strip().upper()
        if level not in LOG_LEVELS:
            raise ValueError(f"LOG_LEVEL must be one of {', '.join(LOG_LEVELS)}")
        return level

    @model_validator(mode="after")
    def _refuse_dev_shortcuts(self) -> Settings:
        """Only APP_ENV=dev may use the memory store or the dev auth mode."""
        if self.app_env != "dev":
            if self.store != "firestore":
                raise ValueError("APP_ENV=prod requires STORE=firestore")
            if self.auth_mode != "firebase":
                raise ValueError("APP_ENV=prod requires AUTH_MODE=firebase")
        return self

    def is_admin_email(self, email: str | None) -> bool:
        """True when the email is listed in ADMIN_EMAILS."""
        if email is None:
            return False
        return email.strip().lower() in self.admin_emails


settings = Settings()
