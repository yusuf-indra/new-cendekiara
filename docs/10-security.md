# 10 — Security and legal limits

## Security rules (never break)

1. **Answer keys never go to the browser before submit.** Items and keys are
   separate collections; item outputs are built from the item model only.
   Exceptions (key or explanation may be sent, only for items with
   `usage.study` that are in no exam package): `study.check` results and
   QuestionCard "Cek jawaban" — always graded on the server, one question at
   a time. Tests assert keys never appear in item/attempt-in-progress outputs
   or public HTML.
2. **Only the backend writes.** `firestore.rules` deny all client reads and
   writes. Scores, credits, payments, stats only through commands.
3. **Login everywhere** except `public=True` readonly commands and the SEO
   pages. The uid comes from the verified Firebase ID token (or API token),
   never from request args. Firebase ID tokens are verified with
   `firebase_admin.auth.verify_id_token` (signature + expiry); a token that
   fails verification answers `invalid_token`.
4. **Ownership**: a command loading user data checks `doc.uid == actor uid`;
   otherwise `not_found` (404), never 403.
5. **Admins** = emails in `ADMIN_EMAILS`, checked on the server for every
   `admin_only` command. Admin commands look absent (404) to others.
6. **Destructive commands** (`*.delete`, bulk retire, token create): `admin_only=True`,
   `allow_jobs=False`.
7. **API tokens** (for Claude/scripts): random 32 bytes, shown once, stored as
   SHA-256 hash in `api_tokens/`, admin only, revocable, `lastUsedAt` logged.
   The token is `ck_` + 32 url-safe bytes; a token acts as the admin who
   created it, runs with `via=remote` and may not run commands with
   `allow_jobs=False` (`token.create`, `token.revoke`). The token stores
   `createdByEmail` and re-checks that email on every use: it is refused as
   soon as its owner's email is no longer in `ADMIN_EMAILS`. Tokens are never
   logged and never stored in clear.
8. **Server-enforced time**: answers saved after `deadline + SUBMIT_GRACE_SEC`
   are ignored; the last autosave counts. Timings capped at 3 h per question.
9. **No secrets in the repo.** Secrets in Secret Manager / env vars; deploy
   via Workload Identity Federation (no JSON keys). `.env` is gitignored.
10. **Escaping**: React and Jinja escape text; Markdown with raw HTML off;
    KaTeX with `trust: false`. Never `dangerouslySetInnerHTML` except the
    KaTeX output component.
11. **Dev shortcuts** (`AUTH_MODE=dev`, `AI_PROVIDER=fake`, `STORE=memory`)
    refuse to start unless `APP_ENV=dev`. The API also refuses to start when
    `APP_ENV` was not set explicitly: a forgotten profile is a production
    accident. The remote CLI (`cendekiara run --remote`) builds no profile at
    all: it needs only a token and a URL.
12. **Internal endpoints** (`/internal/*`, worker) require a Cloud Tasks OIDC
    token for the service account; never routed by Firebase Hosting.
13. **CORS**: only the site URL (`SITE_URL`) and the Capacitor origin
    (`CAPACITOR_ORIGIN`), only for `/api/*`. Nothing else gets CORS headers.
14. **Abuse**: Turnstile on sign-up (Phase 10), rate limits on public
    commands and `study.check`.

## Legal limits (mandatory)

- Do not use the "IELTS" logo/brand as a product name. "IELTS-style" is fine.
  Same for TOEFL, GMAT.
- Do not copy questions from Cambridge, British Council, IDP, ETS, GMAC,
  Bappenas, BKN or any book or site. All questions are original (AI-written
  then reviewed).
- Do not copy official band descriptors; rubrics are our own wording.
- Instructions in questions are in our own words.
- The exam room may imitate **functions** (split screen, timer, navigator);
  colours, logo and identity are Cendekiara's.
- Always show that scores are **estimates** and that the product is not
  affiliated with the owners of IELTS, Bappenas, BKN or PKN STAN.
