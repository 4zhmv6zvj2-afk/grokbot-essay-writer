"""Layer 6. The spine routes to the specialists and does not score the constitution."""

from pathlib import Path

from essay_writer import stage_track
from essay_writer.server import HANDLERS
from essay_writer.spine import (
    advances_without_confirm,
    essay_stage,
    final_review,
    gate_save,
    save_line,
    stage_bibliography,
)
from essay_writer.stage_track import essay_stage as tracked


def test_stage_door_is_the_spine_export():
    assert essay_stage is tracked is HANDLERS["essay.stage"]
    assert gate_save.__module__ == "essay_writer.spine"
    assert save_line("10", None) == "Confirm to save the final look. The tool does not submit."
    assert stage_bibliography.__module__ == "essay_writer.spine"


def test_spine_does_not_keep_a_second_constitution_check():
    spine = Path(stage_track.__file__).resolve().parent.joinpath("spine.py").read_text(encoding="utf-8")
    stage = Path(stage_track.__file__).read_text(encoding="utf-8")
    assert "def assignment_gate" not in spine
    assert "assignment_gate" not in stage
    assert "essay_writer.spine import gate_save" in stage
    assert "essay_writer.spine import final_review" in stage
    assert "essay_writer.spine import stage_bibliography" in stage
    assert "quiet_stage5" in stage
    assert advances_without_confirm("5") == "6"
    assert advances_without_confirm("7") is None
    assert advances_without_confirm("8") is None
    assert advances_without_confirm("9") is None
    assert final_review.__module__ == "essay_writer.spine"
