# 05 — Question bank and authoring

## Terms

| Term | Meaning | Collection |
| --- | --- | --- |
| Item | smallest unit shown together: 1 TPA question, or 1 IELTS passage/recording with its groups | `items/` |
| Item key | answers, explanations, transcripts — server only | `item_keys/` |
| Family | near-identical questions (numbers/words differ); shares a `method` | `families/` |
| Package (test) | sections listing `itemIds`; numbers assigned on assembly | `tests/` |

Classification: exam → section → topic (exam plugin taxonomy), free `tags`,
`familyId`, `difficulty` 1–5 (later replaced by measured difficulty),
`targetTimeSec`. Lifecycle `draft → review → active → retired`; `usage`
says which modes may show the item.

## Three ways to add questions — one validation path

All three end in `item.validate` (pydantic models of the exam plugin and
question-type plugins, taxonomy check, LaTeX only if the exam has `math`,
options/answers consistent, family exists).

1. **Form** in the admin (single multiple-choice question with live preview
   incl. LaTeX; other types edited as JSON with a schema-aware editor).
2. **JSON import** (`item.import`, queued): dry run first (report per item),
   then save all. Format = the item model in `02-data-model.md`.
3. **AI** (`ai.generate_items`, queued): a generator model writes original
   questions for a given exam/section/topic/difficulty/count → a second model
   solves them without the key (`ai.validate_items`) → items whose answer
   differs are flagged → admin picks which to save (default status `review`).
   The check result (`aiCheck`) is stored in `item_keys` because it contains
   answers.

## AI layer

`backend/cendekiara/services/ai/`: provider-agnostic interface
(`generate(prompt, schema) -> model`), providers `anthropic` (default),
others later, and `fake` for dev/tests (`APP_ENV=dev` only). Settings:
`AI_PROVIDER`, `AI_MODEL_GENERATE`, `AI_MODEL_VALIDATE`. API keys from
Secret Manager (`anthropic-api-key`), never in the repo. Prompts are
versioned files in `services/ai/prompts/` and must instruct: original
content only, own wording for instructions, no copying from official or
published materials.

## Stats

From Exam mode only, as increments (`question_stats/{questionId}`): count,
correct, blank, flagged, time histogram, chosen options, discrimination
index data. Considered reliable after 30 answers. Question cards show stats
aggregated over the whole family (`stats.card`), in Practice and Study only,
never in Exam.
