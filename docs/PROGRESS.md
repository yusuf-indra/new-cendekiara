# PROGRESS — read this first in every new session

Single source of truth for where new Cendekiara is. Keep it short. Every
task that changes code updates this file in the same branch (see AGENTS.md,
Definition of done).

## Now

- **Next step:** plan Phase 0 (skeleton: config, clock, logging,
  `system.health`, CLI `commands list [--json]` + `run`) per
  `docs/08-roadmap.md`. Default free model.
- **Waiting on:** nothing; Claude starts on the next "lanjut".
- **Open branches:** none.
- **Deploys:** none yet. Merging to `main` only runs CI until Phase 8.

Already in the first commit (by Claude, do not redo): `core/registry.py`,
`core/context.py`, `core/errors.py`, `core/models.py`, `core/store.py`
(`Store` + `MemoryStore`), reference command `user.set_language` + test,
`Makefile`, CI, docs.

## Phases

| Phase | Status | Branch / PR | Notes |
| --- | --- | --- | --- |
| 0. Skeleton | not started | — | |
| 1. API + auth | not started | — | |
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

- 2026-10-21 — Rebuild from scratch in `new-cendekiara`; old repo is a functional reference.
- 2026-10-21 — Keep Firebase Hosting + Cloud Run + Firestore + Firebase Auth.
- 2026-10-21 — Public SEO pages server-rendered (FastAPI + Jinja); app behind login = React + Vite + TS SPA; Android = Capacitor wrapping the same SPA.
- 2026-10-21 — Mirey-style command registry: every action and app read is a command; API, CLI, jobs and SEO views are thin. Readonly commands also served by GET; public ones cached at the CDN.
- 2026-10-21 — Worker = Cloud Tasks → `/internal/jobs/run` on the same Cloud Run service; inline thread locally.
- 2026-10-21 — Claude runs app commands through the API with an admin API token (`cendekiara run --remote`), no cloud credentials on the VPS.
- 2026-10-21 — Docs in English for AI coders; talk with the owner in Indonesian.
