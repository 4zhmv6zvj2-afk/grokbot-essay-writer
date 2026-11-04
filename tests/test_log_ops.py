"""Operator log export and off-door handoff rows. Stable ids: AC5, AC6, AC8, AC9."""

from __future__ import annotations

import inspect
import json
import os
import zipfile
from pathlib import Path

import pytest
from helpers import mac_handoff_sequence_dir, open_sequence

from essay_writer import build_office, cursor_office
from essay_writer.debug_log import (
    EXPORT_FILENAME,
    FERRY_FILENAME,
    LOG_FILENAME,
    ML_EVENTS_FILENAME,
    SNAPSHOT_FILENAME,
    debug_log_path,
    essay_debug_export,
    ml_events_path,
)
from essay_writer.first_run import main as first_run_main
from essay_writer.ml_events import handoff_outcome, note_cli_handoff
from essay_writer.server import HANDLERS
from essay_writer.server import main as server_main
from essay_writer.shells import cursor_shell, front_office, front_office_call

LAND = "abc123land"


def _output(workspace: Path) -> Path:
    return workspace / "Essay-writer" / "MOD1004AA" / "sequences" / "1" / "output"


def _rows(essay_id: str | None = None) -> list[dict]:
    path = ml_events_path(essay_id)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_ac5_debug_export_zips_present_logs(workspace, monkeypatch, capsys):
    """AC5. With debug on, one export packs debug.log, ml-events.jsonl, and the land snapshot."""
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    monkeypatch.setattr("essay_writer.debug_log.land_sha", lambda: LAND)
    front_office_call("essay.health", {})
    assert debug_log_path().is_file()
    assert ml_events_path().is_file()

    exported = front_office_call("essay.debug.export", {})
    assert exported["ok"] is True
    assert exported["name"] == EXPORT_FILENAME
    assert exported["entries"] == [LOG_FILENAME, ML_EVENTS_FILENAME, SNAPSHOT_FILENAME, FERRY_FILENAME]
    assert "debug.log" not in (exported.get("next") or "")
    archive_path = workspace / EXPORT_FILENAME
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.namelist() == [LOG_FILENAME, ML_EVENTS_FILENAME, SNAPSHOT_FILENAME, FERRY_FILENAME]
        assert b"essay.health" in archive.read(LOG_FILENAME)
        assert b"essay.health" in archive.read(ML_EVENTS_FILENAME)
        snapshot = json.loads(archive.read(SNAPSHOT_FILENAME))
    assert snapshot == {"alive": True, "land": LAND, "tools": snapshot["tools"]}
    assert snapshot["tools"] >= 1

    ml_events_path().unlink()
    capsys.readouterr()
    server_main(["--debug-export"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    with zipfile.ZipFile(archive_path) as archive:
        assert ML_EVENTS_FILENAME not in archive.namelist()
        assert LOG_FILENAME in archive.namelist()
        assert SNAPSHOT_FILENAME in archive.namelist()
        assert FERRY_FILENAME in archive.namelist()
    assert not ml_events_path().exists()

    debug_log_path().unlink()
    archive_path.unlink()
    monkeypatch.setattr("essay_writer.debug_log.land_sha", lambda: "unknown")
    with pytest.raises(SystemExit) as caught:
        server_main(["--debug-export"])
    assert caught.value.code == 1
    refused = json.loads(capsys.readouterr().out)
    assert refused["ok"] is False
    assert refused["refused"] == "debug-export"
    assert "not on disk" in refused["reason"]
    assert not archive_path.exists()
    assert not debug_log_path().exists()
    assert not ml_events_path().exists()


def test_ac6_copy_to_mac_writes_one_ml_events_row(workspace, tmp_path, monkeypatch, capsys):
    """AC6. --copy-to-mac writes one ml-events row. It is not a tool door."""
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    mac = tmp_path / "mac"
    mac.mkdir()
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(mac))
    seq = open_sequence()
    out = _output(workspace)
    out.mkdir(parents=True)
    (out / "annotation.docx").write_bytes(b"ann-bytes")

    code = first_run_main(["--copy-to-mac", str(out)])
    assert code == 0
    capsys.readouterr()
    copied = [row for row in _rows(seq) if row.get("flag") == "--copy-to-mac"]
    assert len(copied) == 1
    assert copied[0]["kind"] == "outcome"
    assert copied[0]["tool"] == "essay-writer"
    assert copied[0]["essay_id"] == seq
    assert copied[0]["outcome"] == "copy_only"
    assert (mac_handoff_sequence_dir(mac, seq) / "annotation.docx").read_bytes() == b"ann-bytes"
    assert "--copy-to-mac" not in HANDLERS

    monkeypatch.delenv("ESSAY_WRITER_MAC_DIR", raising=False)
    first_run_main(["--copy-to-mac", str(out)])
    refused = [
        row
        for row in _rows(seq)
        if row.get("flag") == "--copy-to-mac" and row.get("outcome") == "refused"
    ]
    assert len(refused) == 1
    assert refused[0]["essay_id"] == seq
    assert handoff_outcome({"ok": True, "copied": True, "rebuilt": True}) == "rebuilt"
    assert handoff_outcome({"ok": True, "copied": True}) == "copy_only"
    assert handoff_outcome({"ok": False, "copied": False}) == "refused"


def test_ac8_build_covered_debug_export_cli_and_mcp():
    """AC8. Build covered. CLI and MCP share essay_debug_export and the handoff row."""
    assert HANDLERS["essay.debug.export"] is essay_debug_export
    assert cursor_shell()["handlers"]["essay.debug.export"] is HANDLERS["essay.debug.export"]
    assert front_office()["handlers"]["essay.debug.export"] is HANDLERS["essay.debug.export"]
    server_src = inspect.getsource(server_main)
    assert "--debug-export" in server_src
    assert "essay_debug_export" in server_src
    assert "note_cli_handoff" in inspect.getsource(first_run_main) or "_record_copy_handoff" in inspect.getsource(
        first_run_main
    )
    assert "note_cli_handoff" in inspect.getsource(_record_source())
    assert '"copy_only"' in inspect.getsource(handoff_outcome) or "copy_only" in inspect.getsource(handoff_outcome)
    assert "rebuilt" in inspect.getsource(handoff_outcome)
    assert "refused" in inspect.getsource(handoff_outcome)
    assert "events_enabled()" in inspect.getsource(note_cli_handoff)
    cursor_src = Path(cursor_office.__file__).read_text(encoding="utf-8")
    build_src = Path(build_office.__file__).read_text(encoding="utf-8")
    assert "def essay_debug_export" not in cursor_src
    assert "def essay_debug_export" not in build_src
    assert "def note_cli_handoff" not in cursor_src
    assert "def note_cli_handoff" not in build_src




def test_ac9_mid_office_start_logs_stage_settings(workspace, monkeypatch):
    """AC9. Each Cursor and Build start row records that launch's stage settings."""
    from essay_writer.build_status import finish_mid_process, reset_status
    from essay_writer.cursor_office import start_stage_mid
    from essay_writer.debug_log import (
        _start_launch_fields,
        debug_enabled,
        debug_log_path,
        note_mid_office,
    )
    from essay_writer.ml_events import _shell_event
    from essay_writer.stage_llm import stage_settings

    reset_status()
    try:
        record = {
            "where": "grokbot-cloud-computer",
            "app_path": str(workspace),
            "app": str(workspace),
            "kb1": str(workspace / "KB1"),
            "mid_office_shell": "cursor",
        }
        setup = workspace / "setup.json"
        setup.write_text(json.dumps(record) + "\n", encoding="utf-8")
        monkeypatch.delenv("ESSAY_WRITER_ROOT", raising=False)
        monkeypatch.delenv("ESSAY_WRITER_DEBUG", raising=False)
        monkeypatch.delenv("ESSAY_WRITER_OPERATOR_E2E", raising=False)
        monkeypatch.setattr("essay_writer.paths.saved_setup_path", lambda: setup)
        monkeypatch.setattr("essay_writer.cursor_office.spawn_agent", _started)
        monkeypatch.setattr("essay_writer.build_office.spawn_grok", _started)
        sequence = open_sequence()
        assert debug_enabled() is False
        cursor_off = start_stage_mid(sequence, "4b", launch=_CURSOR)
        finish_mid_process(sequence)
        build_off = start_stage_mid(sequence, "6", launch=_GROK)
        finish_mid_process(sequence)
        assert cursor_off["started"] is True and cursor_off["shell"] == "cursor"
        assert build_off["started"] is True and build_off["shell"] == "grok"
        assert not debug_log_path().exists()
        assert not ml_events_path().exists()

        monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
        assert debug_enabled() is True
        cursor_on = start_stage_mid(sequence, "4b", launch=_CURSOR)
        reset_status()
        build_on = start_stage_mid(sequence, "6", launch=_GROK)
        assert cursor_on["started"] is True and cursor_on["shell"] == "cursor"
        assert build_on["started"] is True and build_on["shell"] == "grok"
        starts = [row for row in _rows(sequence) if row.get("kind") == "shell" and row.get("event") == "start"]
        assert [(row["shell"], row["stage"]) for row in starts] == [("Cursor", "4b"), ("Build", "6")]
        _assert_launch_fields(starts[0], "4b", sequence)
        _assert_launch_fields(starts[1], "6", sequence)
        assert starts[0]["context_window"] == starts[1]["context_window"] == stage_settings("4b")["context_window"]
        assert starts[0]["reasoning"] != starts[1]["reasoning"]

        raw = ml_events_path(sequence).read_text(encoding="utf-8")
        log = debug_log_path(sequence).read_text(encoding="utf-8")
        for stage in ("4b", "6"):
            item = stage_settings(stage)
            overlay = " ".join(item["prompt_overlay"].split())
            rules = " ".join(item["rules"].split())
            assert len(overlay) > 40 and len(rules) > 40
            assert overlay[:80] not in " ".join(raw.split())
            assert overlay[:80] not in " ".join(log.split())
            assert rules[:40] not in " ".join(raw.split())
            assert rules[:40] not in " ".join(log.split())
        for row in _rows(sequence):
            assert "prompt_overlay" not in row
            assert "rules" not in row

        finish_mid_process(sequence)
        done = [row for row in _rows(sequence) if row.get("kind") == "shell" and row.get("event") == "done"]
        assert len(done) == 1
        assert done[0]["shell"] == "Build"
        for key in ("stage", "model", "reasoning", "fast", "context_window", "prompt_overlay", "rules"):
            assert key not in done[0]

        start_src = inspect.getsource(start_stage_mid)
        assert start_src.count("note_mid_office(") == 1
        assert "stage=stage" in start_src
        assert '"Cursor"' in start_src and '"Build"' in start_src
        assert "note_mid_office" not in Path(build_office.__file__).read_text(encoding="utf-8")
        assert "prompt_overlay" not in inspect.getsource(_shell_event)
        assert "prompt_overlay" not in inspect.getsource(_start_launch_fields)
        assert "rules" not in inspect.getsource(_start_launch_fields)
        assert "debug_enabled()" in inspect.getsource(note_mid_office) or "note_call" in inspect.getsource(
            note_mid_office
        )
    finally:
        reset_status()


def _started(command):
    return {
        "started": True,
        "reason": "",
        "pid": os.getpid(),
        "command": list(command),
        "stdout": None,
    }


_CURSOR = {"command": ["agent", "--print", "stage"], "settings": None}
_GROK = {"command": ["grok", "--print", "stage"], "settings": None}


def _assert_launch_fields(row: dict, stage: str, sequence: str) -> None:
    from essay_writer.stage_llm import stage_settings

    item = stage_settings(stage)
    assert row["essay_id"] == sequence
    assert row["stage"] == item["stage"] == stage
    assert row["model"] == item["model"]
    assert row["reasoning"] == item["reasoning"]
    assert row["fast"] is item["fast"]
    assert row["context_window"] == item["context_window"]
    assert "prompt_overlay" not in row
    assert "rules" not in row


def _record_source():
    from essay_writer import first_run

    return first_run._record_copy_handoff
