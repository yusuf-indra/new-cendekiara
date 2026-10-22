"""The exam engine: ownership, deadlines, immutability and the key rules.

Every test runs offline with a frozen clock (tests/conftest.py).

The answers are keyed by the number of the question (the global number the
assembly gives it), never by the id of the question inside its item: that id
repeats in every item of a package ("q1" of every passage).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from cendekiara.core import clock, rate_limit, registry
from cendekiara.core.context import Actor, Context
from cendekiara.core.errors import AppError
from tests.item_helpers import make_item, make_key

FROZEN_NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)

# The fields that may never leave the server before the submit (docs/10).
KEY_FIELDS = ("explanation", "explanations", "transcript", "aiCheck", "ai_check")

# The three questions of the test package, with the key of each of them.
NUMBERS = {"kuantitatif": "1", "verbal": "2", "penalaran": "3"}
KEYS = {"tpa-k-0101": "B", "tpa-v-0101": "C", "tpa-p-0101": "A"}


def seed_package(ctx: Context, test_id: str = "tpa-mini", exam: str = "tpa-bappenas") -> str:
    """Put a package and its three items in the store; return the package id."""
    sections = {"kuantitatif": ["tpa-k-0101"], "verbal": ["tpa-v-0101"], "penalaran": ["tpa-p-0101"]}
    ctx.store.set(
        "tests",
        test_id,
        {
            "id": test_id,
            "exam": exam,
            "sections": sections,
            "durationSec": 180,
            "free": True,
            "wrongPenalty": 0,
            "status": "active",
            "sites": ["id"],
        },
    )
    for item_id, answer in KEYS.items():
        if ctx.store.get("items", item_id) is None:
            ctx.store.set("items", item_id, make_item(item_id))
        if ctx.store.get("item_keys", item_id) is None:
            ctx.store.set("item_keys", item_id, make_key(item_id, answer))
    return test_id


def start(ctx: Context, test_id: str = "tpa-mini") -> str:
    """Start an exam attempt; return its id."""
    out = registry.execute("attempt.start", {"test_id": test_id, "mode": "exam"}, ctx)
    return str(out.model_dump(by_alias=True)["attemptId"])


def other_ctx(mem) -> Context:
    """A signed-in student who owns nothing."""
    return Context(Actor(uid="u-other"), mem)


def build_practice(ctx: Context, **args) -> dict:
    """Build a practice set; return its package."""
    payload = registry.execute("practice.build", args or {"count": 2}, ctx)
    return dict(payload.model_dump(by_alias=True)["package"])


def no_keys(payload: object) -> None:
    """The payload holds no key, no explanation, no transcript and no aiCheck."""
    text = json.dumps(payload, default=str)
    for field in KEY_FIELDS:
        assert field not in text


# --- attempt.start ---------------------------------------------------------


def test_attempt_start_returns_the_package_and_the_deadline(ctx: Context) -> None:
    seed_package(ctx)
    out = registry.execute("attempt.start", {"test_id": "tpa-mini", "mode": "exam"}, ctx)
    data = out.model_dump(by_alias=True)
    assert data["attemptId"]
    assert data["exam"] == "tpa-bappenas"
    assert data["status"] == "in_progress"
    assert data["free"] is True
    assert data["deadlineAt"]
    assert data["package"]["sections"][0]["items"][0]["id"] == "tpa-k-0101"
    # The questions carry the number the answers are keyed with.
    question = data["package"]["sections"][0]["items"][0]["groups"][0]["questions"][0]
    assert question["number"] == 1
    no_keys(data)


def test_attempt_start_stores_the_package_snapshot(ctx: Context) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    doc = ctx.store.get("attempts", attempt_id)
    assert doc is not None
    assert doc["uid"] == "u-siti"
    assert doc["mode"] == "exam"
    assert doc["testId"] == "tpa-mini"
    assert doc["status"] == "in_progress"
    assert doc["deadlineAt"]
    assert doc["packageSnapshot"]["sections"]


def test_attempt_start_needs_login(guest_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("attempt.start", {"test_id": "tpa-mini", "mode": "exam"}, guest_ctx)
    assert err.value.code == "login_required"


def test_attempt_start_of_an_unknown_package_is_not_found(ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("attempt.start", {"test_id": "nope", "mode": "exam"}, ctx)
    assert err.value.code == "not_found"


def test_attempt_start_of_a_draft_package_is_not_found(ctx: Context) -> None:
    seed_package(ctx)
    ctx.store.update("tests", "tpa-mini", {"status": "draft"})
    with pytest.raises(AppError) as err:
        registry.execute("attempt.start", {"test_id": "tpa-mini", "mode": "exam"}, ctx)
    assert err.value.code == "not_found"


def test_attempt_start_of_a_malformed_package_is_not_found(ctx: Context) -> None:
    # A package document that does not fit the model is not a package: it must
    # not reach the assembler.
    ctx.store.set(
        "tests",
        "tpa-broken",
        {"id": "tpa-broken", "exam": "tpa-bappenas", "sections": "not-a-dict", "status": "active"},
    )
    with pytest.raises(AppError) as err:
        registry.execute("attempt.start", {"test_id": "tpa-broken", "mode": "exam"}, ctx)
    assert err.value.code == "not_found"


def test_attempt_start_of_a_practice_set(ctx: Context) -> None:
    seed_package(ctx)
    ctx.store.set("items", "practice-1", make_item("practice-1"))
    package = {"exam": "tpa-bappenas", "sections": {"kuantitatif": ["practice-1"]}}
    out = registry.execute("attempt.start", {"mode": "practice", "package": package}, ctx)
    data = out.model_dump(by_alias=True)
    assert data["mode"] == "practice"
    assert data["deadlineAt"] is None  # a practice set has no timer by default
    assert data["package"]["sections"][0]["items"][0]["id"] == "practice-1"


def test_attempt_start_ignores_a_duration_that_is_not_a_number(ctx: Context) -> None:
    ctx.store.set("items", "practice-1", make_item("practice-1"))
    package = {"exam": "tpa-bappenas", "sections": {"kuantitatif": ["practice-1"]}, "durationSec": True}
    out = registry.execute("attempt.start", {"mode": "practice", "package": package}, ctx)
    data = out.model_dump(by_alias=True)
    assert data["durationSec"] is None
    assert data["deadlineAt"] is None


def test_attempt_start_refuses_an_exam_item_in_a_practice_set(ctx: Context) -> None:
    seed_package(ctx)
    package = {"exam": "tpa-bappenas", "sections": {"kuantitatif": ["tpa-k-0101"]}}
    with pytest.raises(AppError) as err:
        registry.execute("attempt.start", {"mode": "practice", "package": package}, ctx)
    assert err.value.code == "invalid_args"


# --- attempt.save ----------------------------------------------------------


def test_attempt_save_merges_answers_and_timings_and_replaces_flags(ctx: Context) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    registry.execute(
        "attempt.save",
        {"attempt_id": attempt_id, "answers": {"1": "B"}, "timings": {"1": 10}, "flags": ["1"]},
        ctx,
    )
    registry.execute(
        "attempt.save",
        {"attempt_id": attempt_id, "answers": {"2": "C"}, "timings": {"2": 20}, "flags": ["2"]},
        ctx,
    )
    doc = ctx.store.get("attempts", attempt_id)
    assert doc is not None
    assert doc["answers"] == {"1": "B", "2": "C"}
    assert doc["timings"] == {"1": 10.0, "2": 20.0}
    assert doc["flags"] == ["2"]  # the flag list is replaced, not merged


def test_attempt_save_keys_the_answers_by_the_question_number(ctx: Context) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    registry.execute("attempt.save", {"attempt_id": attempt_id, "answers": {"3": "A"}}, ctx)
    doc = ctx.store.get("attempts", attempt_id)
    assert doc is not None
    assert doc["answers"] == {"3": "A"}  # "3" is the third question of the package


def test_attempt_save_refuses_an_answer_for_an_unknown_question(ctx: Context) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    with pytest.raises(AppError) as err:
        registry.execute("attempt.save", {"attempt_id": attempt_id, "answers": {"99": "B"}}, ctx)
    assert err.value.code == "invalid_args"


def test_attempt_save_drops_a_flag_of_an_unknown_question(ctx: Context) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    registry.execute(
        "attempt.save", {"attempt_id": attempt_id, "answers": {"1": "B"}, "flags": ["1", "99"]}, ctx
    )
    doc = ctx.store.get("attempts", attempt_id)
    assert doc is not None
    assert doc["flags"] == ["1"]


def test_attempt_save_takes_the_answer_of_a_multi_question_as_a_list(ctx: Context) -> None:
    ctx.store.set("items", "multi-1", make_multi_item("multi-1"))
    ctx.store.set("item_keys", "multi-1", make_multi_key("multi-1"))
    ctx.store.set(
        "tests",
        "multi-mini",
        {
            "id": "multi-mini",
            "exam": "tpa-bappenas",
            "sections": {"kuantitatif": ["multi-1"]},
            "durationSec": 180,
            "free": True,
            "wrongPenalty": 0,
            "status": "active",
            "sites": ["id"],
        },
    )
    attempt_id = start(ctx, "multi-mini")
    registry.execute("attempt.save", {"attempt_id": attempt_id, "answers": {"1": ["A", "C"]}}, ctx)
    doc = ctx.store.get("attempts", attempt_id)
    assert doc is not None
    assert doc["answers"] == {"1": ["A", "C"]}
    result = registry.execute("attempt.submit", {"attempt_id": attempt_id}, ctx).model_dump(by_alias=True)
    assert result["result"]["correct"] == 1


def test_attempt_save_caps_the_time_of_a_question(ctx: Context) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    registry.execute("attempt.save", {"attempt_id": attempt_id, "timings": {"1": 99999}}, ctx)
    doc = ctx.store.get("attempts", attempt_id)
    assert doc is not None
    assert doc["timings"]["1"] == 3 * 3600


def test_attempt_save_needs_the_owner(ctx: Context, admin_ctx: Context, mem) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    for ctx_actor in (other_ctx(mem), admin_ctx):
        with pytest.raises(AppError) as err:
            registry.execute("attempt.save", {"attempt_id": attempt_id, "answers": {"1": "B"}}, ctx_actor)
        assert err.value.code == "not_found"


def test_attempt_save_needs_login(guest_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("attempt.save", {"attempt_id": "x", "answers": {}}, guest_ctx)
    assert err.value.code == "login_required"


def test_attempt_save_is_refused_after_the_deadline_and_the_grace(ctx: Context) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    clock.freeze(FROZEN_NOW + timedelta(seconds=180 + 61))
    with pytest.raises(AppError) as err:
        registry.execute("attempt.save", {"attempt_id": attempt_id, "answers": {"1": "B"}}, ctx)
    assert err.value.code == "deadline_passed"
    clock.freeze(FROZEN_NOW)


def test_attempt_save_is_allowed_inside_the_grace(ctx: Context) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    clock.freeze(FROZEN_NOW + timedelta(seconds=180 + 30))
    out = registry.execute("attempt.save", {"attempt_id": attempt_id, "answers": {"1": "B"}}, ctx)
    assert out.model_dump(by_alias=True)["savedAnswers"] == 1
    clock.freeze(FROZEN_NOW)


def test_attempt_save_refuses_a_too_large_answer(ctx: Context) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    with pytest.raises(AppError) as err:
        registry.execute(
            "attempt.save",
            {"attempt_id": attempt_id, "answers": {"1": "B" * 30000}},
            ctx,
        )
    assert err.value.code == "invalid_args"


def test_attempt_save_is_rate_limited(ctx: Context) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    rate_limit.limiter.reset()
    for _ in range(30):
        registry.execute("attempt.save", {"attempt_id": attempt_id, "answers": {"1": "B"}}, ctx)
    with pytest.raises(AppError) as err:
        registry.execute("attempt.save", {"attempt_id": attempt_id, "answers": {"1": "B"}}, ctx)
    assert err.value.code == "rate_limited"
    rate_limit.limiter.reset()


# --- attempt.submit --------------------------------------------------------


def test_attempt_submit_grades_the_stored_answers(ctx: Context) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    registry.execute("attempt.save", {"attempt_id": attempt_id, "answers": {"1": "B"}}, ctx)
    out = registry.execute("attempt.submit", {"attempt_id": attempt_id}, ctx)
    data = out.model_dump(by_alias=True)
    assert data["status"] == "submitted"
    result = data["result"]
    assert result["correct"] == 1
    assert result["sections"]["kuantitatif"]["correct"] == 1
    assert result["sections"]["kuantitatif"]["score"] == 800.0


def test_attempt_submit_ignores_answers_sent_with_the_submit(ctx: Context) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    registry.execute("attempt.save", {"attempt_id": attempt_id, "answers": {"1": "A"}}, ctx)
    with pytest.raises(AppError) as err:
        registry.execute("attempt.submit", {"attempt_id": attempt_id, "answers": {"1": "B"}}, ctx)
    assert err.value.code == "invalid_args"  # the submit takes no answers


def test_attempt_submit_needs_the_owner(ctx: Context, admin_ctx: Context, mem) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    for ctx_actor in (other_ctx(mem), admin_ctx):
        with pytest.raises(AppError) as err:
            registry.execute("attempt.submit", {"attempt_id": attempt_id}, ctx_actor)
        assert err.value.code == "not_found"


def test_attempt_submit_is_refused_after_the_deadline_and_the_grace(ctx: Context) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    clock.freeze(FROZEN_NOW + timedelta(seconds=180 + 61))
    with pytest.raises(AppError) as err:
        registry.execute("attempt.submit", {"attempt_id": attempt_id}, ctx)
    assert err.value.code == "deadline_passed"
    clock.freeze(FROZEN_NOW)


def test_attempt_submit_after_the_deadline_inside_the_grace_scores(ctx: Context) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    registry.execute("attempt.save", {"attempt_id": attempt_id, "answers": {"1": "B"}}, ctx)
    clock.freeze(FROZEN_NOW + timedelta(seconds=180 + 30))
    out = registry.execute("attempt.submit", {"attempt_id": attempt_id}, ctx)
    assert out.model_dump(by_alias=True)["result"]["correct"] == 1
    clock.freeze(FROZEN_NOW)


def test_a_submitted_attempt_is_immutable(ctx: Context) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    registry.execute("attempt.submit", {"attempt_id": attempt_id}, ctx)
    with pytest.raises(AppError) as err:
        registry.execute("attempt.save", {"attempt_id": attempt_id, "answers": {"1": "B"}}, ctx)
    assert err.value.code == "conflict"
    with pytest.raises(AppError) as err:
        registry.execute("attempt.submit", {"attempt_id": attempt_id}, ctx)
    assert err.value.code == "conflict"
    with pytest.raises(AppError) as err:
        registry.execute("attempt.pause", {"attempt_id": attempt_id}, ctx)
    assert err.value.code == "conflict"
    with pytest.raises(AppError) as err:
        registry.execute("attempt.resume", {"attempt_id": attempt_id}, ctx)
    assert err.value.code == "conflict"


# --- attempt.get and attempt.history ---------------------------------------


def test_attempt_get_is_read_by_the_owner(ctx: Context) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    out = registry.execute("attempt.get", {"attempt_id": attempt_id}, ctx)
    assert out.model_dump(by_alias=True)["attempt"]["id"] == attempt_id


def test_attempt_get_of_another_student_is_not_found(ctx: Context, mem) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    with pytest.raises(AppError) as err:
        registry.execute("attempt.get", {"attempt_id": attempt_id}, other_ctx(mem))
    assert err.value.code == "not_found"


def test_an_admin_may_read_any_attempt(ctx: Context, admin_ctx: Context, caplog) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    with caplog.at_level("INFO"):
        out = registry.execute("attempt.get", {"attempt_id": attempt_id}, admin_ctx)
    assert out.model_dump(by_alias=True)["attempt"]["id"] == attempt_id
    assert attempt_id in caplog.text
    assert "u-admin" in caplog.text


def test_attempt_history_holds_only_the_own_attempts(ctx: Context, mem) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    registry.execute("attempt.submit", {"attempt_id": attempt_id}, ctx)
    start(other_ctx(mem))
    out = registry.execute("attempt.history", {}, ctx)
    rows = out.model_dump(by_alias=True)["attempts"]
    assert [row["id"] for row in rows] == [attempt_id]
    assert rows[0]["score"] is not None
    no_keys(rows)


def test_attempt_history_needs_login(guest_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("attempt.history", {}, guest_ctx)
    assert err.value.code == "login_required"


# --- pause and resume ------------------------------------------------------


def test_pause_and_resume_a_practice_attempt(ctx: Context) -> None:
    seed_package(ctx)
    ctx.store.set("items", "practice-1", make_item("practice-1"))
    package = {"exam": "tpa-bappenas", "sections": {"kuantitatif": ["practice-1"]}}
    out = registry.execute("attempt.start", {"mode": "practice", "package": package}, ctx)
    attempt_id = str(out.model_dump(by_alias=True)["attemptId"])
    paused = registry.execute("attempt.pause", {"attempt_id": attempt_id}, ctx).model_dump()
    assert paused["status"] == "paused"
    resumed = registry.execute("attempt.resume", {"attempt_id": attempt_id}, ctx).model_dump()
    assert resumed["status"] == "in_progress"


def test_a_paused_attempt_cannot_be_saved(ctx: Context) -> None:
    seed_package(ctx)
    ctx.store.set("items", "practice-1", make_item("practice-1"))
    package = {"exam": "tpa-bappenas", "sections": {"kuantitatif": ["practice-1"]}}
    out = registry.execute("attempt.start", {"mode": "practice", "package": package}, ctx)
    attempt_id = str(out.model_dump(by_alias=True)["attemptId"])
    registry.execute("attempt.pause", {"attempt_id": attempt_id}, ctx)
    with pytest.raises(AppError) as err:
        registry.execute("attempt.save", {"attempt_id": attempt_id, "answers": {"1": "B"}}, ctx)
    assert err.value.code == "conflict"


def test_an_exam_attempt_cannot_be_paused(ctx: Context) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    with pytest.raises(AppError) as err:
        registry.execute("attempt.pause", {"attempt_id": attempt_id}, ctx)
    assert err.value.code == "invalid_args"
    with pytest.raises(AppError) as err:
        registry.execute("attempt.resume", {"attempt_id": attempt_id}, ctx)
    assert err.value.code == "invalid_args"


def test_a_running_attempt_cannot_be_resumed(ctx: Context) -> None:
    seed_package(ctx)
    ctx.store.set("items", "practice-1", make_item("practice-1"))
    package = {"exam": "tpa-bappenas", "sections": {"kuantitatif": ["practice-1"]}}
    out = registry.execute("attempt.start", {"mode": "practice", "package": package}, ctx)
    attempt_id = str(out.model_dump(by_alias=True)["attemptId"])
    with pytest.raises(AppError) as err:
        registry.execute("attempt.resume", {"attempt_id": attempt_id}, ctx)
    assert err.value.code == "conflict"


def test_pause_and_resume_need_the_owner(ctx: Context, admin_ctx: Context, mem) -> None:
    seed_package(ctx)
    ctx.store.set("items", "practice-1", make_item("practice-1"))
    package = {"exam": "tpa-bappenas", "sections": {"kuantitatif": ["practice-1"]}}
    out = registry.execute("attempt.start", {"mode": "practice", "package": package}, ctx)
    attempt_id = str(out.model_dump(by_alias=True)["attemptId"])
    for ctx_actor in (other_ctx(mem), admin_ctx):
        with pytest.raises(AppError) as err:
            registry.execute("attempt.pause", {"attempt_id": attempt_id}, ctx_actor)
        assert err.value.code == "not_found"
        with pytest.raises(AppError) as err:
            registry.execute("attempt.resume", {"attempt_id": attempt_id}, ctx_actor)
        assert err.value.code == "not_found"


# --- practice and study ----------------------------------------------------


def test_practice_build_never_uses_an_exam_package_item(ctx: Context) -> None:
    seed_package(ctx)
    ctx.store.set("items", "practice-1", make_item("practice-1"))
    out = registry.execute("practice.build", {"count": 10}, ctx)
    data = out.model_dump(by_alias=True)
    assert data["itemIds"] == ["practice-1"]
    assert "tpa-k-0101" not in json.dumps(data)


def test_practice_build_needs_login(guest_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("practice.build", {"count": 5}, guest_ctx)
    assert err.value.code == "login_required"


def test_practice_build_takes_items_from_different_families_first(ctx: Context) -> None:
    seed_package(ctx)
    first = make_item("practice-1")
    first["familyId"] = "fam-1"
    second = make_item("practice-2")
    second["familyId"] = "fam-1"
    third = make_item("practice-3")
    third["familyId"] = "fam-2"
    for item in (first, second, third):
        ctx.store.set("items", str(item["id"]), item)
    out = registry.execute("practice.build", {"count": 2}, ctx)
    assert out.model_dump(by_alias=True)["itemIds"] == ["practice-1", "practice-3"]


def test_study_next_never_returns_an_exam_package_item(ctx: Context) -> None:
    seed_package(ctx)
    ctx.store.set("items", "study-1", make_item("study-1"))
    out = registry.execute("study.next", {}, ctx)
    item = out.model_dump(by_alias=True)["item"]
    assert item is not None
    assert item["id"] == "study-1"
    no_keys(item)


def test_study_next_needs_login(guest_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("study.next", {}, guest_ctx)
    assert err.value.code == "login_required"


def test_study_check_grades_a_study_item(ctx: Context) -> None:
    seed_package(ctx)
    ctx.store.set("items", "study-1", make_item("study-1"))
    ctx.store.set("item_keys", "study-1", make_key("study-1"))
    out = registry.execute("study.check", {"item_id": "study-1", "question_id": "q1", "answer": "B"}, ctx)
    data = out.model_dump(by_alias=True)
    assert data["correct"] is True
    assert data["explanation"] == "Penjelasan singkat."


def test_study_check_of_an_exam_package_item_is_not_found(ctx: Context) -> None:
    seed_package(ctx)
    with pytest.raises(AppError) as err:
        registry.execute("study.check", {"item_id": "tpa-k-0101", "question_id": "q1", "answer": "B"}, ctx)
    assert err.value.code == "not_found"


def test_study_check_is_rate_limited(ctx: Context) -> None:
    seed_package(ctx)
    ctx.store.set("items", "study-1", make_item("study-1"))
    ctx.store.set("item_keys", "study-1", make_key("study-1"))
    rate_limit.limiter.reset()
    for _ in range(60):
        registry.execute("study.check", {"item_id": "study-1", "question_id": "q1", "answer": "B"}, ctx)
    with pytest.raises(AppError) as err:
        registry.execute("study.check", {"item_id": "study-1", "question_id": "q1", "answer": "B"}, ctx)
    assert err.value.code == "rate_limited"
    rate_limit.limiter.reset()


# --- the keys never leave the server ---------------------------------------


def test_no_student_output_holds_a_key(ctx: Context) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    registry.execute("attempt.save", {"attempt_id": attempt_id, "answers": {"1": "B"}}, ctx)
    for name, args in (
        ("attempt.get", {"attempt_id": attempt_id}),
        ("attempt.history", {}),
    ):
        out = registry.execute(name, args, ctx)
        no_keys(out.model_dump(by_alias=True))
    started = registry.execute("attempt.start", {"test_id": "tpa-mini", "mode": "exam"}, ctx)
    no_keys(started.model_dump(by_alias=True))
    ctx.store.set("items", "practice-1", make_item("practice-1"))
    package = build_practice(ctx, count=2)
    no_keys(package)


def test_the_result_of_a_submitted_attempt_holds_no_explanation(ctx: Context) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    registry.execute("attempt.save", {"attempt_id": attempt_id, "answers": {"1": "B"}}, ctx)
    out = registry.execute("attempt.submit", {"attempt_id": attempt_id}, ctx)
    no_keys(out.model_dump(by_alias=True))


# --- end to end ------------------------------------------------------------


def test_a_tpa_attempt_is_scored_end_to_end(ctx: Context) -> None:
    seed_package(ctx)
    attempt_id = start(ctx)
    registry.execute(
        "attempt.save",
        {"attempt_id": attempt_id, "answers": {"1": "B", "2": "C", "3": "A"}, "timings": {"1": 30}},
        ctx,
    )
    out = registry.execute("attempt.submit", {"attempt_id": attempt_id}, ctx)
    result = out.model_dump(by_alias=True)["result"]
    assert result["scoreType"] == "number"
    assert result["correct"] == 3
    assert result["wrong"] == 0
    assert result["score"] == 800.0
    assert result["sections"]["kuantitatif"]["marks"] == 1.0
    assert result["sections"]["kuantitatif"]["timeSec"] == 30.0
    doc = ctx.store.get("attempts", attempt_id)
    assert doc is not None
    assert doc["status"] == "submitted"
    assert doc["submittedAt"]


def test_an_ielts_attempt_is_scored_end_to_end(ctx: Context) -> None:
    ctx.store.set(
        "items",
        "ielts-r-0101",
        {
            "id": "ielts-r-0101",
            "exam": "ielts",
            "section": "reading",
            "difficulty": 2,
            "targetTimeSec": 90,
            "status": "active",
            "usage": {"exam": True, "practice": True, "study": False},
            "sites": ["id", "global"],
            "stimulus": None,
            "groups": [
                {
                    "id": "g1",
                    "type": "choice",
                    "topic": None,
                    "instructions": "Choose the best answer.",
                    "options": [
                        {"id": "A", "text": "one"},
                        {"id": "B", "text": "two"},
                    ],
                    "questions": [
                        {"id": "q1", "prompt": "First?"},
                        {"id": "q2", "prompt": "Second?"},
                    ],
                }
            ],
        },
    )
    ctx.store.set(
        "item_keys",
        "ielts-r-0101",
        {
            "id": "ielts-r-0101",
            "answers": {"q1": ["A"], "q2": ["B"]},
            "explanations": {"q1": "Because."},
            "transcript": None,
            "aiCheck": None,
        },
    )
    ctx.store.set(
        "tests",
        "ielts-mini",
        {
            "id": "ielts-mini",
            "exam": "ielts",
            "sections": {"reading": ["ielts-r-0101"]},
            "durationSec": 300,
            "free": True,
            "wrongPenalty": 0,
            "status": "active",
            "sites": ["id", "global"],
        },
    )
    out = registry.execute("attempt.start", {"test_id": "ielts-mini", "mode": "exam"}, ctx)
    attempt_id = str(out.model_dump(by_alias=True)["attemptId"])
    registry.execute("attempt.save", {"attempt_id": attempt_id, "answers": {"1": "A", "2": "C"}}, ctx)
    result = registry.execute("attempt.submit", {"attempt_id": attempt_id}, ctx).model_dump(by_alias=True)
    assert result["result"]["scoreType"] == "band"
    assert result["result"]["correct"] == 1
    assert result["result"]["wrong"] == 1
    assert result["result"]["sections"]["reading"]["score"] == 5.5


def test_the_wrong_penalty_is_applied_by_the_core(ctx: Context) -> None:
    seed_package(ctx)
    ctx.store.update("tests", "tpa-mini", {"wrongPenalty": 0.5})
    attempt_id = start(ctx)
    registry.execute("attempt.save", {"attempt_id": attempt_id, "answers": {"1": "A"}}, ctx)
    result = registry.execute("attempt.submit", {"attempt_id": attempt_id}, ctx).model_dump(by_alias=True)
    assert result["result"]["wrongPenalty"] == 0.5
    assert result["result"]["sections"]["kuantitatif"]["marks"] == 0.0


def test_the_wrong_penalty_lowers_the_score(ctx: Context) -> None:
    seed_package(ctx)
    ctx.store.set(
        "tests",
        "penalty-mini",
        {
            "id": "penalty-mini",
            "exam": "tpa-bappenas",
            "sections": {"kuantitatif": ["tpa-k-0101", "tpa-v-0101"]},
            "durationSec": 180,
            "free": True,
            "wrongPenalty": 0.5,
            "status": "active",
            "sites": ["id"],
        },
    )
    attempt_id = start(ctx, "penalty-mini")
    registry.execute("attempt.save", {"attempt_id": attempt_id, "answers": {"1": "B", "2": "A"}}, ctx)
    result = registry.execute("attempt.submit", {"attempt_id": attempt_id}, ctx).model_dump(by_alias=True)
    # One correct answer and one wrong: 1 - 0.5 marks out of 2 questions.
    # Without the penalty the score would be 500.
    assert result["result"]["correct"] == 1
    assert result["result"]["wrong"] == 1
    assert result["result"]["sections"]["kuantitatif"]["marks"] == 0.5
    assert result["result"]["score"] == 350.0


# --- helpers ---------------------------------------------------------------


def make_multi_item(item_id: str) -> dict[str, Any]:
    """An item with a `multi` group (choose two options)."""
    return {
        "id": item_id,
        "exam": "tpa-bappenas",
        "section": "kuantitatif",
        "difficulty": 2,
        "targetTimeSec": 45,
        "status": "active",
        "usage": {"exam": True, "practice": True, "study": True},
        "sites": ["id"],
        "stimulus": None,
        "groups": [
            {
                "id": "g1",
                "type": "multi",
                "topic": None,
                "instructions": "Pilih dua jawaban.",
                "options": [
                    {"id": "A", "text": "24"},
                    {"id": "B", "text": "26"},
                    {"id": "C", "text": "28"},
                    {"id": "D", "text": "30"},
                ],
                "questions": [{"id": "q1", "prompt": "Pilih dua."}],
            }
        ],
    }


def make_multi_key(item_id: str) -> dict[str, Any]:
    """The key of the `multi` item: the two right options."""
    return {
        "id": item_id,
        "answers": {"q1": ["A", "C"]},
        "explanations": {"q1": "Penjelasan singkat."},
        "transcript": None,
        "aiCheck": None,
    }
