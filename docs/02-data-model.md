# 02 — Data model (Firestore)

All documents are pydantic models (`cendekiara.core.models` or the plugin
that owns them), stored with camelCase keys. Commands read/write them only
through `cendekiara.core.store`. Firestore security rules deny every client
read and write: the backend (Admin SDK) is the only writer and reader.

Conventions: ids are lowercase-with-dashes (`tpa-k-0101`) or Firestore auto
ids; timestamps are ISO-8601 UTC strings set by the server (`createdAt`,
`updatedAt`); every content document has `sites: ["id"]` (missing = `["id"]`).

## Collections

| Collection | Holds | Written by |
| --- | --- | --- |
| `users/{uid}` | profile: email, displayName, nickname, `lang` (id/en), `leaderboardOptOut` | `user.*` |
| `items/{itemId}` | one question unit: 1 TPA question, or 1 IELTS passage/recording with its question groups. **No answers.** | `item.*` (admin) |
| `item_keys/{itemId}` | answers, explanations, transcripts, `aiCheck`. **Server only, never sent before submit.** | `item.*` (admin) |
| `families/{familyId}` | near-identical questions: name, `method` (shared solution), optional video link | `family.*` |
| `tests/{testId}` | a package: exam, sections → `itemIds`, duration, `free`, `wrongPenalty`, status | `test.*` (admin) |
| `attempts/{attemptId}` | uid, testId or embedded practice package, mode, answers, timings, flags, deadline, status, result | `attempt.*` |
| `question_stats/{questionId}` | increments from Exam mode: count, correct, blank, flagged, time histogram, option picks, discrimination data | worker after `attempt.submit` |
| `leaderboard/{testId}__{uid}` | first Exam attempt per package: score, week, month, display name | worker |
| `articles/{slug}` | blog: lang, title, markdown body, `math`, `sites`, status | `article.*` (admin) |
| `item_marks/{uid}__{itemId}` | like / saved | `item.mark` |
| `item_reports/{id}` | user reports on a question | `item.report`, `report.*` (admin) |
| `jobs/{jobId}` | queued command: name, args, actor, status, result/error, timings | core/jobs |
| `api_tokens/{tokenHash}` | admin API tokens (hash only), label, lastUsedAt | `token.*` (admin) |
| `ledger/{entryId}` (later) | every credit/plan change from any channel | `billing.*` (Phase 10) |

## Item (shared by all exams)

```jsonc
{
  "id": "tpa-k-0101",
  "exam": "tpa-bappenas",          // exam plugin id
  "section": "kuantitatif",        // from the exam's taxonomy
  "familyId": "fam-deret-selisih-bertingkat",   // optional
  "tags": ["deret"],
  "difficulty": 3,                 // 1–5 author estimate
  "targetTimeSec": 60,
  "status": "active",              // draft | review | active | retired
  "usage": {"exam": true, "practice": true, "study": false},
  "sites": ["id"],
  "stimulus": null,                // passage {title, paragraphs[{label,text}]} | audio {url, ttsFallback} | image
  "groups": [
    {
      "id": "g1",
      "type": "choice",            // question-type plugin id (docs/04-exams.md)
      "topic": "deret-angka",
      "instructions": "…",
      "options": null,             // group-level options, or per question
      "questions": [
        {"id": "q1", "prompt": "2, 5, 10, 17, …", "options": [{"id": "A", "text": "24"}, …]}
      ]
    }
  ]
}
```

`item_keys/{id}`: `{"answers": {"q1": ["C"]}, "explanations": {"q1": "…"}, "transcript": null, "aiCheck": {…}}`.

Question numbers are **not** stored on items: they are assigned when a
package is assembled (`bank.assemble`), because one item can sit at
different positions in different packages.

## Rules

- An item that is in **any** package with `usage.exam` (including drafts)
  never appears in Study mode or public question cards.
- Only `status: active` items are used anywhere outside admin.
- Content edits by admins are versioned by `updatedAt`; attempts store the
  assembled package snapshot they were taken with, so later edits never
  change old results.
- Migration from the old app: same collection names and item/test shapes
  where possible; differences are listed here when Phase 8 defines the
  migration command.
