# PROGRESS — read this first in every new session

Single source of truth for where new Cendekiara is. Keep it short. Every
task that changes code updates this file in the same branch (see AGENTS.md,
Definition of done).

## Now

- **Next step:** Phase 2 (Firestore + plugins): `core/firestore_store.py`
  (Admin SDK behind `Store`), the seed loader for the memory store, the
  exam plugin loader (`ielts`, `tpa-bappenas`, `cpns-skd`, `pkn-stan`,
  `toefl`, `gmat`), the scoring plugins (`scale_200_800`, `ielts_band`),
  the question types (`choice`, `select`, `multi`, `text`) and the
  `catalog.*` commands. Adding a dummy exam in the tests must need no
  edit in the core.
- **Waiting on:** nothing; Claude starts on the next "lanjut".
- **Open branches:** `feat/phase-1-api-auth` (Phase 1, in review).
- **Deploys:** none yet. Merging to `main` only runs CI until Phase 8.

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

## Phases

| Phase | Status | Branch / PR | Notes |
| --- | --- | --- | --- |
| 0. Skeleton | merged | PR #1 | config, clock, logging, `system.health`, CLI (`commands list [--json]`, `run --arg k=v`); `make check` green |
| 1. API + auth | in review | `feat/phase-1-api-auth` | FastAPI app, `core/auth.py` (dev + Firebase + API tokens), `user.me`, `user.update_profile`, `token.create/revoke`, `run --remote` |
| 2. Firestore + plugins | not started | — | |
| 3. Question bank | not started | — | |
| 4. Exam engine | not started | — | |
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

## Infrastructure

| Thing | Where |
| --- | --- |
| Code repo | `yusuf-indra/new-cendekiara` (private) → VPS `/home/talantan/projects/new-cendekiara` |
| Old app (reference only, still in production) | `yusuf-indra/Cendekiara` |
| opencode MCP | `opencode.mireystudio.com` (systemd `opencode-mcp`) |
| Production (later) | Firebase Hosting + Cloud Run + Firestore, domain `cendekiara.com` (Cloudflare) |

## Decisions log (newest first)

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
