"""Stage 6 and stage 7 use the locked story. Opaque ids.

The acceptance label for each case is in the docstring.
"""

from __future__ import annotations

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.prompt_loader import bullets, sections
from essay_writer.stage_llm import stage_settings

TOOL_DRAFTS = "The tool drafts."
STUDENT_DIRECTS = "The student directs and confirms."
STAGE6 = "Stage 6 is the student's read-through and feedback, not a tool rewrite."
STAGE7 = "Stage 7 asks questions and edits from the student's answers."
GENRES = (None, "essay", "report", "diary")


def test_case_1():
    """AC1: Stage 6 and 7 match the locked story on Cursor and Grok Build.

    The tool drafts. The student directs and confirms. Stage 6 is the student's
    read-through and feedback, not a tool rewrite. Stage 7 asks questions and
    edits from the student's answers. Both launches read that same rules text.
    The checklist bullets stay flat.
    """
    for genre in GENRES:
        for stage, sentence in (("6", STAGE6), ("7", STAGE7)):
            rules = stage_settings(stage, genre)["rules"]
            assert TOOL_DRAFTS in rules
            assert STUDENT_DIRECTS in rules
            assert sentence in rules
            assert stage_launch(stage)["settings"]["rules"] == stage_settings(stage)["rules"]
            assert cursor_stage_launch(stage)["settings"]["rules"] == stage_settings(stage)["rules"]
    stage6 = bullets("stages/06.md", "shared")
    stage7 = bullets("stages/07.md", "shared")
    assert STAGE6 in stage6[0]
    assert STAGE7 in stage7[0]
    assert all("\n" not in line for line in stage6 + stage7)
    assert "show the short read list once, then stop" in stage_settings("6")["rules"]
    assert "Do not rewrite the draft for them." in stage_settings("6")["rules"]


def test_case_2():
    """AC2: content_check, phrasebank_pointer, and edit_recheck stay, and so does the read list."""
    voice = sections("craft/voice.md")
    assert voice["content_check"]
    assert voice["phrasebank_pointer"]
    assert voice["edit_recheck"]
    assert voice["content_check"] in stage_settings("5")["rules"]
    assert voice["phrasebank_pointer"] in stage_settings("5")["rules"]
    assert voice["edit_recheck"] in stage_settings("8")["rules"]
    read_list = sections("front_office/chat.md")["stage6_read_list"]
    assert read_list.startswith("Read the draft and edit it yourself.")
    assert "show the short read list once, then stop" in stage_settings("6")["rules"]
