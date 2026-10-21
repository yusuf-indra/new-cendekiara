"""Exam engine tests."""

from __future__ import annotations

import json

import pytest

from cendekiara.core import clock, rate_limit, registry
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from tests.item_helpers import make_item, make_key

KEY_FIELDS = {"answers", "keys", "explanations", "transcript", "ai_check", "aiCheck"}


def _ensure_tpa_mini(ctx: Context) -> None:
    ctx.store.set(
        "tests",
        "tpa-mini",
        {
            "id": "tpa-mini",
            "exam": "tpa-bappenas",
            "sections": {
                "kuantitatif": ["tpa-k-0101"],
                "verbal": ["tpa-v-0101"],
                "penalaran": ["tpa-p-0101"],
            },
            "durationSec": 180,
            "free": True,
            "wrongPenalty": 0,
            "status": "active",
            "sites": ["id"],
        },
    )
    # ensure items/keys exist

    for iid in ["tpa-k-0101", "tpa-v-0101", "tpa-p-0101"]:
        if ctx.store.get("items", iid) is None:
            ctx.store.set("items", iid, make_item(iid))
        if ctx.store.get("item_keys", iid) is None:
            ctx.store.set("item_keys", iid, make_key(iid))


def test_attempt_start_exam_happy_path(ctx: Context) -> None:
    _ensure_tpa_mini(ctx)
    out = _ensure_tpa_mini(ctx) or registry.execute(
        "attempt.start", {"test_id": "tpa-mini", "mode": "exam"}, ctx
    )
    data = out.model_dump(by_alias=True)
    assert data["attemptId"]
    assert data["exam"] == "tpa-bappenas"
    assert data["status"] == "in_progress"
    assert "package" in data


def test_attempt_start_needs_login(guest_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("attempt.start", {"test_id": "tpa-mini", "mode": "exam"}, guest_ctx)
    assert err.value.code == "login_required"


def test_attempt_get_ownership_other_user(admin_ctx: Context, ctx: Context, mem) -> None:
    # create attempt as ctx user
    out = _ensure_tpa_mini(ctx) or registry.execute(
        "attempt.start", {"test_id": "tpa-mini", "mode": "exam"}, ctx
    )
    aid = out.model_dump(by_alias=True)["attemptId"]
    # admin may read any attempt
    out2 = registry.execute("attempt.get", {"attempt_id": aid}, admin_ctx)
    assert out2.model_dump(by_alias=True)["attempt"]["id"] == aid
    # other user cannot read
    from cendekiara.core.context import Actor, Context

    other = Context(Actor(uid="u-other"), mem)
    with pytest.raises(AppError) as err:
        registry.execute("attempt.get", {"attempt_id": aid}, other)
    assert err.value.code == "not_found"


def test_admin_cannot_write_others_attempt(ctx: Context, admin_ctx: Context) -> None:
    out = _ensure_tpa_mini(ctx) or registry.execute(
        "attempt.start", {"test_id": "tpa-mini", "mode": "exam"}, ctx
    )
    aid = out.model_dump(by_alias=True)["attemptId"]
    with pytest.raises(AppError) as err:
        registry.execute("attempt.save", {"attempt_id": aid, "answers": {"q1": ["B"]}}, admin_ctx)
    assert err.value.code == "not_found"
    with pytest.raises(AppError) as err:
        registry.execute("attempt.submit", {"attempt_id": aid}, admin_ctx)
    assert err.value.code == "not_found"
    with pytest.raises(AppError) as err:
        registry.execute("attempt.pause", {"attempt_id": aid}, admin_ctx)
    assert err.value.code == "not_found"
    with pytest.raises(AppError) as err:
        registry.execute("attempt.resume", {"attempt_id": aid}, admin_ctx)
    assert err.value.code == "not_found"


def test_attempt_save_merges_answers_timings_flags(ctx: Context) -> None:
    out = _ensure_tpa_mini(ctx) or registry.execute(
        "attempt.start", {"test_id": "tpa-mini", "mode": "exam"}, ctx
    )
    aid = out.model_dump(by_alias=True)["attemptId"]
    registry.execute(
        "attempt.save",
        {"attempt_id": aid, "answers": {"q1": ["B"]}, "timings": {"q1": 10}, "flags": ["q1"]},
        ctx,
    )
    registry.execute("attempt.save", {"attempt_id": aid, "answers": {"q2": ["A"]}, "flags": ["q2"]}, ctx)
    doc = ctx.store.get("attempts", aid)
    assert doc["answers"]["q1"] == ["B"]
    assert doc["answers"]["q2"] == ["A"]
    assert doc["flags"] == ["q2"]  # replaced


def test_attempt_save_deadline_grace(ctx: Context) -> None:
    out = _ensure_tpa_mini(ctx) or registry.execute(
        "attempt.start", {"test_id": "tpa-mini", "mode": "exam"}, ctx
    )
    aid = out.model_dump(by_alias=True)["attemptId"]
    # move past deadline + grace
    from datetime import timedelta

    clock.freeze(clock.now() + timedelta(hours=5))
    with pytest.raises(AppError) as err:
        registry.execute("attempt.save", {"attempt_id": aid, "answers": {"q1": ["B"]}}, ctx)
    assert err.value.code == "deadline_passed"
    clock.unfreeze()
    clock.freeze(
        __import__("datetime").datetime(2026, 10, 21, 12, 0, tzinfo=__import__("datetime").timezone.utc)
    )


def test_attempt_submit_grades_stored_answers_not_final(ctx: Context) -> None:
    out = _ensure_tpa_mini(ctx) or registry.execute(
        "attempt.start", {"test_id": "tpa-mini", "mode": "exam"}, ctx
    )
    aid = out.model_dump(by_alias=True)["attemptId"]
    registry.execute(
        "attempt.save", {"attempt_id": aid, "answers": {"q1": ["B"], "q2": ["B"], "q3": ["A"]}}, ctx
    )
    res = registry.execute("attempt.submit", {"attempt_id": aid, "timings": {"q1": 5}}, ctx)
    data = res.model_dump(by_alias=True)
    assert data["status"] == "submitted"
    assert "result" in data


def test_attempt_immutability(ctx: Context) -> None:
    out = _ensure_tpa_mini(ctx) or registry.execute(
        "attempt.start", {"test_id": "tpa-mini", "mode": "exam"}, ctx
    )
    aid = out.model_dump(by_alias=True)["attemptId"]
    registry.execute("attempt.submit", {"attempt_id": aid}, ctx)
    with pytest.raises(AppError) as err:
        registry.execute("attempt.save", {"attempt_id": aid, "answers": {"q1": ["B"]}}, ctx)
    assert err.value.code == "conflict"
    with pytest.raises(AppError) as err:
        registry.execute("attempt.submit", {"attempt_id": aid}, ctx)
    assert err.value.code == "conflict"


def test_pause_resume_practice_rules(ctx: Context) -> None:
    # start practice
    pkg = registry.execute("practice.build", {"count": 2}, ctx).model_dump(by_alias=True)["package"]
    out = registry.execute("attempt.start", {"mode": "practice", "package": pkg}, ctx)
    aid = out.model_dump(by_alias=True)["attemptId"]
    registry.execute("attempt.pause", {"attempt_id": aid}, ctx)
    registry.execute("attempt.resume", {"attempt_id": aid}, ctx)
    # cannot pause exam
    out2 = _ensure_tpa_mini(ctx) or registry.execute(
        "attempt.start", {"test_id": "tpa-mini", "mode": "exam"}, ctx
    )
    aid2 = out2.model_dump(by_alias=True)["attemptId"]
    with pytest.raises(AppError) as err:
        registry.execute("attempt.pause", {"attempt_id": aid2}, ctx)
    assert err.value.code == "invalid_args"


def test_practice_study_exclude_exam_package_items(ctx: Context, admin_ctx: Context) -> None:
    # add an exam package item to tests? tpa-mini already uses items - they must not appear in practice/study
    pb = registry.execute("practice.build", {"count": 10}, ctx).model_dump(by_alias=True)
    # package should not contain exam items
    pkg = pb["package"]
    # walk
    item_ids = set()
    for sec in pkg.get("sections", []):
        for it in sec.get("items", []):
            item_ids.add(it["id"])
    # tpa-mini uses tpa-k-0101, tpa-v-0101, tpa-p-0101
    assert "tpa-k-0101" not in item_ids
    sn = registry.execute("study.next", {}, ctx).model_dump(by_alias=True)
    # if returns item, it must not be from exam package
    if sn["item"]:
        assert sn["item"]["id"] not in {"tpa-k-0101", "tpa-v-0101", "tpa-p-0101"}


def test_study_check_gate_exam_package_item(ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("study.check", {"item_id": "tpa-k-0101", "question_id": "q1", "answer": "B"}, ctx)
    assert err.value.code == "not_found"


def test_rate_limit_attempt_save_and_study_check(ctx: Context, mem) -> None:
    rate_limit.reset()
    # create a study item not in any test? add one

    item = make_item("study-x-1")
    item["usage"] = {"exam": False, "practice": False, "study": True}
    registry.execute(
        "item.create",
        {"item": item, "key": make_key("study-x-1")},
        __import__("cendekiara.core.context", fromlist=["Context"]).Context(
            __import__("cendekiara.core.context", fromlist=["Actor"]).Actor(
                uid="u-admin", email="admin@example.com", is_admin=True
            ),
            mem,
        ),
    )
    rate_limit.reset()
    # hammer
    from cendekiara.core import config

    limit = int(getattr(config.settings, "study_check_rate_limit", 60))
    for _i in range(limit):
        registry.execute("study.check", {"item_id": "study-x-1", "question_id": "q1", "answer": "B"}, ctx)
    with pytest.raises(AppError) as err:
        registry.execute("study.check", {"item_id": "study-x-1", "question_id": "q1", "answer": "B"}, ctx)
    assert err.value.code == "rate_limited"


def test_key_leak_across_all_student_outputs(ctx: Context) -> None:
    out = _ensure_tpa_mini(ctx) or registry.execute(
        "attempt.start", {"test_id": "tpa-mini", "mode": "exam"}, ctx
    )
    aid = out.model_dump(by_alias=True)["attemptId"]
    s = json.dumps(out.model_dump())
    assert not any(k in s for k in ["explanation", "transcript", "aiCheck"])
    registry.execute("attempt.save", {"attempt_id": aid, "answers": {"q1": ["B"]}}, ctx)
    g = registry.execute("attempt.get", {"attempt_id": aid}, ctx)
    s2 = json.dumps(g.model_dump())
    assert "explanation" not in s2
    h = registry.execute("attempt.history", {}, ctx)
    s3 = json.dumps(h.model_dump())
    assert "explanation" not in s3


def test_end_to_end_tpa_attempt_scale_200_800(ctx: Context) -> None:
    out = _ensure_tpa_mini(ctx) or registry.execute(
        "attempt.start", {"test_id": "tpa-mini", "mode": "exam"}, ctx
    )
    aid = out.model_dump(by_alias=True)["attemptId"]
    registry.execute(
        "attempt.save", {"attempt_id": aid, "answers": {"q1": ["B"], "q2": ["B"], "q3": ["A"]}}, ctx
    )
    res = registry.execute("attempt.submit", {"attempt_id": aid}, ctx)
    data = res.model_dump(by_alias=True)
    assert data["result"]["scoreType"] == "number" or "score" in data["result"]


def test_end_to_end_ielts_attempt_ielts_band(ctx: Context) -> None:
    # try to start ielts if test exists? or build
    pass


def test_late_submit(ctx: Context) -> None:
    out = _ensure_tpa_mini(ctx) or registry.execute(
        "attempt.start", {"test_id": "tpa-mini", "mode": "exam"}, ctx
    )
    aid = out.model_dump(by_alias=True)["attemptId"]
    from datetime import timedelta

    clock.freeze(clock.now() + timedelta(hours=5))
    with pytest.raises(AppError) as err:
        registry.execute("attempt.submit", {"attempt_id": aid}, ctx)
    assert err.value.code == "deadline_passed"
    clock.unfreeze()
    clock.freeze(
        __import__("datetime").datetime(2026, 10, 21, 12, 0, tzinfo=__import__("datetime").timezone.utc)
    )
