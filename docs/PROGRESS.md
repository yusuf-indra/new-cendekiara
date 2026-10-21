# PROGRESS — read this first in every new session

Single source of truth for where new Cendekiara is. Keep it short. Every
task that changes code updates this file in the same branch (see AGENTS.md,
Definition of done).

## Now

- **Next step:** Phase 5 (frontend); continue from Phase 4 work.
- **Waiting on:** nothing.
- **Open branches:** `feat/phase-4-exam-engine` (Phase 4, in review).
- **Deploys:** none yet. Merging to `main` only runs CI until Phase 8.
- **Follow-up:** `system.health` reads the global settings; move to
  `ctx.settings` (a half-done attempt is in `git stash` on the VPS, may be
  dropped).
- **Follow-up:** Jobs: Cloud Tasks may deliver a job twice; make the
  queued→running switch atomic (Firestore transaction / precondition) before
  production (Phase 8).
- **Follow-up:** Rate limits are per Cloud Run instance; add a shared limiter before production (Phase 8).

Already in the first commit (by Claude, do not redo): `core/registry.py`,
`core/context.py`, `core/errors.py`, `core/models.py`, `core/store.py`
(`Store` + `MemoryStore`), reference command `user.set_language` + test,
`Makefile`, CI, docs.

Phase 1 added: `api/app.py` (FastAPI: discovery, `POST`/`GET
/api/commands/{name}`, error rendering, cache headers, CORS on `/api`),
`core/auth.py` (Firebase ID token, dev token `dev:<uid>`, admin API tokens
`ck_…` hashed in `api_tokens/`), `core/remote.py` (`cendekiara run
--remote`), the commands `user.me`, `user.update_profile`, `token.create`,
`token.revoke`.

Phase 2 added: `core/firestore_store.py` (Admin SDK behind `Store`, lazy,
injectable client), `seed/` (one JSON per collection) + `load_seed()` feeding
`build_store("memory")`, `core/plugins.py` (exam/scoring/qtype discovery),
the exams `ielts`, `tpa-bappenas`, `cpns-skd`, `pkn-stan`, `toefl`, `gmat`,
the scoring methods `scale_200_800` and `ielts_band`, the question types
`choice`, `select`, `multi`, `text`, and the commands `catalog.categories`
and `catalog.exam`.

Phase 3 added: `core/items.py` (item/key/family/test models + the single
validation path `validate_item`), `core/assemble.py` (`assemble_test`, the
function Phase 4 `attempt.start` calls), `core/jobs.py` (the job document,
inline-thread and Cloud Tasks dispatch, the worker `run_job`, the OIDC
`verify_worker_token`), `seed/items.json` + `item_keys.json` + `tests.json`
(original sample questions), the commands `item.validate/create/update/retire`,
`item.import` (queued, dry run), `bank.assemble`, `bank.export` (queued),
`job.get`, `catalog.tests`, the worker endpoint `/internal/jobs/run`, and the
CLI `cendekiara jobs run`.

## Phases

| Phase | Status | Branch / PR | Notes |
| --- | --- | --- | --- |
| 0. Skeleton | merged | PR #1 | config, clock, logging, `system.health`, CLI (`commands list [--json]`, `run --arg k=v`); `make check` green |
| 1. API + auth | merged | PR #2 | FastAPI app, `core/auth.py` (dev + Firebase + API tokens), `user.me`, `user.update_profile`, `token.create/revoke`, `run --remote` |
| 2. Firestore + plugins | merged | PR #3 | Firestore store, seed loader, plugin discovery, 6 exams, 2 scoring methods, 4 question types, `catalog.categories`/`catalog.exam` |
| 3. Question bank | merged | PR #4 | item/key/family/test models + validation, `item.validate/create/update/retire`, `item.import` (queued, dry run), `bank.assemble`/`bank.export`, jobs (`core/jobs.py`, `job.get`, `jobs run`), `catalog.tests` |
| 4. Exam engine | in review | `feat/phase-4-exam-engine` | `attempt.start/save/submit/get/history`, `attempt.pause/resume`, `practice.build`, `study.next/check`, server deadlines + grace, timings, `wrongPenalty`, per-section results |
| 5. App shell (React SPA) | not started | — | |
| 6. Public site (SEO) | not started | — | |
| 7. Admin + AI + stats | not started | — | |
| 8. Deploy + migration | not started | — | owner decides Firebase project and cut-over from the old app |
| 9. Android (Capacitor) | not started | — | |
| 10. Business + AI scoring | not started | — | |

Status words: `not started`, `plan ready`, `building`, `in review`,
`merged`, `blocked`.

## How work gets done (for Claude)

The owner only says "lanjut" / "cek status" / "merge". Claude runs the loop:

1. Read this file (`repo_read_file("new-cendekiara", "docs/PROGRESS.md")`).
2. Start opencode in **plan** mode for the next step:
   `opencode_start(repo="new-cendekiara", mode="plan", task="Phase N … per docs/08-roadmap.md, follow AGENTS.md")`.
3. Claude reviews the plan itself against `docs/08-roadmap.md`, the area
   docs and `AGENTS.md` (security and legal rules first). Fits → build:
   `opencode_build(run_id, branch="feat/phase-N-<name>")`. Otherwise
   `opencode_reply` with corrections. Ask the owner only for decisions the
   docs do not answer (scope, costs, deleting data, deploy/cut-over).
4. Do not poll in a loop. After starting, end the turn; check again when the
   owner writes.
5. Review the result (commits, diff stat, `make check` via `vps_run`). Fix
   via `opencode_reply` until it passes and follows AGENTS.md.
6. Merge with the owner's approval: `vps_run_approved`
   `gh pr create --fill --base main`, `vps_run` `gh pr checks <n>`, then
   `vps_run_approved` `gh pr merge <n> --merge --delete-branch`,
   `vps_run_approved` `git checkout main`, `vps_run` `git pull`
   (cwd `/home/talantan/projects/new-cendekiara`). Update the table and "Now".

## Choosing the model

| Situation | Model |
| --- | --- |
| Default: plans and normal builds | none given → `opencode/big-pickle` (server falls back automatically on quota) |
| Same task fails twice (checks red after 2 fix rounds, rules ignored, loops) | `model="deepseek/deepseek-v4-pro"` |
| DeepSeek V4 Pro also stuck | `model="minimax/MiniMax-M3"` |
| Hard or risky work (auth/security, exam scoring, payments, migration) | may start with `deepseek/deepseek-v4-pro` |
| Small edits, docs, i18n text | free models only |

Paid models cost money: back to the default for the next task. Note the
model used in the run summary.

Balances: MiniMax and DeepSeek ran out on 2026-10-21 and the server does
**not** fall back automatically on `insufficient balance` (only on quota), so
avoid `minimax/MiniMax-M3` and `deepseek/deepseek-v4-pro` until they are
topped up. The `opencode/*` free models still work.

## Infrastructure

| Thing | Where |
| --- | --- |
| Code repo | `yusuf-indra/new-cendekiara` (private) → VPS `/home/talantan/projects/new-cendekiara` |
| Old app (reference only, still in production) | `yusuf-indra/Cendekiara` |
| opencode MCP | `opencode.mireystudio.com` (systemd `opencode-mcp`) |
| Production (later) | Firebase Hosting + Cloud Run + Firestore, domain `cendekiara.com` (Cloudflare) |

## Decisions log (newest first)

- 2026-10-22 — Phase 4 (exam engine): admins may read any attempt (`attempt.get`) for support but may not save/submit/pause/resume another user's attempt (→ `not_found` to avoid revealing existence); acting uid logged on admin reads. Server time only; `attempt.save` after `deadline + SUBMIT_GRACE_SEC` refused, `attempt.submit` grades only stored answers (may take final timings). Submitted attempts immutable. Keys/explanations/transcripts/aiCheck never in in-progress outputs/history. `practice.build` and `study.next` only use items not referenced by any `tests/` document; `study.check` on an exam-package item → `not_found`. Rate/size limits on `attempt.save` and `study.check` (in-memory). Practice has no timer by default, same package repeatable, `attempt.save` merges answers/timings/flags, `free` stored, no entitlement until Phase 10.
- 2026-10-21 — Tests: the job queue never starts a thread in the test
  suite: `tests/conftest.py` replaces `jobs._dispatch` (`no_background_dispatch`,
  autouse), so a test that runs the job itself (`jobs.run_job`) cannot race the
  inline worker and read the job while it still runs. The inline thread stays
  covered by one test that asks for the real dispatcher (`real_dispatch`) and
  waits for the job to finish. The production behaviour is unchanged.

- 2026-10-21 — Jobs: unexpected errors fail the job with `internal_error`;
  Cloud Tasks OIDC audience is `WORKER_URL`. A job always ends (`done` or
  `failed`): a bad stored argument fails with `invalid_args`, a bug in a
  command with `internal_error` — the traceback stays in the server log, the
  job document holds neither a traceback nor the argument values. The Cloud
  Tasks task sets the OIDC audience explicitly, or Cloud Tasks would use the
  task URL (`WORKER_URL/internal/jobs/run`) and every worker call would be
  rejected.

- 2026-10-21 — Phase 3 (question bank): `item.import` runs in the worker as a
  dry run by default; a non-dry-run saves every valid item (upsert) and
  reports the invalid ones without failing. `bank.export` stores its
  result (items + keys) in the job `result`, so a large bank is bounded by
  Firestore's 1 MB document limit. `item.retire` retires a single item and
  keeps `allow_jobs=True` (bulk retire stays a destructive Phase 7 command).
  `item.update` is a full replace; the key is optional and, when given,
  replaces the stored key. `Stimulus` is a discriminated union on `kind`
  (`passage` | `audio` | `image`). Security decisions A–D (job actor
  re-checks admin at run time, `job.get` ownership, `bank.assemble` is an
  admin-only preview over `core/assemble.py`, the `/internal/jobs/run` OIDC
  guard) are recorded in `docs/10-security.md`.
- 2026-10-21 — Phase 2: exams are discovered as subpackages of `cendekiara.exams` (folder in snake_case, `EXAM.id` is the dashed slug); scoring methods and question types register with `@scoring` / `@qtype`; adding a plugin never edits core code. `catalog.tests` is deferred to Phase 3. Coming-soon exams use placeholder section names (cpns-skd → twk/tiu/tkp) and forward-looking scoring ids where the method is not built yet.
- 2026-10-21 — Phase 2: exam categories are two slugs for now, `english` and `seleksi-kedinasan`; the per-site slugs of docs/09 (`bahasa-inggris`, `english-tests`, `graduate-admissions`) are reconciled when the public site (Phase 6) maps them.
- 2026-10-21 — API tokens re-check the creator's admin email on every use; Firebase tokens verified with verify_id_token.
- 2026-10-21 — Phase 1: an API token acts as the admin who created it (uid of the creator, admin, `via=remote`) and may not run commands with `allow_jobs=False` (`token.create`, `token.revoke`); the token format is `ck_` + 32 url-safe bytes, stored as its SHA-256 hash only; the remote CLI builds no local profile at all (no store, no auth mode): it needs only `CENDEKIARA_TOKEN` and the URL.
- 2026-10-21 — Phase 1: the API refuses to start when `APP_ENV` was not set explicitly, and the settings are built on first use, not on import, so the remote CLI never validates a profile it does not use.
- 2026-10-21 — Phase 0: settings default to the dev profile; APP_ENV=prod requires STORE=firestore + AUTH_MODE=firebase; system.health is public but hides env/store from anonymous callers; ADMIN_EMAILS is comma-separated.
- 2026-10-21 — Rebuild from scratch in `new-cendekiara`; old repo is a functional reference.
- 2026-10-21 — Keep Firebase Hosting + Cloud Run + Firestore + Firebase Auth.
- 2026-10-21 — Public SEO pages server-rendered (FastAPI + Jinja); app behind login = React + Vite + TS SPA; Android = Capacitor wrapping the same SPA.
- 2026-10-21 — Mirey-style command registry: every action and app read is a command; API, CLI, jobs and SEO views are thin. Readonly commands also served by GET; public ones cached at the CDN.
- 2026-10-21 — Worker = Cloud Tasks → `/internal/jobs/run` on the same Cloud Run service; inline thread locally.
- 2026-10-21 — Claude runs app commands through the API with an admin API token (`cendekiara run --remote`), no cloud credentials on the VPS.
- 2026-10-21 — Docs in English for AI coders; talk with the owner in Indonesian.
