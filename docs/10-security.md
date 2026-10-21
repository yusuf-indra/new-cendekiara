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
   never from request args.
4. **Ownership**: a command loading user data checks `doc.uid == actor uid`;
   otherwise `not_found` (404), never 403.
5. **Admins** = emails in `ADMIN_EMAILS`, checked on the server for every
   `admin_only` command. Admin commands look absent (404) to others.
6. **Destructive commands** (`*.delete`, bulk retire, token create): `admin_only=True`,
   `allow_jobs=False`.
7. **API tokens** (for Claude/scripts): random 32 bytes, shown once, stored as
   SHA-256 hash in `api_tokens/`, admin only, revocable, `lastUsedAt` logged.
8. **Server-enforced time**: answers saved after `deadline + SUBMIT_GRACE_SEC`
   are ignored; the last autosave counts. Timings capped at 3 h per question.
9. **No secrets in the repo.** Secrets in Secret Manager / env vars; deploy
   via Workload Identity Federation (no JSON keys). `.env` is gitignored.
10. **Escaping**: React and Jinja escape text; Markdown with raw HTML off;
    KaTeX with `trust: false`. Never `dangerouslySetInnerHTML` except the
    KaTeX output component.
11. **Dev shortcuts** (`AUTH_MODE=dev`, `AI_PROVIDER=fake`, `STORE=memory`)
    refuse to start unless `APP_ENV=dev`.
12. **Internal endpoints** (`/internal/*`, worker) require a Cloud Tasks OIDC
    token for the service account; never routed by Firebase Hosting.
13. **CORS**: only the site URL and the Capacitor origin, only for `/api/*`.
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
