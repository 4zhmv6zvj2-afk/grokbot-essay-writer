"""Cursor mid-office launch uses agent --model from stage_settings."""

import json

import pytest
from helpers import open_sequence

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import RESIDUALS, cursor_stage_launch, stage_host_launch
from essay_writer.server import main as server_main
from essay_writer.setup import SHELL_GROK_BUILD
from essay_writer.stage_llm import STAGE_KEYS, stage_settings
from essay_writer.stage_track import essay_stage


def test_cursor_launch_puts_model_and_effort_on_the_model_flag():
    for stage in STAGE_KEYS:
        item = stage_settings(stage)
        launch = cursor_stage_launch(stage)
        assert launch["source"] == "essay_writer.stage_llm.stage_settings"
        assert launch["settings"] == item
        command = launch["command"]
        assert command == ["agent", "--model", f"grok-4.7-{item['reasoning']}"]
        assert command[command.index("--model") + 1] == f"{item['model']}-{item['reasoning']}"
        assert not command[-1].endswith("-fast")
        assert "--effort" not in command
        assert "--context" not in command
        assert "--context-window" not in command
        assert "--rules" not in command
        assert "context=" not in " ".join(command)
        assert "Context window" not in " ".join(command)
        assert str(item["context_window"]) not in command
        assert "prompt text" in launch["context_residual"]
        assert "Cannot use this model" in launch["context_residual"]
        assert launch["context_residual_id"] == "cursor-context-flag"
        assert launch["context_residual"] == RESIDUALS["cursor-context-flag"]
        assert item["fast"] is False


def test_cursor_effort_ids_match_the_stage_locks():
    effort = {
        stage: cursor_stage_launch(stage)["command"][-1].rsplit("-", 1)[-1]
        for stage in STAGE_KEYS
    }
    assert effort["4b"] == "xhigh"
    assert effort["5"] == "xhigh"
    assert effort["eqr"] == "xhigh"
    assert effort["10"] == "medium"
    assert effort["1"] == "high"
    assert all(effort[stage] == "high" for stage in ("6", "7", "8"))


def test_build_launch_still_passes_model_and_effort():
    for stage in STAGE_KEYS:
        item = stage_settings(stage)
        command = stage_launch(stage)["command"]
        assert command[command.index("--model") + 1] == item["model"] == "grok-4.7"
        assert command[command.index("--effort") + 1] == item["reasoning"]
        assert stage_launch(stage)["context_residual_id"] == "context-flag"


def test_cursor_launch_refuses_fast(monkeypatch):
    def fast_on(stage, genre=None):
        item = dict(stage_settings(stage, genre))
        item["fast"] = True
        return item

    monkeypatch.setattr("essay_writer.cursor_office.stage_settings", fast_on)
    with pytest.raises(RuntimeError, match="fast"):
        cursor_stage_launch("1")


def test_cursor_stage_launch_cli_prints_the_4b_model(capsys):
    server_main(["--cursor-stage-launch", "4b"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == ["agent", "--model", "grok-4.7-xhigh"]
    assert payload["settings"]["context_window"] == 256_000
    assert "256000" not in payload["command"]
    assert "500000" not in payload["command"]
    assert payload["context_residual_id"] == "cursor-context-flag"

    with pytest.raises(SystemExit) as caught:
        server_main(["--cursor-stage-launch", "nope"])
    assert caught.value.code == "unknown stage nope"


def test_stage_door_uses_the_cursor_model_id(workspace):
    seq = open_sequence()
    draft = essay_stage(seq, "1", "draft", "The task asks for a short report.")
    assert draft["ok"] is True, draft
    launch = draft["mid_office_launch"]
    assert launch["command"] == ["agent", "--model", "grok-4.7-high"]
    assert launch["shell"] == "cursor"
    assert "256000" not in launch["command"]


def test_stage_door_uses_grok_flags_when_build_is_stored(workspace, monkeypatch):
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_GROK_BUILD)
    command = stage_host_launch("5")["command"]
    assert command[0] == "grok"
    assert command[command.index("--model") + 1] == "grok-4.7"
    assert command[command.index("--effort") + 1] == "xhigh"
    seq = open_sequence()
    draft = essay_stage(seq, "1", "draft", "The task asks for a short report.")
    assert draft["ok"] is True, draft
    command = draft["mid_office_launch"]["command"]
    assert command[0] == "grok"
    assert command[command.index("--model") + 1] == "grok-4.7"
    assert command[command.index("--effort") + 1] == "high"
