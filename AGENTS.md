# AGENTS.md — rules for any AI (or human) writing code in this repo

Read this file first, then `docs/PROGRESS.md` (where the project is now),
then the doc for the area you touch. These rules are binding. If a rule
blocks you, stop and ask; do not invent a new pattern.

## Read before coding

| You are working on | Read |
| --- | --- |
| Anything | `docs/01-architecture.md`, `docs/07-coding-standards.md` |
| Firestore documents, a new field | `docs/02-data-model.md` |
| An action, a read, an API endpoint, a CLI command | `docs/03-commands.md` |
| A new test type, section, scoring, question type, layout | `docs/04-exams.md` |
| Questions, families, packages, authoring, AI generation | `docs/05-question-bank.md` |
| The app (React SPA) or Android | `docs/06-frontend.md` |
| Public pages, blog, sitemap, the two sites | `docs/09-seo-and-sites.md` |
| Login, admin, anything public, answer keys | `docs/10-security.md` |
| Credits, payments, vouchers | `docs/11-business.md` |

## The rules

1. **Every action is a command.** A button in the app, an admin action, a CLI
   call and a job all run the same command in `backend/cendekiara/commands/`.
   Reads the app needs are commands too (`readonly=True`). No logic in API
   routes, Jinja views, React components or scripts.
2. **One command = one file**, named `<domain>_<action>.py`, registered with
   `@command("domain.action")`. Copy `commands/user_set_language.py` and its
   test.
3. **Data goes through the store.** Read and write Firestore only through
   `cendekiara.core.store` (`Store`, `load`, `save`). Never import the
   Firestore SDK outside `core/firestore_store.py`. Every document shape is a
   pydantic model in `docs/02-data-model.md`.
4. **Answer keys never reach the browser before submit.** Questions live in
   `items/`, answers/explanations/transcripts in `item_keys/`. Scoring runs
   only on the server. The only exceptions are listed in `docs/10-security.md`.
5. **Exams, scoring methods, question types and exam layouts are plugins.**
   Adding one means adding a folder/file, not editing core code
   (`docs/04-exams.md`).
6. **Typed everything.** Python: pydantic models + type hints, `mypy --strict`
   clean. TypeScript: `strict: true`, no `any`; API types are generated from
   the command schemas (`make schema`), never written by hand.
7. **The frontend never touches Firestore or a model API.** It calls
   `POST /api/commands/{name}` (and `GET` for readonly commands) with the
   Firebase ID token. Nothing else. Firestore rules deny all client access.
8. **Long work runs in the worker.** A command marked `queued=True` returns a
   job id at once; the worker runs it. Never block an HTTP request > 2 s
   (AI calls, imports, exports, stats rebuilds are queued).
9. **Every command has a test** in `backend/tests/commands/` using the memory
   store fixtures: one happy path, plus login/ownership/validation errors.
   No test, not done. No network in tests.
10. **All UI text goes through i18n** (`id` and `en`), in the app and in the
    public pages. No hard-coded user-facing strings.
11. **Login and ownership on everything.** Commands require login unless
    `public=True` (readonly only). Data owned by someone else answers
    `not_found` (404), never 403. The uid comes from the verified token,
    never from arguments. Destructive commands set `admin_only=True` and
    `allow_jobs=False`.
12. **Legal limits** (`docs/10-security.md`): no "IELTS" brand as product
    name ("IELTS-style" is fine), no copied questions or official band
    descriptors, scores always shown as estimates, no affiliation claims.
13. **Small, focused changes.** One feature per branch
    (`feat/…`, `fix/…`, `chore/…`, `docs/…`, `refactor/…`), never push to
    `main`. Commit message `<area>: <what changed>`.

## Definition of done

- [ ] `make check` passes (ruff, mypy, pytest; eslint, tsc, vitest once `frontend/` exists)
- [ ] New command appears in `cendekiara commands list` (and in `/api/commands` once the API exists)
- [ ] Security rules and legal limits still hold
- [ ] New UI text in both `id` and `en`
- [ ] Docs updated if you added a command domain, exam, question type, field or decision
- [ ] `docs/PROGRESS.md` updated: phase status, branch, next step
- [ ] No secrets, no binaries, no hard-coded URLs, paths or API keys
