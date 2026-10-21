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

## Settings

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
| `SITE_URL` | – | the site URL; CORS on `/api` allows it |
| `CAPACITOR_ORIGIN` | – | the origin of the Android app; CORS on `/api` allows it |
| `LOG_LEVEL` | `INFO` | log level |

The API refuses to start when `APP_ENV` was not set explicitly, and never runs with
`AUTH_MODE=dev` outside `APP_ENV=dev`.

Every action is a command (`backend/cendekiara/commands/`). The CLI runs them locally; the
API serves them to the app and the admin screens.

```bash
cd backend
cendekiara commands list            # every command with its flags
cendekiara commands list --json     # the discovery payload (docs/03-commands.md)
cendekiara run system.health        # run one command; JSON on stdout
cendekiara run user.set_language --arg lang=en
```

The result is JSON on stdout; an error is JSON on stderr
(`{"error": {"code", "message", "hint"}}`) and the exit code is 1.

## Phase 1: the API and the auth

The API is a thin FastAPI app (`backend/cendekiara/api/app.py`): discovery, one route per
command, one error shape.

```bash
curl http://127.0.0.1:8080/api/commands                      # what you may run
curl -X POST http://127.0.0.1:8080/api/commands/system.health
curl -H 'Authorization: Bearer dev:u-siti' http://127.0.0.1:8080/api/commands/user.me
```

The caller comes from the `Authorization` header only: a Firebase ID token, a dev token
(`dev:<uid>`, admin with `dev:admin`) or an admin API token (`ck_…`, hashed in `api_tokens/`).

Admin tokens let Claude and scripts run commands on the server without cloud credentials:

```bash
export CENDEKIARA_TOKEN=ck_…            # from token.create, shown once
cendekiara run system.health --remote https://cendekiara.com
```

See [`docs/03-commands.md`](docs/03-commands.md) for the API contract, the error codes and the
token commands.
