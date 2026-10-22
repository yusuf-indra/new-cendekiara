# 04 — Exams, scoring, question types, layouts (plugins)

Four extension points. Each is a folder or file that the core discovers;
adding one never edits core code.

## 0. Discovery and models

`cendekiara.core.plugins` discovers all three backend extension points by
import (`load_all()`):

- **Exams** are subpackages of `cendekiara.exams` (folder in snake_case, e.g.
  `tpa_bappenas/`) each defining `EXAM = ExamDef(id="tpa-bappenas", ...)` —
  the `id` is the dashed URL slug. Accessors: `register_exam`, `get_exam`
  (unknown id → `not_found`), `all_exams`.
- **Scoring methods** are modules in `cendekiara.scoring/` registered with
  `@scoring("scale_200_800")`.
- **Question types** are modules in `cendekiara.qtypes/` registered with
  `@qtype("choice")`.

The plugin interface models also live in `cendekiara.core.plugins`: `ExamDef`,
`RawResult` / `SectionResult`, `TestSpec` / `SectionSpec` (a minimal package
shape the scoring methods read; the full `TestDef` is Phase 4), `Score`,
`Marks` and `Option`.

## 1. Exam plugin — `backend/cendekiara/exams/<exam-id>/__init__.py`

```python
EXAM = ExamDef(
    id="tpa-bappenas",                 # also the URL slug /id/tpa-bappenas/
    category="seleksi-kedinasan",
    scoring="scale_200_800",           # scoring plugin id
    layout="cbt",                      # frontend layout plugin id
    content_lang="id",                 # language of the questions
    features=("math",),                # math = LaTeX on; never for IELTS-style ($ prices)
    status="active",                   # active | coming_soon (landing page only)
    sections={                         # section -> topics (taxonomy)
        "verbal": ("sinonim", "antonim", "analogi", "pengelompokan-kata", "pemahaman-bacaan"),
        "kuantitatif": ("deret-angka", "aritmetika", "aljabar", "perbandingan-kuantitatif",
                        "soal-cerita", "geometri"),
        "penalaran": ("silogisme", "logika-proposisi", "logika-analitis", "deret-huruf",
                      "pola-gambar", "spasial"),
    },
    sites=("id",),
)
```

Texts (names, descriptions, section and topic labels) are i18n keys
`exam.<id>.*`, `section.<id>.<section>`, `topic.<topic>` in both languages.
Exam ids must not collide with top-level paths (`app`, `api`, `assets`,
`blog`, `soal`, `question`, `admin`, `i18n`).

Initial exams (from the old app): `ielts` (IELTS-style, layout `split`,
scoring `ielts_band`, sections listening/reading/writing/speaking),
`tpa-bappenas` (active), `cpns-skd`, `pkn-stan` (coming soon, id site),
`toefl`, `gmat` (coming soon, global site).

## 2. Scoring plugin — `backend/cendekiara/scoring/<method>.py`

```python
@scoring("scale_200_800")
def score(result: RawResult, test: TestDef) -> Score: ...
```

`RawResult` = per-section correct / wrong / blank / marks; `Score` =
`{score, scoreType, sections{...}, correct, wrong, blank}`. `wrongPenalty`
(default 0) is applied by the core before the plugin: every wrong answer costs
`wrongPenalty` marks, so the **marks** of a section (one mark per correct
question, minus the penalty, never below zero) are what a method scores: a
package with a penalty scores lower. Every method's docstring says it is an
**estimate** and how it is computed. Methods:
`scale_200_800` (linear `200 + 600 × marks/total`), `ielts_band` (own estimate
table, short tests scaled to 40), later `cpns_skd` (TWK/TIU 5/0, TKP 1–5,
passing grades), AI rubric scoring for Writing/Speaking.

## 3. Question-type plugin — `backend/cendekiara/qtypes/<type>.py` + `frontend/src/qtypes/<type>/`

Backend: the pydantic model of a group/question of this type, the answer
model, and `grade(question, key, answer) -> Marks`. Frontend: a component
that renders it and returns the answer. Initial types:

| type | Used for | Answer | Key |
| --- | --- | --- | --- |
| `choice` | multiple choice, T/F/NG, Y/N/NG | one option id | `["B"]` |
| `select` | matching via dropdown | one option id | `["D"]` |
| `multi` | choose TWO/THREE | list of ids | `["A","C"]` |
| `text` | completion, short answer (`maxWords`) | free text | all accepted variants |
| `essay` (later) | Writing tasks | text | rubric, AI-scored |
| `speech` (later) | Speaking parts | audio | rubric, STT + AI |

Text matching ignores case, repeated spaces, quotes and trailing
punctuation; any other variant must be in the key.

## 4. Layout plugin — `frontend/src/exam/layouts/<layout>/`

How the exam room looks, sharing one attempt hook (`useAttempt`: start,
autosave every 15 s and on change of question, submit, timings).

- `cbt`: one question per screen, number panel, "Ragu-ragu" flag,
  keys A–E and ←/→.
- `split`: passage or audio on one side, questions on the other, bottom
  navigator (IELTS-style function only; colours, logo and identity are
  Cendekiara's).

## Modes

| Mode | Content | Pause | Stats, progress, leaderboard |
| --- | --- | --- | --- |
| Exam (`exam`) | a package in `tests/` | no | yes |
| Practice (`practice`) | built from the bank: section, topics, difficulty, count, optional timer; package snapshot stored in the attempt | yes | no |
| Study | one item per screen, `study.check` graded on the server | – (not stored) | no |

Practice picks items from different families first; siblings only fill up
the count. Practice uses only the `usage.practice` items, study only the
`usage.study` items; an item flagged for another mode alone is never offered
(it is in no exam package either).

Time per question (`timings`, seconds) is measured in the browser only while
the question is visible and the page is visible, sent with autosave/submit,
capped at 3 h per question by the server. Deadlines are enforced on the
server: an answer saved after `deadline + SUBMIT_GRACE_SEC` is refused; the
server alone decides time (client timestamps are never trusted).

Running out of time is not a dead end: the owner may always submit, and a
submit after the deadline + the grace is graded from the answers that were
saved in time and marked `late: true` (the timings that come with a late
submit are ignored). An attempt that ran out of time is submitted the same
way when the owner reads it (`attempt.get`, `attempt.history`), so the
student sees a result instead of an attempt that stays in progress. A
submitted attempt is immutable.

`wrongPenalty` is applied by the core before/while scoring; results include
per-section breakdowns from scoring plugins.

The answers, the timings and the flags of an attempt are keyed by the
**number** of the question (the global number the assembly gives it), never by
the id of the question inside its item: that id repeats in every item of a
package ("q1" of every passage), so it cannot identify an answer.
