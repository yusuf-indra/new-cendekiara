# 03 — Commands

Everything the system does is a command: a class in
`backend/cendekiara/commands/<domain>_<action>.py`, registered with
`@command("domain.action", summary=…, flags…)`, with a pydantic input model
`<Domain><Action>In` and output model `<Domain><Action>Out`. The reference
is `user_set_language.py` and `tests/commands/test_user_set_language.py`.

## Flags

| Flag | Default | Meaning |
| --- | --- | --- |
| `queued` | False | Long work: the call returns `{jobId}` at once; the worker runs it; poll `job.get` |
| `admin_only` | False | Only admins; others get `admin_only` → 404 (the command looks absent) |
| `allow_jobs` | True | May run from a job / remote CLI. Destructive commands set False |
| `readonly` | False | No writes. Also served at `GET /api/commands/{name}?…` |
| `public` | False | No login (readonly only). SEO pages and question cards use these |
| `cache_seconds` | 0 | `Cache-Control` for public GETs (CDN) |

`registry.check_access` enforces login/admin/job rules on every call, from
every entry point. Commands still check **ownership** themselves (load the
document, compare `uid` with `ctx.actor.require_uid()`, else `not_found`).

## Entry points (all thin, no logic)

| Entry | How |
| --- | --- |
| App / admin UI | `POST /api/commands/{name}` JSON body = args; `GET` for readonly |
| SEO pages | `web/` views call `registry.execute` in-process with an anonymous or signed-in actor |
| CLI on a server | `cendekiara run <name> --arg key=value` (actor = system) |
| Claude / scripts | `cendekiara run <name> … --remote https://cendekiara.com` with `CENDEKIARA_TOKEN` (admin API token) — calls the API |
| Jobs | `cendekiara jobs run <file.json>`: `{"steps": [{"command": "...", "args": {...}}]}` |
| Worker | `POST /internal/jobs/run` (Cloud Tasks, OIDC) → `registry.execute` with the stored actor |

Discovery: `GET /api/commands` and `cendekiara commands list --json` return
`[{"name","summary","queued","adminOnly","allowJobs","readonly","public","inputSchema","outputSchema"}]`.
The API returns only what the caller may run: the public commands for an
anonymous caller, everything but the admin commands for a signed-in user, and
everything for an admin. The frontend's TypeScript types are generated from
this list (`make schema`).

Job run output (`--json`): `{"id","ok","steps":[{"command","ok","result"|"error","seconds"}]}`,
exit code 0/1 — same contract as Mirey, so the opencode-mcp job tool can be
generalised to this app.

## Errors

Raise `AppError(code, message, hint=None)`. Codes and HTTP statuses live in
`core/errors.py` (`invalid_args` 422, `not_found` 404, `login_required` 401,
`invalid_token` 401, `admin_only` 404, `method_not_allowed` 405,
`conflict` 409, `deadline_passed` 409, `quota_exceeded` 402).
API body: `{"error": {"code", "message", "hint"}}`.

The CLI prints the same body on stderr and leaves with exit code 1. The
remote CLI adds one code of its own: `remote_error` (the server could not be
reached).

## The API (`api/app.py`)

| Route | What it does |
| --- | --- |
| `GET /api/commands` | The commands the caller may run, with their schemas |
| `POST /api/commands/{name}` | Run a command; the body is the arguments of the command |
| `GET /api/commands/{name}` | Run a readonly command; the query string is the arguments |

- The body of a POST is a JSON object with the arguments of the command
  (`{"lang": "en"}`); an empty body means "no arguments". The query string of
  a GET uses the same names (`?examId=tpa-bappenas`). An unknown argument is
  `invalid_args` (422).
- `GET` is only for readonly commands; anything else is `method_not_allowed`
  (405). An unknown command is `unknown_command` (404). Admin commands look
  absent to everyone else (`admin_only`, 404).
- Arguments are validated with the input model of the command, so the same
  rules apply on every entry point.
- The caller is only known from the `Authorization` header: a Firebase ID
  token, a dev token (`dev:<uid>`, only when `APP_ENV=dev`) or an admin API
  token (`ck_…`). A missing or malformed header is anonymous. A token that
  cannot be verified is `invalid_token` (401).
- Cache headers: a public readonly command with `cache_seconds` is
  `Cache-Control: public, max-age=…`; everything else is `no-store` with
  `Vary: Authorization`. `system.health` is never cached.
- CORS is only on `/api`, and only for `SITE_URL` and `CAPACITOR_ORIGIN`.
- The API refuses to start when `APP_ENV` was not set explicitly, and never
  runs with `AUTH_MODE=dev` outside `APP_ENV=dev`.

## API tokens (`token.*`)

Admin tokens for Claude and scripts, so no cloud credentials live on the
VPS. `token.create` gives a token of `ck_` + 32 url-safe bytes, shown **once**
and stored as its SHA-256 hash in `api_tokens/{hash}` (label, creator uid,
`createdAt`, `lastUsedAt`, `revokedAt`). The token itself is never logged
and never stored. `token.revoke` takes the id of the token or its label; an
unknown token is `not_found`.

A token acts as the admin who created it: it is an admin, it runs commands
with `via=remote` and it may not run commands with `allow_jobs=False`
(`token.create` and `token.revoke` themselves). A revoked or unknown token is
`invalid_token`.

```bash
cendekiara run <name> --arg key=value --remote https://cendekiara.com
```

The token comes from `CENDEKIARA_TOKEN`; without it the CLI stops with exit
code 1. The remote mode needs no store, no auth mode and no cloud
credentials: only the token and the URL.

## Catalog commands (`catalog.*`)

The public, cached, readonly reads the SEO pages and the app use to list what
is available. They expose i18n keys, never brand display strings, and never
answer keys (docs/10-security.md rule 1).

- `catalog.categories` → the categories, each with its exams (`id`, `nameKey`,
  `status`). Categories are derived from the exam plugins.
- `catalog.exam` (`examId`) → one exam's definition: `category`, the scoring
  and layout plugin ids, `contentLang`, `features`, `status`, `sites`, and
  `sections` (`id`, `nameKey`, topic slugs). Unknown `examId` → `not_found`.

`catalog.tests` (the packages of an exam) is deferred to Phase 3, together
with the `tests/` documents it reads.

## Domains (planned; add rows as commands are built)

| Domain | Examples |
| --- | --- |
| `system` | `system.health` |
| `user` | `user.me`, `user.set_language`, `user.update_profile` |
| `catalog` | `catalog.categories`, `catalog.exam` (Phase 2); `catalog.tests` (Phase 3) — public, cached |
| `attempt` | `attempt.start`, `attempt.save`, `attempt.submit`, `attempt.pause`, `attempt.resume`, `attempt.get`, `attempt.history` |
| `practice` | `practice.build` (from bank: section, topics, difficulty, count, timer) |
| `study` | `study.next`, `study.check` (server-graded) |
| `item` | `item.create`, `item.update`, `item.import` (queued), `item.validate`, `item.retire`, `item.public_get` (public), `item.mark`, `item.report` |
| `family` · `test` · `bank` | `family.*`, `test.create/update/publish`, `bank.assemble`, `bank.export` |
| `ai` | `ai.generate_items` (queued), `ai.validate_items` (queued) |
| `stats` · `leaderboard` | `stats.items` (admin), `stats.card` (public), `leaderboard.get` |
| `article` | `article.create/update/publish`, `article.public_get` |
| `job` · `token` | `job.get`, `token.create/revoke` (admin, `allow_jobs=False`) |
