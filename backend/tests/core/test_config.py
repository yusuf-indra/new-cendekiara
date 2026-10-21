"""Settings: the dev profile by default, admin emails parsed, prod refuses shortcuts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cendekiara.core.config import Settings

ENV_KEYS = ("APP_ENV", "SITE", "STORE", "AUTH_MODE", "JOBS", "ADMIN_EMAILS", "LOG_LEVEL")


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """No setting comes from the shell."""
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_defaults_are_the_dev_profile(clean_env: None) -> None:
    settings = Settings(_env_file=None)
    assert settings.app_env == "dev"
    assert settings.site == "id"
    assert settings.store == "memory"
    assert settings.auth_mode == "dev"
    assert settings.jobs == "inline"
    assert settings.admin_emails == []
    assert settings.log_level == "INFO"


def test_admin_emails_are_a_comma_separated_list(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_EMAILS", " Admin@Example.com , other@example.com ")
    settings = Settings(_env_file=None)
    assert settings.admin_emails == ["admin@example.com", "other@example.com"]
    assert settings.is_admin_email("ADMIN@example.com")
    assert not settings.is_admin_email("stranger@example.com")
    assert not settings.is_admin_email(None)


def test_prod_refuses_the_memory_store(clean_env: None) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="prod", store="memory", auth_mode="firebase")


def test_prod_refuses_dev_auth(clean_env: None) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="prod", store="firestore", auth_mode="dev")


def test_prod_with_firestore_and_firebase_is_fine(clean_env: None) -> None:
    settings = Settings(_env_file=None, app_env="prod", store="firestore", auth_mode="firebase")
    assert settings.app_env == "prod"
    assert settings.store == "firestore"


def test_unknown_log_level_is_refused(clean_env: None) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, log_level="chatty")
