"""Layer 6. The spine routes to the specialists and does not score the constitution."""

from pathlib import Path

import pytest

from essay_writer import stage_run
from essay_writer.server import HANDLERS
from essay_writer.spine import (
    advances_without_confirm,
    final_review,
    gate_save,
    save_line,
    stage_bibliography,
)
from essay_writer.stage_run import essay_stage as tracked


def test_stage_door_is_the_track_export():
    assert tracked is HANDLERS["essay.stage"]
    assert gate_save.__module__ == "essay_writer.spine"
    assert save_line("10", None) == "Confirm to save the final look. The tool does not submit."
    assert stage_bibliography.__module__ == "essay_writer.spine"


@pytest.mark.parametrize("case_id", [pytest.param("essay-left-a1", id="essay-left-a1")])
def test_spine_does_not_keep_a_second_constitution_check(case_id):
    """essay-left-a1: The spine keeps no second constitution check, and stage 4a still stores a brief answer."""
    assert case_id == "essay-left-a1"
    spine = (
        Path(stage_run.__file__).resolve().parent.joinpath("spine.py").read_text(encoding="utf-8")
    )
    stage = Path(stage_run.__file__).read_text(encoding="utf-8")
    assert "def assignment_gate" not in spine
    assert "def assignment_gate(" not in stage
    # The brief-answer store rides in on its own import; a second check does not.
    assert "from essay_writer.assignment_gate import store_brief_answer" in stage
    assert stage.count("essay_writer.spine import gate_save") == 1
    assert stage.count("essay_writer.spine import final_review") == 1
    assert stage.count("essay_writer.spine import stage_bibliography") == 1
    assert "quiet_stage5" in stage
    assert advances_without_confirm("5") == "6"
    assert advances_without_confirm("7") is None
    assert advances_without_confirm("8") is None
    assert advances_without_confirm("9") is None
    assert final_review.__module__ == "essay_writer.spine"
