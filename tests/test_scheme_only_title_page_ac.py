"""Scheme-file-only title-page asks become asked cover rows (AC5)."""

from helpers import open_sequence

from essay_writer.brief_contract import pack_with_registration, remember_registration
from essay_writer.diary import cover_field_rows, print_cover_row, title_page_spec
from essay_writer.paths import essay_dir
from essay_writer.word import cover_lines

MODULE = "RPT5001AA"
NUMBER = "445566"

SCHEME_ONLY_TITLE_PAGE = """
Assignment title: Individual reflective diary

Module title: Practice module
Module code: RPT5001AA

Assignment task: Write four entries.

# Marking criteria/feedback form

| Criterion | 0-39 | 70+ |
| --- | --- | --- |
| Title page | thin | student address |
"""


def _write(text: str) -> None:
    folder = essay_dir(MODULE)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(text, encoding="utf-8")


def _pack(seq: str) -> dict:
    return {
        "essay_id": seq,
        "title": "Individual reflective diary",
        "referencing": "harvard",
        "assessment": "Individual reflective diary",
        "module_title": "Practice module",
        "sections": [{"heading": "One decision", "body": "A decision with theory."}],
    }


def _report(pack: dict) -> dict:
    return {
        "title": pack.get("title"),
        "word_count": {"counted": 120},
        "sections": pack.get("sections") or [],
    }


def test_ac5_scheme_only_title_page_ask_is_asked_cover_row(workspace):
    """AC5. A title-page field named only in the marking table prints as an asked row."""
    _write(SCHEME_ONLY_TITLE_PAGE)
    seq = open_sequence(MODULE)
    assert remember_registration(seq, NUMBER) == NUMBER
    spec = title_page_spec(SCHEME_ONLY_TITLE_PAGE)
    assert spec["labels"] == ["Student address"]
    pack = pack_with_registration(seq, _pack(seq))
    report = _report(pack)
    rows = cover_field_rows(seq, pack, report, essay=False)
    custom = [row for row in rows if row.key == "custom"]
    assert len(custom) == 1
    assert custom[0].kind == "asked"
    assert custom[0].label == "Student address"
    assert custom[0].value == ""
    assert print_cover_row(custom[0]) == "Student address:"
    lines = cover_lines(seq, pack, report)
    assert "Student address:" in lines
