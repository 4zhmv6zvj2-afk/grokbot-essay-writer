"""Stage dispatcher routes id refusal and confirm through the same behaviour."""

from helpers import open_sequence, picked, write_upload

from essay_writer.stage_track import essay_stage


def test_bad_id_refuses_before_a_branch(workspace):
    result = essay_stage("bad id", "1", "draft")
    assert result["ok"] is False
    assert result["refused"] == "essay-id"


def test_draft_then_confirm_uses_the_split_helpers(workspace):
    write_upload(workspace)
    seq = open_sequence()
    draft = essay_stage(seq, "1", "draft", "The brief asks for a report.")
    assert draft["ok"] is True
    assert draft["stage"] == "1"
    confirm = essay_stage(seq, "1", "confirm", "The brief asks for a report.", **picked(draft))
    assert confirm["ok"] is True
    assert confirm["stored"] is True
