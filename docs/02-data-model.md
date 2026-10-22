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
| `attempts/{attemptId}` | uid, testId (a practice attempt gets a generated id), mode, the assembled package snapshot, answers, timings, flags (all keyed by the question number), deadlineAt, status (in_progress/paused/submitted), late (submitted after the deadline + the grace), result (scored only on submit), free, wrongPenalty | `attempt.*` |
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
  "stimulus": null,                // {kind:"passage", title, paragraphs[{label,text}]} | {kind:"audio", url, ttsFallback} | {kind:"image", url}
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

`item_keys/{id}`: `{"id": "<itemId>", "answers": {"q1": ["C"]}, "explanations": {"q1": "…"}, "transcript": null, "aiCheck": {…}}`.
The `stimulus` field is a pydantic discriminated union on `kind`
(`passage` | `audio` | `image`); each variant carries only its own fields.

`families/{familyId}`: `{"id", "name", "method": "…", "videoUrl": null}` —
near-identical questions sharing one solution method.

`tests/{testId}`: `{"id", "exam", "sections": {"<section>": ["<itemId>", …]},
"durationSec": 180, "free": true, "wrongPenalty": 0, "status": "active",
"sites": ["id"]}`. Section order and item order are the display order; question
numbers are assigned on assembly, not stored.

`attempts/{attemptId}`:

```jsonc
{
  "id": "a1b2c3",
  "uid": "u-siti",
  "mode": "exam",                    // exam | practice
  "testId": "tpa-mini",              // the package (a practice attempt gets a generated id)
  "exam": "tpa-bappenas",
  "packageSnapshot": {…},            // the assembled package, as it was taken (never a key)
  "status": "in_progress",           // in_progress | paused | submitted
  "answers": {"1": "B", "7": ["A", "C"]},
  "timings": {"1": 42.5},            // seconds
  "flags": ["1"],                    // the flagged questions
  "deadlineAt": "2026-10-21T12:03:00+00:00",   // absent when the attempt has no timer
  "startedAt": "…", "updatedAt": "…", "pausedAt": null, "submittedAt": null,
  "late": false,                    // submitted after the deadline + the grace
  "free": true,
  "wrongPenalty": 0,
  "durationSec": 180,
  "result": null                     // the score, written on submit
}
```

The answers, the timings and the flags are keyed by the **number** of the
question (the global number the assembly gives it), never by the id of the
question inside its item: that id repeats in every item of a package ("q1" of
every passage), so it cannot identify an answer. A `multi` answer is a list
of option ids; every other answer is a string.

`result` (written on submit): `{"score": 512.0, "scoreType": "number",
"correct": 21, "wrong": 7, "blank": 2, "wrongPenalty": 0.25, "late": false,
"sections": {"kuantitatif": {"correct": 8, "wrong": 3, "blank": 1, "marks": 7.25,
"score": 470.0, "timeSec": 320.5}}}`. The score is always an estimate.

`jobs/{jobId}`: `{"id", "name", "args": {…}, "actor": {"uid", "email"},
"createdBy": "<uid>", "status": "queued|running|done|failed",
"result": {…} | null, "error": {"code","message","hint"} | null, "createdAt",
"startedAt", "finishedAt"}`. The actor stores `{uid, email}` only — never an
admin flag (it is re-checked at run time). `bank.export` stores its result
(items + keys) in `result`, so a large export is bounded by Firestore's 1 MB
document limit.

`api_tokens/{tokenHash}`: `{"id": "<tokenHash>", "label": "laptop", "createdBy": "<uid>",
"createdByEmail": "<email>", "createdAt": "…", "lastUsedAt": "…", "revokedAt": null}`.
The document id is the SHA-256 hash of the token: the token itself (`ck_` + 32
url-safe bytes) is shown once at creation and never stored. `createdByEmail` is
re-checked on every use: the token is refused when that email is no longer an
admin (docs/10-security.md).

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
