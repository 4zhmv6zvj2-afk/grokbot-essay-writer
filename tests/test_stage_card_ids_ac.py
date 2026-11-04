"""Stage card ids. Stable ids: AC1, AC2, AC3."""

from helpers import ESSAY, open_sequence, picked

from essay_writer.health import essay_health
from essay_writer.projects import essay_projects
from essay_writer.server import HANDLERS
from essay_writer.stage_llm import stage_settings
from essay_writer.stage_track import essay_stage, render_tracking

MODULE = ESSAY


def test_ac1_stage1_tracking_and_card_name_sequence_id(workspace):
    seq = open_sequence()
    look = "The task is a report on one named chain."
    draft = essay_stage(seq, "1", "draft", look)
    assert draft["card"]["essay_id"] == seq
    note = render_tracking("1", status="draft", look=look, essay_id=seq)
    assert f"Sequence id: {seq}" in note
    saved = essay_stage(seq, "1", "confirm", look, **picked(draft))
    assert saved["stored"] is True
    folder = workspace / "Essay-writer" / MODULE / "sequences" / "1" / "tracking" / "1.md"
    final = folder.read_text(encoding="utf-8")
    assert f"Sequence id: {seq}" in final


def test_ac2_health_and_continue_show_one_card_id(workspace):
    seq = open_sequence()
    row = essay_projects("continue")["rows"][0]
    assert row["essay_id"] == seq
    assert "module" not in row
    assert "sequence_id" not in row
    pack = essay_health()["packs"][0]
    assert pack["essay_id"] == seq
    assert "module" not in pack
    assert "sequence_id" not in pack
    archive = essay_projects("archive")
    assert archive["modules"] == [MODULE]


def test_ac3_build_covered_shared_handlers():
    assert HANDLERS["essay.health"] is essay_health
    assert HANDLERS["essay.projects"] is essay_projects
    assert HANDLERS["essay.stage"] is essay_stage
    overlay = stage_settings("1")["prompt_overlay"]
    assert "tracking" in overlay
