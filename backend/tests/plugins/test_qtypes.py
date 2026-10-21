"""The question-type grading: choice, select, multi and text (normalisation)."""

from __future__ import annotations

from cendekiara.core.plugins import get_qtype
from cendekiara.qtypes.text import normalize_text


def test_choice_grades_a_single_option() -> None:
    grade = get_qtype("choice")
    assert grade(None, ["B"], "B").correct is True
    assert grade(None, ["B"], "A").correct is False


def test_select_grades_a_single_option() -> None:
    grade = get_qtype("select")
    assert grade(None, ["D"], "D").correct is True
    assert grade(None, ["D"], "C").correct is False


def test_multi_grades_an_exact_set() -> None:
    grade = get_qtype("multi")
    assert grade(None, ["A", "C"], ["C", "A"]).correct is True
    assert grade(None, ["A", "C"], ["A"]).correct is False
    assert grade(None, ["A", "C"], ["A", "C", "D"]).correct is False


def test_text_normalisation_ignores_case() -> None:
    assert normalize_text("HELLO") == "hello"


def test_text_normalisation_ignores_repeated_spaces() -> None:
    assert normalize_text("  the   cat  ") == "the cat"


def test_text_normalisation_ignores_quotes() -> None:
    assert normalize_text('"the cat"') == "the cat"
    assert normalize_text("'the cat'") == "the cat"


def test_text_normalisation_ignores_trailing_punctuation() -> None:
    assert normalize_text("the cat.") == "the cat"
    assert normalize_text("the cat!") == "the cat"


def test_text_grades_normalised_variants() -> None:
    grade = get_qtype("text")
    assert grade(None, ["the cat"], "The  cat!").correct is True
    assert grade(None, ["the cat"], "the dog").correct is False
