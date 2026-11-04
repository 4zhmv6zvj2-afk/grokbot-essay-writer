"""FO wipe for the app-folder run log. Speech only; no UI button."""

import inspect
import json

from helpers import open_sequence

from essay_writer.debug_log import (
    LOG_FILENAME,
    ML_EVENTS_FILENAME,
    debug_log_wipe_speech,
    essay_debug_wipe,
    wipe_operator_log_files,
)
from essay_writer.doors import DOORS
from essay_writer.server import HANDLERS, INSTRUCTIONS
from essay_writer.setup import essay_setup
from essay_writer.shells import cursor_shell, front_office, front_office_call

PHRASES = (
    "delete the logs",
    "clear debug log",
    "Clear the debug log.",
    "wipe the run log",
    "please delete debug log",
)


def test_debug_log_wipe_speech_matches_clear_synonyms():
    for phrase in PHRASES:
        assert debug_log_wipe_speech(phrase) is True
    assert debug_log_wipe_speech("delete this module") is False
    assert debug_log_wipe_speech("") is False


def test_front_office_call_clears_both_operator_logs_in_one_phrase(workspace, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    open_sequence()
    front_office_call("essay.health", {})
    log_path = workspace / LOG_FILENAME
    ml_path = workspace / ML_EVENTS_FILENAME
    ml_path.write_text('{"kind":"outcome","tool":"essay.health"}\n', encoding="utf-8")
    assert log_path.is_file()
    assert log_path.stat().st_size > 0
    assert ml_path.is_file()

    wiped = front_office_call("essay.debug.wipe", {"speech": "clear debug log"})
    assert wiped["ok"] is True
    assert wiped["cleared"] is True
    assert wiped["wrote"] is True
    assert wiped["cleared_debug"] is True
    assert wiped["cleared_ml_events"] is True
    assert not log_path.exists()
    assert not ml_path.exists()

    again = front_office_call("essay.debug.wipe", {"speech": "delete the logs"})
    assert again["ok"] is True
    assert again["cleared"] is False
    assert again["wrote"] is False
    assert "debug.log" not in json.dumps(wiped)
    assert "ml-events" not in json.dumps(wiped)
    assert "debug.log" not in json.dumps(again)
    assert "debug.log" not in wiped["next"]
    assert wiped["next"] == "Cleared the run logs."


def test_wipe_operator_log_files_is_idempotent_when_ml_jsonl_is_missing(workspace):
    log_path = workspace / LOG_FILENAME
    log_path.write_text("line\n", encoding="utf-8")
    removed = wipe_operator_log_files()
    assert removed == {LOG_FILENAME: True, ML_EVENTS_FILENAME: False}
    assert not log_path.exists()
    assert wipe_operator_log_files() == {LOG_FILENAME: False, ML_EVENTS_FILENAME: False}


def test_refused_speech_does_not_touch_the_logs(workspace, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    front_office_call("essay.health", {})
    log_path = workspace / LOG_FILENAME
    ml_path = workspace / ML_EVENTS_FILENAME
    ml_path.write_text("{}\n", encoding="utf-8")
    assert log_path.is_file()

    refused = front_office_call("essay.debug.wipe", {"speech": "archive the module"})
    assert refused["ok"] is False
    assert refused["refused"] == "debug-wipe"
    assert log_path.is_file()
    assert ml_path.is_file()


def test_cursor_and_grok_build_share_the_wipe_handler():
    assert cursor_shell()["handlers"]["essay.debug.wipe"] is front_office()["handlers"]["essay.debug.wipe"]
    assert cursor_shell()["handlers"]["essay.debug.wipe"] is HANDLERS["essay.debug.wipe"]
    assert cursor_shell()["handlers"]["essay.debug.wipe"] is essay_debug_wipe


def test_no_wipe_button_or_settings_toggle(workspace):
    setup_src = inspect.getsource(essay_setup)
    assert "wipe" not in setup_src.casefold()
    assert "essay.debug.wipe" in INSTRUCTIONS
    assert "no settings toggle" in INSTRUCTIONS.casefold()
    assert "no chat button" in INSTRUCTIONS.casefold()
    door = next(item for item in DOORS if item["tool"] == "essay.debug.wipe")
    assert door["confirm"] is None
    assert "no chat card" in door["description"].casefold()
    assert "debug.log" not in door["description"]
