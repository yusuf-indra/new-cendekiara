# 07 — Coding standards

Goal: code written by different AIs looks like it was written by one person.
When in doubt, copy the closest existing file.

## Python (backend)

- Python 3.12. Tools: `ruff` (lint + format, line length 110), `mypy --strict`,
  `pytest`. Config in `backend/pyproject.toml`. `make check` must pass.
- Names: modules/functions `snake_case`, classes `PascalCase`, constants
  `UPPER_SNAKE`. Command files `<domain>_<action>.py`, classes
  `<Domain><Action>` with `<Domain><Action>In` / `Out`.
- Imports absolute (`from cendekiara.core.store import Store`), sorted by ruff.
- Models: subclass `cendekiara.core.models.Model` (strict, camelCase JSON).
  Python fields `snake_case`.
- Config only via `cendekiara.core.config.settings` (pydantic-settings).
  Never `os.environ[...]` elsewhere.
- Logging: `logging.getLogger(__name__)` / `ctx.log`; no `print`. Never log
  tokens, answers keys or personal data beyond the uid.
- Errors: raise `AppError(code, message, hint=None)`. No bare `except:`;
  catch narrow exceptions and re-raise as `AppError`.
- External services (Firestore, Firebase Auth, AI, TTS, Cloud Tasks,
  payments) only in `core/firestore_store.py`, `core/auth.py`,
  `core/jobs.py` and `services/`, each behind an interface with a fake used
  by tests and `APP_ENV=dev`.
- Time: `cendekiara.core.clock.now()` (UTC), so tests can freeze it. Never
  `datetime.now()` in commands (old app had date-dependent flaky tests).
- Docstrings: one line, English. Comments say why, not what.
- Functions ≤ 40 lines; files ≤ 300 lines.

## TypeScript (frontend)

- `strict: true`, no `any`, no non-null `!` without a comment why.
- Components `PascalCase.tsx`, hooks `useThing.ts`, others `camelCase.ts`.
- Server state only via TanStack Query; local UI state via `useState`.
- Prettier: 2 spaces, single quotes, no semicolons, width 100.

## Jinja (public pages)

- Templates in `backend/cendekiara/web/templates/`, autoescape on, text via
  `t('key')`. No raw HTML from data; Markdown rendered with HTML disabled.

## JSON

- 2-space indent, UTF-8, no `\u` escapes, trailing newline. i18n files
  sorted by key.

## Git

- Branches `feat|fix|chore|docs|refactor/<short-name>`; never push to `main`.
- Commit message `<area>: <what changed>`, imperative, ≤ 72 chars.

## Tests

- Every command: happy path + login/ownership/validation errors, using the
  `ctx`, `admin_ctx`, `guest_ctx`, `mem` fixtures (`tests/conftest.py`).
- Every scoring and question-type plugin: table-driven tests.
- Public pages: render test (status 200, key text, no answer key in HTML).
- Frontend: Vitest for hooks and plugins; no snapshot-only tests.
