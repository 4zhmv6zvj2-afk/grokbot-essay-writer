"""Cover title must be the brief assessment title, never a gate or genre tip.

AC1: Gate tip phrasing (how to score, 70+, mark-scheme opener) is not the cover title.
AC2: RPT5001AA-style diary cover prints the brief assignment title when the pack carries a tip.
AC3: Cursor and Grok Build share cover_lines → cover_field_rows → assignment_on_cover.
"""

import inspect

from helpers import pack

from essay_writer.diary import (
    assignment_on_cover,
    cover_field_rows,
    cover_lines_from_field_rows,
    diary_cover_lines,
    gate_tip_cover_title,
)
from essay_writer.word import cover_lines, write_docx

MODULE = "RPT5001AA"
SEQ = f"{MODULE}-1"
ASSIGNMENT = "Individual reflective diary"
BRIEF = f"""
Assignment title: {ASSIGNMENT}

Module title: The Challenge Module
Module code: {MODULE}

Title page
It should specify the module title, the module code, the assignment title, and student registration numbers.
DO NOT include your name.

# Marking criteria/feedback form

| Criterion | 0-39 | 70+ |
| --- | --- | --- |
| Structure | thin | clear |
"""

_GATE_TIPS = (
    "How to score high: 70+.",
    "How to score high 70+",
    "The mark scheme scores 70+.",
    "No mark scheme is on this module.",
    "70+",
)


def test_ac1_gate_tip_phrases_are_not_cover_assignment_titles():
    """AC1. Gate and genre tip lines are rejected for the cover assignment title."""
    for tip in _GATE_TIPS:
        assert gate_tip_cover_title(tip) is True
        assert assignment_on_cover({"title": tip, "assessment": tip}, {"title": tip}, BRIEF) == ASSIGNMENT


def test_ac2_diary_cover_uses_brief_title_when_pack_carries_gate_tip(workspace, monkeypatch):
    """AC2. Diary cover prints the brief assignment title when pack/report hold a gate tip."""
    saved = {
        "essay_id": SEQ,
        "title": "How to score high: 70+.",
        "assessment": "Draft",
        "referencing": "harvard",
        "module_title": "The Challenge Module",
        "conclusion": "noted",
        "sections": pack(SEQ)["sections"],
    }
    report = {"title": "How to score high: 70+.", "word_count": {"counted": 42}}
    monkeypatch.setattr(
        "essay_writer.textutil.module_brief_text",
        lambda _essay_id: BRIEF,
    )
    rows = cover_field_rows(SEQ, saved, report, essay=False)
    lines = cover_lines_from_field_rows(SEQ, saved, rows)
    assert ASSIGNMENT in lines
    assert not any(gate_tip_cover_title(line) for line in lines)
    assert lines.count(ASSIGNMENT) == 1
    diary = diary_cover_lines(SEQ, saved, report)
    assert ASSIGNMENT in diary
    assert not any(gate_tip_cover_title(line) for line in diary)


def test_ac3_build_covered_shared_cover_title_path():
    """AC3. write_docx and cover_lines share cover_field_rows and assignment_on_cover."""
    cover_src = inspect.getsource(cover_lines)
    write_src = inspect.getsource(write_docx)
    assert "cover_field_rows(" in cover_src
    assert "cover_lines(" in write_src
    assert "assignment_on_cover" in inspect.getsource(cover_field_rows)
