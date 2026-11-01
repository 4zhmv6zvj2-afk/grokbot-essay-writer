"""Brief-fit in the stage prompts. Stable ids: AC1–AC3.

Stages 5 and 8 already carry the brief's word rules. This adds the other half
of assessment fit: each part serves a criterion the brief prints, and no
criterion, weighting, or band is invented. Prompt text only, one copy in the
shared helper note, read from the same stage row on both launchers.
"""

from pathlib import Path

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.stage_llm import stage_settings
from essay_writer.student_voice import student_surface_hits
from essay_writer.writing_basics import MARK_TABLE_LEAN, basics_lines

REPO = Path(__file__).resolve().parents[1]
HELPERS = REPO / "docs" / "academic-writing-helpers.md"
GENRES = (None, "diary", "essay", "report")
WRITING = ("5", "8")
OTHER = ("1", "2", "3", "4a", "4b", "6", "7", "9", "10")


def test_ac1_writing_stages_carry_the_mark_table_bullet():
    """AC1. Stage 5 and stage 8 carry it for every genre; other stages do not."""
    for stage in WRITING:
        for genre in GENRES:
            item = stage_settings(stage, genre)
            assert MARK_TABLE_LEAN in item["rules"]
            assert MARK_TABLE_LEAN in item["prompt_overlay"]
            assert student_surface_hits(item["prompt_overlay"]) == []
    for stage in OTHER:
        assert MARK_TABLE_LEAN not in stage_settings(stage)["rules"]


def test_ac2_the_helper_note_and_both_launchers_read_the_same_bullet():
    """AC2. One copy in the helper note, read by both launchers."""
    helpers = HELPERS.read_text(encoding="utf-8")
    assert helpers.count(MARK_TABLE_LEAN) == 2
    for stage in WRITING:
        for line in basics_lines(stage):
            assert line in helpers
        shared = stage_settings(stage)
        assert stage_launch(stage)["settings"]["rules"] == shared["rules"]
        cursor = cursor_stage_launch(stage)
        assert cursor["settings"]["rules"] == shared["rules"]
        command = stage_launch(stage)["command"]
        assert MARK_TABLE_LEAN in command[command.index("--rules") + 1]


def test_ac3_the_bullet_leans_on_listed_criteria_and_invents_none():
    """AC3. Listed criteria only. No invented criterion, weighting, or band."""
    for phrase in (
        "each part of the draft serves one of them",
        "Use the criteria it lists and no others",
        "do not add a criterion, a weighting, or a band the brief does not print",
        "A point that serves no listed criterion still has to answer the question.",
    ):
        assert phrase in MARK_TABLE_LEAN
    assert student_surface_hits(MARK_TABLE_LEAN) == []
    folded = MARK_TABLE_LEAN.casefold()
    for invented in ("invent a criterion", "assume the weighting", "use the standard rubric"):
        assert invented not in folded
    gates = (REPO / "src" / "essay_writer" / "gates.py").read_text(encoding="utf-8")
    validate = (REPO / "src" / "essay_writer" / "validate.py").read_text(encoding="utf-8")
    assert "MARK_TABLE_LEAN" not in gates
    assert "MARK_TABLE_LEAN" not in validate
    writing = (REPO / "src" / "essay_writer" / "writing_basics.py").read_text(encoding="utf-8")
    assert writing.count("MARK_TABLE_LEAN = (") == 1
