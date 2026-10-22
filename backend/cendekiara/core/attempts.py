"""Attempt grading and helpers (server-side only)."""

from __future__ import annotations

from typing import Any

from cendekiara.core import plugins
from cendekiara.core.items import ItemKey
from cendekiara.core.plugins import Marks, RawResult, SectionResult, TestSpec
from cendekiara.core.store import Store

SUBMIT_GRACE_SEC = 60


def get_submit_grace_sec(settings: Any = None) -> int:
    if settings is not None and hasattr(settings, "submit_grace_sec"):
        try:
            return int(settings.submit_grace_sec)
        except (TypeError, ValueError):
            pass
    try:
        from cendekiara.core import config

        s = config.settings
        if hasattr(s, "submit_grace_sec"):
            try:
                return int(s.submit_grace_sec)
            except (TypeError, ValueError):
                pass
    except (ImportError, AttributeError):
        pass
    return SUBMIT_GRACE_SEC


def cap_timings(timings: dict[str, float]) -> dict[str, float]:
    capped: dict[str, float] = {}
    for k, v in timings.items():
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if fv < 0:
            fv = 0.0
        if fv > 3 * 3600:
            fv = 3 * 3600
        capped[k] = fv
    return capped


def grade_attempt(
    store: Store, attempt: dict[str, Any], package_snapshot: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Grade a submitted attempt using stored answers. Never trust client scores."""
    from cendekiara.core.models import AttemptResult, AttemptResultSection

    pkg = package_snapshot or attempt.get("packageSnapshot") or attempt.get("package_snapshot") or {}
    if isinstance(pkg, dict) and "sections" in pkg and isinstance(pkg["sections"], list):
        # assembled form
        sections_list = pkg["sections"]
    elif isinstance(pkg, dict) and "sections" in pkg and isinstance(pkg["sections"], dict):
        sections_list = []
        for sid, items in pkg["sections"].items():
            # convert dict form to assembled-like if needed
            sections_list.append({"id": sid, "items": items})
    else:
        # try to find sections in package_snapshot stored differently
        sections_list = []

    answers = attempt.get("answers") or {}
    if isinstance(answers, dict):
        pass
    else:
        answers = {}

    # Build maps
    wrong_penalty = float(
        attempt.get("wrongPenalty")
        or attempt.get("wrong_penalty")
        or pkg.get("wrongPenalty")
        or pkg.get("wrong_penalty")
        or 0.0
    )
    exam_id = attempt.get("exam") or pkg.get("exam")

    # Collect all questions with their item/group info
    raw_sections: dict[str, SectionResult] = {}
    question_to_section: dict[str, str] = {}
    question_to_item: dict[str, str] = {}
    question_to_group_type: dict[str, str] = {}
    total_questions_per_section: dict[str, int] = {}

    # Also need to know how many questions per section for TestSpec
    # Walk assembled package
    if isinstance(pkg, dict) and "sections" in pkg and isinstance(pkg["sections"], list):
        for sec in pkg["sections"]:
            sec_id = sec.get("id") or sec.get("sectionId")
            if not sec_id:
                continue
            count_q = 0
            items = sec.get("items") or []
            for it in items:
                item_id = it.get("id") if isinstance(it, dict) else getattr(it, "id", None)
                groups = it.get("groups") or [] if isinstance(it, dict) else getattr(it, "groups", [])
                for g in groups:
                    gtype = g.get("type") if isinstance(g, dict) else getattr(g, "type", None)
                    questions = (
                        g.get("questions") or [] if isinstance(g, dict) else getattr(g, "questions", [])
                    )
                    for q in questions:
                        qid = q.get("id") if isinstance(q, dict) else getattr(q, "id", None)
                        if qid:
                            question_to_section[qid] = sec_id
                            if item_id:
                                question_to_item[qid] = item_id
                            if gtype:
                                question_to_group_type[qid] = gtype
                            count_q += 1
            total_questions_per_section[sec_id] = count_q
    else:
        # try dict form
        sections_dict = pkg.get("sections") if isinstance(pkg, dict) else None
        if isinstance(sections_dict, dict):
            for sec_id, items in sections_dict.items():
                count_q = 0
                # items might be list of item objects or just ids; if objects walk them
                if isinstance(items, list):
                    for it in items:
                        if isinstance(it, dict):
                            item_id = it.get("id")
                            groups = it.get("groups") or []
                            for g in groups:
                                if isinstance(g, dict):
                                    gtype = g.get("type")
                                    questions = g.get("questions") or []
                                    for q in questions:
                                        if isinstance(q, dict):
                                            qid = q.get("id")
                                            if qid:
                                                question_to_section[qid] = sec_id
                                                if item_id:
                                                    question_to_item[qid] = item_id
                                                if gtype:
                                                    question_to_group_type[qid] = gtype
                                                count_q += 1
                total_questions_per_section[sec_id] = count_q

    # Initialize raw sections
    for sec_id in total_questions_per_section:
        raw_sections[sec_id] = SectionResult(correct=0, wrong=0, blank=0, marks=0.0)

    # Grade each question
    for qid, section_id in question_to_section.items():
        ans = answers.get(qid)
        if (
            ans is None
            or (isinstance(ans, str) and ans.strip() == "")
            or (isinstance(ans, list) and len(ans) == 0)
        ):
            raw_sections[section_id].blank += 1
            continue
        item_id = question_to_item.get(qid)
        gtype = question_to_group_type.get(qid)
        if not item_id or not gtype:
            raw_sections[section_id].blank += 1
            continue
        key_doc = store.get("item_keys", item_id)
        if not key_doc:
            raw_sections[section_id].blank += 1
            continue
        try:
            key = ItemKey.from_doc(key_doc)
        except Exception:
            raw_sections[section_id].blank += 1
            continue
        expected = key.answers.get(qid)
        if expected is None:
            raw_sections[section_id].blank += 1
            continue
        try:
            grade_fn = plugins.get_qtype(gtype)
            qmodel = plugins.get_qtype_model(gtype)
            # Try to build question instance
            try:
                qinst = qmodel.model_validate({"id": qid, "prompt": ""})
            except Exception:
                qinst = type("Q", (), {"id": qid})()
            try:
                marks = grade_fn(qinst, expected, ans)
            except TypeError:
                try:
                    marks = grade_fn(qinst, ans, expected)
                except Exception:
                    marks = Marks(correct=False, marks=0.0)
        except Exception:
            marks = Marks(correct=False, marks=0.0)

        if marks.correct:
            raw_sections[section_id].correct += 1
            raw_sections[section_id].marks += float(marks.marks)
        else:
            raw_sections[section_id].wrong += 1
            raw_sections[section_id].marks += float(marks.marks)

    # Apply wrong penalty
    if wrong_penalty and wrong_penalty != 0:
        for sec_id in raw_sections:
            raw_sections[sec_id].marks = (
                raw_sections[sec_id].marks - wrong_penalty * raw_sections[sec_id].wrong
            )
            if raw_sections[sec_id].marks < 0:
                raw_sections[sec_id].marks = 0.0

    from cendekiara.core.plugins import SectionSpec

    raw_result = RawResult(sections=raw_sections)
    test_spec = TestSpec(
        sections={
            sid: SectionSpec(total=total_questions_per_section.get(sid, 0))
            for sid in total_questions_per_section
        }
    )
    try:
        if exam_id:
            exam = plugins.get_exam(exam_id)
            scoring_fn = plugins.get_scoring(exam.scoring)
            score = scoring_fn(raw_result, test_spec)
        else:
            from cendekiara.core.plugins import Score

            total_correct = sum(s.correct for s in raw_sections.values())
            total_wrong = sum(s.wrong for s in raw_sections.values())
            total_blank = sum(s.blank for s in raw_sections.values())
            score = Score(
                score=float(total_correct),
                score_type="number",
                sections={},
                correct=total_correct,
                wrong=total_wrong,
                blank=total_blank,
            )
    except Exception:
        from cendekiara.core.plugins import Score

        total_correct = sum(s.correct for s in raw_sections.values())
        total_wrong = sum(s.wrong for s in raw_sections.values())
        total_blank = sum(s.blank for s in raw_sections.values())
        score = Score(
            score=float(total_correct),
            score_type="number",
            sections={},
            correct=total_correct,
            wrong=total_wrong,
            blank=total_blank,
        )

    # Build result dict
    res_sections: dict[str, AttemptResultSection] = {}
    for sid, sres in raw_sections.items():
        res_sections[sid] = AttemptResultSection(
            correct=sres.correct,
            wrong=sres.wrong,
            blank=sres.blank,
            marks=sres.marks,
            score=score.sections.get(sid),
        )
    result = AttemptResult(
        score=score.score,
        score_type=score.score_type,
        correct=score.correct,
        wrong=score.wrong,
        blank=score.blank,
        sections=res_sections,
        raw_sections={
            k: {"correct": v.correct, "wrong": v.wrong, "blank": v.blank, "marks": v.marks}
            for k, v in raw_sections.items()
        },
    )
    return result.model_dump(by_alias=True)
