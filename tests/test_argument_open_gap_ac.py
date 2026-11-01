"""An unsettled point is stated, not filled. Stable ids: AC1–AC3.

Stages 5 and 8 carry one bullet: when the opened sources do not settle a
point, the draft says the evidence is mixed or thin instead of asserting a
view the sources do not hold. Prompt text only, one copy in the shared helper
note. No new pass/fail gate.
"""

from pathlib import Path

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.stage_llm import stage_settings
from essay_writer.student_voice import student_surface_hits
from essay_writer.writing_basics import OPEN_GAP, basics_lines

REPO = Path(__file__).resolve().parents[1]
HELPERS = REPO / "docs" / "academic-writing-helpers.md"
GENRES = (None, "diary", "essay", "report")
WRITING = ("5", "8")
OTHER = ("1", "2", "3", "4a", "4b", "6", "7", "9", "10")


def test_ac1_writing_stages_carry_the_open_gap_bullet():
    """AC1. Stage 5 and stage 8 carry it for every genre; other stages do not."""
    for stage in WRITING:
        for genre in GENRES:
            item = stage_settings(stage, genre)
            assert OPEN_GAP in item["rules"]
            assert OPEN_GAP in item["prompt_overlay"]
            assert student_surface_hits(item["prompt_overlay"]) == []
    for stage in OTHER:
        assert OPEN_GAP not in stage_settings(stage)["rules"]


def test_ac2_the_helper_note_and_both_launchers_read_the_same_bullet():
    """AC2. One copy in the helper note, read by both launchers."""
    helpers = HELPERS.read_text(encoding="utf-8")
    assert helpers.count(OPEN_GAP) == 2
    for stage in WRITING:
        for line in basics_lines(stage):
            assert line in helpers
        shared = stage_settings(stage)
        assert stage_launch(stage)["settings"]["rules"] == shared["rules"]
        cursor = cursor_stage_launch(stage)
        assert cursor["settings"]["rules"] == shared["rules"]
        command = stage_launch(stage)["command"]
        assert OPEN_GAP in command[command.index("--rules") + 1]


def test_ac3_the_bullet_keeps_the_gap_open_and_stays_prompt_only():
    """AC3. The gap is named, not filled. No gate and no invented settled view."""
    for phrase in (
        "When the sources you opened do not settle a point",
        "say that the evidence is mixed or thin",
        "Do not fill the gap with an assertion",
        "do not present one source as the settled view",
        "A gap is part of the answer, not a line to hide.",
    ):
        assert phrase in OPEN_GAP
    assert student_surface_hits(OPEN_GAP) == []
    folded = OPEN_GAP.casefold()
    for invented in ("invent a source", "take a side", "state the opposite", "assume the answer"):
        assert invented not in folded
    gates = (REPO / "src" / "essay_writer" / "gates.py").read_text(encoding="utf-8")
    validate = (REPO / "src" / "essay_writer" / "validate.py").read_text(encoding="utf-8")
    assert "OPEN_GAP" not in gates
    assert "OPEN_GAP" not in validate
    writing = (REPO / "src" / "essay_writer" / "writing_basics.py").read_text(encoding="utf-8")
    assert writing.count("OPEN_GAP = (") == 1
