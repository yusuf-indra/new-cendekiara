# 08 — Roadmap

Each phase is one or more branches; each ends with `make check` green and
`docs/PROGRESS.md` updated. "Done when" is the acceptance test Claude uses
when reviewing.

| # | Phase | Contents | Done when |
| --- | --- | --- | --- |
| 0 | Skeleton | `core/config.py` (pydantic-settings: `APP_ENV`, `SITE`, `STORE`, `AUTH_MODE`, `JOBS`, `ADMIN_EMAILS`), `core/clock.py`, logging setup, `system.health` command + test, CLI (`cendekiara commands list [--json]`, `cendekiara run <name> --arg k=v`) | both CLI commands work against `STORE=memory`; `make check` green |
| 1 | API + auth | FastAPI app (`api/app.py`): `GET /api/commands`, `POST/GET /api/commands/{name}`, error rendering, `core/auth.py` (Firebase ID token verify; `AUTH_MODE=dev` with `dev:<uid>`, refused unless `APP_ENV=dev`), admin by `ADMIN_EMAILS`, CORS (site URL + Capacitor origin), `user.me`, `user.update_profile`; admin API tokens (`token.create/revoke`, hashed) + `--remote` mode in the CLI | API tests: anonymous vs signed-in vs admin; ownership → 404; token auth works |
| 2 | Firestore + plugins | `core/firestore_store.py` (Admin SDK, behind `Store`), seed loader for memory store, exam plugin loader + `ielts`, `tpa-bappenas`, `cpns-skd`, `pkn-stan`, `toefl`, `gmat`; scoring plugins `scale_200_800`, `ielts_band`; question types `choice`, `select`, `multi`, `text`; `catalog.*` commands | plugin discovery tested; adding a dummy exam in tests needs no core edit |
| 3 | Question bank | item/key/family/test models, `item.validate/create/update/retire`, `item.import` (queued, dry run), `bank.assemble`, `bank.export`; jobs: `core/jobs.py` (inline + Cloud Tasks), `job.get`, `cendekiara jobs run` | seeded IELTS-style and TPA samples import cleanly; keys never in item outputs |
| 4 | Exam engine | `attempt.start/save/submit/get/history`, `attempt.pause/resume` (practice), `practice.build`, `study.next/check`, server deadlines + grace, timings, `wrongPenalty`, results per section | full TPA and IELTS-style sample attempts scored end to end in tests, incl. late submit |
| 5 | App shell | `frontend/` Vite + React + TS, ESLint/Prettier/Vitest in `make check`, `make schema` type generation, Firebase login (dev login on localhost), i18n id/en, routing, dashboard, history, exam room with `cbt` and `split` layouts, QuestionCard | a student can log in (dev), take the TPA sample and see the result on mobile width |
| 6 | Public site | Jinja views: home, category, exam landing, coming-soon pages, blog + `[soal id="…"]` shortcode, question pages `/id/soal/{id}` and `/en/question/{id}`, sitemap, robots, `INDEXING=off`, two sites (`SITE=id|global`), hreflang | render tests pass; no answer key in any public HTML |
| 7 | Admin + AI + stats | admin screens (bank, form, JSON import, packages, articles, reports), `ai.generate_items` + `ai.validate_items` (fake + anthropic), `question_stats`, leaderboard, marks/reports | AI flow works with `AI_PROVIDER=fake`; stats increments tested |
| 8 | Deploy + migration | `firebase.json` (hosting rewrites, `/app/**` SPA fallback), `firestore.rules` (deny all), Dockerfile, GitHub Actions deploy on merge to `main` (Workload Identity, no keys), Secret Manager, migration command from the old app's Firestore; owner decides cut-over | staging deploy works; old data imported in staging; owner approves cut-over |
| 9 | Android | Capacitor config, native Google sign-in, absolute API base, app icons, release build docs | debug APK runs the full TPA flow on a phone |
| 10 | Business + AI scoring | credits, packages, subscriptions, vouchers, promo/referral, ledger, Midtrans (+ Play Billing), Turnstile on sign-up; Writing/Speaking AI scoring, TTS audio | per `11-business.md` |

Until Phase 8 nothing deploys: merging to `main` only runs CI.
