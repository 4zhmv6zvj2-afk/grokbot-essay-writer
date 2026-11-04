"""Layer 5. Stages call Grok Bot and Researcher. There is not a second dig."""

from pathlib import Path

from essay_writer import build_office, free_alt, stage_track
from essay_writer.dig import consensus_status, essay_dig
from essay_writer.first_run import package_root
from essay_writer.health import consensus_status as health_status
from essay_writer.server import HANDLERS
from essay_writer.shells import front_office_call
from essay_writer.specialists.grok_bot import confirm_line, sequence_delete_speech
from essay_writer.specialists.grok_bot import front_office_call as grok_speak
from essay_writer.specialists.researcher import (
    deliver_bibliography,
    deliver_saved_sources,
)


def test_stage_save_speech_comes_from_grok_bot():
    assert confirm_line("1", None).startswith(
        "Confirm to save the final look and go to **Stage 2 — "
    )
    assert confirm_line("10", None) == "Confirm to save the final look. The tool does not submit."
    stage = Path(stage_track.__file__).read_text(encoding="utf-8")
    spine = Path(stage_track.__file__).resolve().parent.joinpath("spine.py").read_text(encoding="utf-8")
    assert "essay_writer.spine import save_line" in stage
    assert "essay_writer.spine import gate_save" in stage
    assert "essay_writer.specialists.grok_bot import confirm_line" in spine
    assert "essay_writer.specialists.grok_bot import confirm_gate" in spine
    assert front_office_call is grok_speak
    assert "This deletes only" in sequence_delete_speech("MOD1004AA-2", computer=False)


def test_stored_sources_have_one_researcher_writer():
    stage = Path(stage_track.__file__).read_text(encoding="utf-8")
    spine = Path(stage_track.__file__).resolve().parent.joinpath("spine.py").read_text(encoding="utf-8")
    office = Path(build_office.__file__).read_text(encoding="utf-8")
    leftovers = Path(free_alt.__file__).read_text(encoding="utf-8")
    assert "stage_bibliography" in stage
    assert "deliver_bibliography" in spine
    assert "deliver_saved_sources" in office
    assert "essay_writer.specialists.researcher import real_4a_bibliography" in leftovers
    assert "def ship_4a" not in stage
    assert "def ship_4a" not in office
    assert HANDLERS["essay.dig"] is essay_dig
    assert health_status is consensus_status
    assert deliver_bibliography.__module__ == "essay_writer.specialists.researcher"
    assert deliver_saved_sources.__module__ == "essay_writer.specialists.researcher"


def test_held_runner_is_not_in_this_layer():
    root = package_root() / "src" / "essay_writer"
    grok = (root / "specialists" / "grok_bot.py").read_text(encoding="utf-8")
    spine = (root / "spine.py").read_text(encoding="utf-8")
    stage = (root / "stage_track.py").read_text(encoding="utf-8")
    office = (root / "build_office.py").read_text(encoding="utf-8")
    status = (root / "build_status.py").read_text(encoding="utf-8")
    assert 'kind": "confirm"' in grok
    assert "def confirm_card" in grok
    assert "AUTO_START" in spine
    assert "advances_without_confirm" in stage
    assert "def confirm_card" not in office
    assert "def essay_stage" not in office
    assert 'kind": "watch"' not in status
    assert "HEARTBEAT_SECONDS = 300" in status
    assert "advances_without_confirm" in status
    assert "import subprocess" not in status
    assert "Popen" not in status
