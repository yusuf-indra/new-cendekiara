# Cendekiara (new)

Practice-test platform: IELTS-style English tests, TPA Bappenas, CPNS SKD, PKN STAN and more,
with a question bank, exam / practice / study modes, a public SEO site and an Android app.

This is a fresh rebuild. The old app (`yusuf-indra/Cendekiara`) is a **reference only**.

- Rules for anyone writing code (AI or human): [`AGENTS.md`](AGENTS.md)
- Where the project is now: [`docs/PROGRESS.md`](docs/PROGRESS.md)
- Design: [`docs/`](docs/)

```bash
make install   # backend venv (+ frontend deps)
make check     # lint, types, tests: exactly what CI runs
make dev       # local backend (memory store, dev login) + frontend
```

## Phase 0: the backend skeleton

Settings live in `backend/cendekiara/core/config.py` (pydantic-settings) and come from the
environment: `cp .env.example backend/.env` (the file is read from the folder you start the
backend from).

| Variable | Default | Meaning |
| --- | --- | --- |
| `APP_ENV` | `dev` | `dev` or `prod`; `prod` requires `STORE=firestore` + `AUTH_MODE=firebase` |
| `SITE` | `id` | `id` or `global` |
| `STORE` | `memory` | `memory` or `firestore` |
| `AUTH_MODE` | `dev` | `dev` (token `dev:<uid>`) or `firebase` (ID tokens) |
| `JOBS` | `inline` | `inline` (thread) or `cloudtasks` |
| `ADMIN_EMAILS` | – | comma-separated emails of the admins |
| `LOG_LEVEL` | `INFO` | log level |

Every action is a command (`backend/cendekiara/commands/`). The CLI runs them locally; the
API arrives in Phase 1.

```bash
cd backend
cendekiara commands list            # every command with its flags
cendekiara commands list --json     # the discovery payload (docs/03-commands.md)
cendekiara run system.health        # run one command; JSON on stdout
cendekiara run user.set_language --arg lang=en
```

The result is JSON on stdout; an error is JSON on stderr
(`{"error": {"code", "message", "hint"}}`) and the exit code is 1. `--remote` (run through the
API with an admin token) arrives in Phase 1.
