# 09 — Public site, SEO and the two sites

## Sites (`backend/cendekiara/sites.py`, chosen with env `SITE`)

| Site | Brand | Languages | Categories |
| --- | --- | --- | --- |
| `id` | Cendekiara (`cendekiara.com`) | id, en | `bahasa-inggris` (IELTS-style), `seleksi-kedinasan` (TPA, CPNS, STAN) |
| `global` | placeholder "Cendekiara Global" | en | `english-tests` (IELTS-style, TOEFL-style), `graduate-admissions` (GMAT-style) |

Exam engine, scoring and bank are shared. Content (tests, items, articles)
has `sites`; missing = `["id"]`. One domain per site, **subfolders, not
subdomains**: one login, one credit balance, one deploy, one SEO authority.

## URLs (site `id`)

| Path | Page |
| --- | --- |
| `/` → `/id/` | home (free packages, sample question cards) |
| `/id/<category>/` | category landing |
| `/id/<exam-id>/` | exam landing (active or coming soon) |
| `/id/blog/`, `/id/blog/<slug>` | articles |
| `/id/soal/<item-id>`, `/en/question/<item-id>` | one public question (study items only) |
| `/sitemap.xml`, `/robots.txt` | generated |
| `/app/…` | SPA (not indexed, `noindex`) |

## Rules

- Pages are server-rendered with Jinja, data from public readonly commands
  in-process. Cache headers: HTML 5 min at the CDN (`s-maxage`), stale-while-revalidate.
- Every page: `<title>`, meta description, canonical, `hreflang` (id/en),
  Open Graph, JSON-LD where it fits (`Article`, `Quiz`/`Question`,
  `BreadcrumbList`). Text through `backend/cendekiara/i18n/{id,en}.json`.
- `INDEXING=off` (default until launch) → `robots.txt` disallow all and
  `X-Robots-Tag: noindex` on every response.
- **Shortcode** in articles: `[soal id="tpa-k-0101"]` on its own line → a
  static card (question + options, **no key**) for SEO, made interactive by
  the card island script. Exam items or missing ids are skipped silently.
- Articles: Markdown with raw HTML disabled; `"math": true` turns formulas
  into `<span class="math">` (escaped) rendered by KaTeX on the client.
- Footer on every page: scores are estimates; not affiliated with the
  owners of IELTS, Bappenas, BKN or PKN STAN.
