"""Layer 5. Stages call Grok Bot and Researcher. There is not a second dig."""

from essay_writer.build_status import HEARTBEAT_SECONDS
from essay_writer.dig import consensus_status, essay_dig
from essay_writer.health import consensus_status as health_status
from essay_writer.server import HANDLERS
from essay_writer.shells import front_office_call
from essay_writer.specialists.grok_bot import confirm_line, sequence_delete_speech
from essay_writer.specialists.grok_bot import front_office_call as grok_speak
from essay_writer.specialists.researcher import (
    deliver_bibliography,
    deliver_saved_sources,
)
from essay_writer.spine import advances_without_confirm, stage_uses_confirm_card


def test_stage_save_speech_comes_from_grok_bot():
    assert confirm_line("1", None).startswith(
        "Confirm to save the final look and go to **Stage 2 — "
    )
    assert confirm_line("10", None) == "Confirm to save the final look. The tool does not submit."
    assert front_office_call is grok_speak
    assert "This deletes only" in sequence_delete_speech("MOD1004AA-2", computer=False)


def test_stored_sources_have_one_researcher_writer():
    assert HANDLERS["essay.dig"] is essay_dig
    assert health_status is consensus_status
    assert deliver_bibliography.__module__ == "essay_writer.specialists.researcher"
    assert deliver_saved_sources.__module__ == "essay_writer.specialists.researcher"


def test_held_runner_is_not_in_this_layer():
    assert advances_without_confirm("5") == "6"
    assert advances_without_confirm("1") is None
    assert stage_uses_confirm_card("5") is False
    assert stage_uses_confirm_card("1") is True
    assert HEARTBEAT_SECONDS == 300
    assert front_office_call is grok_speak
