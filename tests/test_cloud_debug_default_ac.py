"""Cloud-computer where does not turn operator debug on.

AC1: where=grokbot-cloud-computer, ESSAY_WRITER_DEBUG unset, no debug:true
     leaves debug.log and ml-events.jsonl unwritten.
AC2: ESSAY_WRITER_DEBUG or setup debug:true still writes both files.
AC3: Build covered. Cursor and Grok Build share that default.
"""

from __future__ import annotations

import inspect
import json
import os
from pathlib import Path

from helpers import open_sequence

from essay_writer.build_status import finish_mid_process, reset_status
from essay_writer.cursor_office import start_stage_mid
from essay_writer.debug_log import (
    LOG_FILENAME,
    ML_EVENTS_FILENAME,
    debug_enabled,
    debug_log_path,
    essay_debug_export,
    ml_events_path,
    note_call,
    note_mid_office,
    operator_debug_default,
)
from essay_writer.first_run import main as first_run_main
from essay_writer.ml_events import events_enabled
from essay_writer.paths import load_saved_setup
from essay_writer.shells import front_office_call

REPO = Path(__file__).resolve().parents[1]
CURSOR_LAUNCH = {"command": ["agent", "--print", "stage"], "settings": None}
GROK_LAUNCH = {"command": ["grok", "--print", "stage"], "settings": None}


def _started(command):
    return {
        "started": True,
        "reason": "",
        "pid": os.getpid(),
        "command": list(command),
        "stdout": None,
    }


def _load_cloud_setup(workspace: Path, monkeypatch, **extra) -> Path:
    """Friend-cloud setup.json. ESSAY_WRITER_ROOT stays unset so the record is read."""
    record = {
        "where": "grokbot-cloud-computer",
        "app_path": str(workspace),
        "app": str(workspace),
        "kb1": str(workspace / "KB1"),
        "mid_office_shell": extra.pop("mid_office_shell", "grok_build"),
    }
    record.update(extra)
    path = workspace / "setup.json"
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    monkeypatch.delenv("ESSAY_WRITER_ROOT", raising=False)
    monkeypatch.delenv("ESSAY_WRITER_DEBUG", raising=False)
    monkeypatch.delenv("ESSAY_WRITER_OPERATOR_E2E", raising=False)
    monkeypatch.setattr("essay_writer.paths.saved_setup_path", lambda: path)
    return path


def _assert_operator_logs_absent(workspace: Path) -> None:
    assert debug_log_path() == workspace / LOG_FILENAME
    assert ml_events_path() == workspace / ML_EVENTS_FILENAME
    assert not debug_log_path().exists()
    assert not ml_events_path().exists()


def test_ac1_cloud_where_leaves_debug_log_and_ml_events_off(workspace, monkeypatch):
    """AC1. Cloud where alone does not write debug.log or ml-events.jsonl."""
    path = _load_cloud_setup(workspace, monkeypatch)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["where"] == "grokbot-cloud-computer"
    assert saved.get("debug") is not True
    loaded = load_saved_setup()
    assert loaded is not None
    assert loaded["where"] == "grokbot-cloud-computer"
    assert loaded.get("debug") is not True
    assert operator_debug_default() is False
    assert debug_enabled() is False
    assert events_enabled() is False

    report = front_office_call("essay.health", {})
    assert report["alive"] is True
    note_call("essay.health", {}, result={"ok": True, "alive": True, "wrote": False})
    _assert_operator_logs_absent(workspace)

    note = (REPO / "docs" / "operator-log.md").read_text(encoding="utf-8")
    assert "grokbot-cloud-computer" in note
    assert "does not turn it on by itself" in note


def test_ac2_env_or_setup_debug_turns_operator_logs_on(workspace, monkeypatch):
    """AC2. ESSAY_WRITER_DEBUG or setup debug:true still writes both operator files."""
    _load_cloud_setup(workspace, monkeypatch)
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    assert operator_debug_default() is False
    assert debug_enabled() is True
    assert events_enabled() is True
    front_office_call("essay.health", {})
    debug_text = debug_log_path().read_text(encoding="utf-8")
    ml_text = ml_events_path().read_text(encoding="utf-8")
    assert "essay.health" in debug_text
    assert '"tool":"essay.health"' in ml_text

    debug_log_path().unlink()
    ml_events_path().unlink()
    monkeypatch.delenv("ESSAY_WRITER_DEBUG", raising=False)
    path = _load_cloud_setup(workspace, monkeypatch, debug=True)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["where"] == "grokbot-cloud-computer"
    assert saved["debug"] is True
    assert operator_debug_default() is False
    assert debug_enabled() is True
    assert events_enabled() is True
    front_office_call("essay.health", {})
    assert "essay.health" in debug_log_path().read_text(encoding="utf-8")
    assert '"tool":"essay.health"' in ml_events_path().read_text(encoding="utf-8")


def test_ac7_cloud_where_keeps_logs_off_for_copy_and_export(workspace, monkeypatch, capsys):
    """AC7. Cloud where alone stays off for copy and export. Env and setup debug still turn logs on."""
    _load_cloud_setup(workspace, monkeypatch)
    assert operator_debug_default() is False
    assert debug_enabled() is False
    assert events_enabled() is False
    seq = open_sequence()
    out = workspace / "Essay-writer" / "MOD1004AA" / "sequences" / "1" / "output"
    out.mkdir(parents=True)
    (out / "annotation.docx").write_bytes(b"ann")
    mac = workspace / "mac-off"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(mac))
    first_run_main(["--copy-to-mac", str(out)])
    capsys.readouterr()
    monkeypatch.setattr("essay_writer.debug_log.land_sha", lambda: "unknown")
    refused = essay_debug_export()
    assert refused["ok"] is False
    _assert_operator_logs_absent(workspace)

    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    assert debug_enabled() is True
    assert events_enabled() is True
    front_office_call("essay.health", {})
    assert debug_log_path().is_file()
    assert ml_events_path().is_file()

    debug_log_path().unlink()
    ml_events_path().unlink()
    monkeypatch.delenv("ESSAY_WRITER_DEBUG", raising=False)
    _load_cloud_setup(workspace, monkeypatch, debug=True)
    assert operator_debug_default() is False
    assert debug_enabled() is True
    assert events_enabled() is True
    front_office_call("essay.health", {})
    assert "essay.health" in debug_log_path().read_text(encoding="utf-8")
    assert '"tool":"essay.health"' in ml_events_path().read_text(encoding="utf-8")
    assert seq.startswith("MOD1004AA-")


def test_ac3_build_covered_cursor_and_grok_build_share_debug_default(workspace, monkeypatch):
    """AC3. Build covered. Cursor and Grok Build share debug_enabled. Cloud where stays off."""
    reset_status()
    try:
        _load_cloud_setup(workspace, monkeypatch, mid_office_shell="cursor")
        assert debug_enabled() is False
        assert events_enabled() is debug_enabled()
        sequence = open_sequence()
        monkeypatch.setattr("essay_writer.cursor_office.spawn_agent", _started)
        monkeypatch.setattr("essay_writer.build_office.spawn_grok", _started)

        cursor_off = start_stage_mid(sequence, "6", launch=CURSOR_LAUNCH)
        finish_mid_process(sequence)
        grok_off = start_stage_mid(sequence, "8", launch=GROK_LAUNCH)
        finish_mid_process(sequence)
        assert cursor_off["started"] is True
        assert cursor_off["shell"] == "cursor"
        assert grok_off["started"] is True
        assert grok_off["shell"] == "grok"
        note_mid_office("start", sequence, "Cursor")
        note_mid_office("start", sequence, "Build")
        _assert_operator_logs_absent(workspace)

        monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
        assert debug_enabled() is True
        assert events_enabled() is True
        cursor_on = start_stage_mid(sequence, "6", launch=CURSOR_LAUNCH)
        finish_mid_process(sequence)
        grok_on = start_stage_mid(sequence, "8", launch=GROK_LAUNCH)
        assert cursor_on["started"] is True
        assert grok_on["started"] is True
        text = debug_log_path(sequence).read_text(encoding="utf-8")
        assert "Mid-office start Cursor." in text
        assert "Mid-office start Build." in text
        shells = []
        for line in ml_events_path(sequence).read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("kind") == "shell":
                shells.append((row.get("shell"), row.get("event")))
        assert ("Cursor", "start") in shells
        assert ("Build", "start") in shells

        start_src = inspect.getsource(start_stage_mid)
        assert start_src.count("note_mid_office(") == 1
        assert '"Cursor"' in start_src
        assert '"Build"' in start_src
        assert "note_call" in inspect.getsource(note_mid_office)
        assert "debug_enabled()" in inspect.getsource(note_call)
        assert "return debug_enabled()" in inspect.getsource(events_enabled)
        build_src = (REPO / "src" / "essay_writer" / "build_office.py").read_text(encoding="utf-8")
        assert "note_mid_office" not in build_src
        assert "debug.log" not in build_src
    finally:
        reset_status()
