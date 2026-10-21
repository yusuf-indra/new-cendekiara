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
`[{"name","summary","queued","adminOnly","allowJobs","readonly","public","inputSchema","outputSchema"}]`
(only what the caller may run). The frontend's TypeScript types are
generated from this list (`make schema`).

Job run output (`--json`): `{"id","ok","steps":[{"command","ok","result"|"error","seconds"}]}`,
exit code 0/1 — same contract as Mirey, so the opencode-mcp job tool can be
generalised to this app.

## Errors

Raise `AppError(code, message, hint=None)`. Codes and HTTP statuses live in
`core/errors.py` (`invalid_args` 422, `not_found` 404, `login_required` 401,
`admin_only` 404, `conflict` 409, `deadline_passed` 409, `quota_exceeded` 402).
API body: `{"error": {"code", "message", "hint"}}`.

## Domains (planned; add rows as commands are built)

| Domain | Examples |
| --- | --- |
| `system` | `system.health` |
| `user` | `user.me`, `user.set_language`, `user.update_profile` |
| `catalog` | `catalog.categories`, `catalog.exam`, `catalog.tests` (public, cached) |
| `attempt` | `attempt.start`, `attempt.save`, `attempt.submit`, `attempt.pause`, `attempt.resume`, `attempt.get`, `attempt.history` |
| `practice` | `practice.build` (from bank: section, topics, difficulty, count, timer) |
| `study` | `study.next`, `study.check` (server-graded) |
| `item` | `item.create`, `item.update`, `item.import` (queued), `item.validate`, `item.retire`, `item.public_get` (public), `item.mark`, `item.report` |
| `family` · `test` · `bank` | `family.*`, `test.create/update/publish`, `bank.assemble`, `bank.export` |
| `ai` | `ai.generate_items` (queued), `ai.validate_items` (queued) |
| `stats` · `leaderboard` | `stats.items` (admin), `stats.card` (public), `leaderboard.get` |
| `article` | `article.create/update/publish`, `article.public_get` |
| `job` · `token` | `job.get`, `token.create/revoke` (admin, `allow_jobs=False`) |
