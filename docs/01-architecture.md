# 01 — Architecture

## Product in one paragraph

Cendekiara is a practice-test platform grouped by category: English tests
(IELTS-style: Listening, Reading, Writing, Speaking), civil-service selection
(TPA Bappenas 200–800, CPNS SKD, PKN STAN) and later more (TOEFL-style,
GMAT-style, UTBK). Students take full **exams**, build **practice** sets from
the question bank, and **study** one question at a time with instant
checking. Admins author questions (form, JSON import, AI generator + AI
validator), assemble packages, write blog articles and read item stats. Two
sites come from one codebase: `id` (Cendekiara, Indonesian + English) and
`global` (English). Android app via Capacitor. Old repo
`yusuf-indra/Cendekiara` is the functional reference; this repo is a
redesign, not a copy.

## Components

```
                    Firebase Hosting (CDN, cendekiara.com)
     ┌──────────────────────────┬──────────────────────────────────────┐
     │ /app/**  static SPA      │ /, /id/**, /en/**, /sitemap.xml,      │
     │ (frontend/dist)          │ /robots.txt, /api/**  → Cloud Run     │
     └────────────┬─────────────┴────────────────┬─────────────────────┘
                  │ fetch /api/commands/*        │
   Android app ───┘ (Capacitor, same SPA)        ▼
                                   Cloud Run service "api" (FastAPI, Python 3.12)
                                   ├── api/      JSON API: /api/commands/{name}
                                   ├── web/      SEO pages (Jinja2, server-rendered, CDN cached)
                                   ├── commands/ every action and app read
                                   ├── exams/ scoring/ qtypes/   plugins
                                   ├── services/ AI, TTS, payments, mail (behind interfaces + fakes)
                                   └── core/     registry, context, store, config, auth
                                   Cloud Tasks ──► /internal/jobs/run (same service) = worker
     Firestore · Firebase Auth · Cloud Storage (audio, images) · Secret Manager
```

- **One backend app** (FastAPI) serves the JSON API, the SEO pages and the
  worker endpoint. Same container, same code, same commands.
- **SEO pages are server-rendered** by Jinja (`backend/cendekiara/web/`):
  home, category, exam landing, blog, per-question pages, sitemap, robots.
  They call commands in-process, never HTTP. Cached at the CDN.
- **The app behind login is a React + Vite + TypeScript SPA**
  (`frontend/`), served as static files under `/app/`. It is also the
  Android app (Capacitor wraps `frontend/dist`). No SEO needed there.
- **Firebase Auth** signs users in (Google, email). The SPA sends the ID
  token as `Authorization: Bearer`; the backend verifies it and builds the
  `Actor`. Admins = emails in `ADMIN_EMAILS`.
- **Worker**: queued commands become a `jobs/{id}` document plus a Cloud
  Tasks task that calls `POST /internal/jobs/run` (OIDC-authenticated,
  not public). Locally (`JOBS=inline`) jobs run in a background thread.
  Cloud Run request timeout 600 s; Firebase Hosting cuts proxied requests at
  60 s, so nothing user-facing waits on a job: the SPA polls `job.get`.
- **Claude / scripts** run commands through the same API with an admin API
  token (`cendekiara run --remote …`), so no cloud credentials live on the
  VPS. See `03-commands.md`.

## Request flow (app)

1. SPA → `POST /api/commands/attempt.submit` with token and JSON args.
2. `api/` verifies the token → `Actor`, builds `Context(actor, store, site)`.
3. `registry.execute` checks login/admin/job rules, validates args with the
   command's input model, runs it, returns the output model as JSON.
4. Errors are `AppError(code, message, hint)` → JSON `{error: {...}}` with
   the status from `core/errors.HTTP_STATUS`.

## Local development

No cloud needed: `STORE=memory` (seeded from `backend/cendekiara/seed/`),
`AUTH_MODE=dev` (token `dev:<uid>`, admin if `dev:admin`), `AI_PROVIDER=fake`,
`JOBS=inline`. `AUTH_MODE=dev` and `AI_PROVIDER=fake` are refused unless
`APP_ENV=dev`. `make dev` runs the backend on :8080 and Vite on :5173
(proxying `/api`).

## Folder layout

```
backend/
  cendekiara/
    core/        registry, context, errors, models, store (+ firestore_store), config, auth, jobs
    commands/    <domain>_<action>.py — one per command
    exams/       <exam-id>/  exam definition plugins
    scoring/     <method>.py scoring plugins
    qtypes/      <type>.py question-type plugins (model + grading)
    services/    ai/, tts/, payments/, mail/ — interface + real + fake
    api/         FastAPI app, thin routes
    web/         Jinja views + templates for SEO pages
    i18n/        id.json, en.json for public pages
    seed/        sample data for STORE=memory
    cli.py       `cendekiara` CLI
  tests/
frontend/        React + Vite + TS SPA (+ capacitor.config.ts, android/)
docs/
firebase.json, firestore.rules (deny all client access), .github/workflows/
```
