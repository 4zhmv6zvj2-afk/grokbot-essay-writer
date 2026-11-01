"""Cover fields the brief already asked for. Stable ids: AC1–AC3.

A brief that asks for a candidate number, an enrolment number, or a
matriculation number is asking for the registration field. The same field the
essay door stores and prints. Nothing is added when the brief is silent or says
to leave the number off.
"""

from pathlib import Path

from helpers import ESSAY

from essay_writer.diary import missing_cover_fields, title_page_spec

BRIEF = (
    "Genre: report\n"
    "Question: How do chokepoints constrain the corridor?\n"
    "Title page: candidate number, module code, and word count.\n"
)


def _plant(workspace: Path, text: str) -> None:
    folder = workspace / "Essay-writer" / ESSAY
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(text, encoding="utf-8")


def test_ac1_the_named_cover_field_is_a_registration_number():
    """AC1. Candidate, enrolment, and matriculation numbers are the registration field."""
    for ask in (
        "Title page: candidate number and word count.",
        "Title page: candidate numbers.",
        "Title page: enrolment number.",
        "Title page: enrollment number.",
        "Title page: matriculation number.",
    ):
        spec = title_page_spec(ask)
        assert spec["registration"] is True, ask
        assert "registration" in spec["fields"], ask
    silent = title_page_spec("Title page: module code and word count.")
    assert silent["registration"] is False
    assert "registration" not in silent["fields"]


def test_ac2_a_negated_ask_is_not_an_ask():
    """AC2. "Do not include your candidate number" stays no field."""
    spec = title_page_spec("Do not include your candidate number on the title page.")
    assert spec["registration"] is False
    assert "registration" not in spec["fields"]


def test_ac3_a_missing_named_field_blocks_word_until_supplied(workspace):
    """AC3. Word asks for the named field, and accepts the number the student supplies."""
    _plant(workspace, BRIEF)
    missing = missing_cover_fields(ESSAY, {}, {"word_count": {}})
    assert "registration number" in missing
    supplied = {"registration_number": "102938"}
    assert "registration number" not in missing_cover_fields(
        ESSAY, supplied, {"word_count": {}}
    )
    student = {"student_number": "102938"}
    assert "registration number" not in missing_cover_fields(
        ESSAY, student, {"word_count": {}}
    )
