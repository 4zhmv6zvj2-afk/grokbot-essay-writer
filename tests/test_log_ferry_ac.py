"""Zip ferry for catch-runs. Stable ids: AC1, AC2, AC3, AC4, AC5.

AC1: export zip holds the full debug.log and ml-events.jsonl for a fixture run.
AC2: those members are the whole files, not a 32KB stub, and a clipped write is refused.
AC3: default debug stays off unless setup or ESSAY_WRITER_DEBUG turns it on.
AC4: FO, docs, and health name zip-for-ferry and say not to paste.
AC5: a mid-office run with debug on exports a zip Cursor can open. No Remy paste.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import zipfile
from pathlib import Path

from helpers import open_sequence

from essay_writer import debug_log
from essay_writer.cursor_office import start_stage_mid
from essay_writer.debug_log import (
    CHAT_PASTE_CEILING,
    EXPORT_FILENAME,
    FERRY_FILENAME,
    FERRY_ZIP_TIP,
    INCOMPLETE_EXPORT_REASON,
    LOG_FILENAME,
    ML_EVENTS_FILENAME,
    debug_enabled,
    debug_log_path,
    essay_debug_export,
    ferry_tip_sha,
    log_word_step,
    ml_events_path,
    note_call,
    operator_debug_default,
)
from essay_writer.doors import DOORS
from essay_writer.health import essay_health
from essay_writer.server import HANDLERS, INSTRUCTIONS
from essay_writer.shells import cursor_shell, front_office, front_office_call

REPO = Path(__file__).resolve().parents[1]
PACK = "Essay-writer/MOD1004AA/sequences/1/pack.json"
TAIL = b"FERRY-TAIL-PAST-32KB\n"
HEAD = b"FERRY-HEAD\n"
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


def _cloud_setup(workspace: Path, monkeypatch, **extra) -> None:
    record = {
        "where": "grokbot-cloud-computer",
        "app_path": str(workspace),
        "app": str(workspace),
        "kb1": str(workspace / "KB1"),
        "mid_office_shell": "cursor",
    }
    record.update(extra)
    path = workspace / "setup.json"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    monkeypatch.delenv("ESSAY_WRITER_ROOT", raising=False)
    monkeypatch.delenv("ESSAY_WRITER_DEBUG", raising=False)
    monkeypatch.delenv("ESSAY_WRITER_OPERATOR_E2E", raising=False)
    monkeypatch.setattr("essay_writer.paths.saved_setup_path", lambda: path)


def _log_members(archive: zipfile.ZipFile) -> list[str]:
    return [
        name
        for name in archive.namelist()
        if name == LOG_FILENAME
        or name.endswith("/" + LOG_FILENAME)
        or name == ML_EVENTS_FILENAME
        or name.endswith("/" + ML_EVENTS_FILENAME)
    ]


def _assert_log_members_match_disk(archive: zipfile.ZipFile, workspace: Path) -> None:
    names = _log_members(archive)
    assert any(name.endswith(LOG_FILENAME) for name in names)
    assert any(name.endswith(ML_EVENTS_FILENAME) for name in names)
    for name in names:
        disk = workspace / name
        payload = archive.read(name)
        assert disk.is_file()
        assert payload == disk.read_bytes()
        assert payload
        info = archive.getinfo(name)
        assert info.file_size == len(payload)


def test_ac1_export_zip_contains_full_debug_log_and_ml_events(workspace, monkeypatch):
    """AC1. One export packs the full debug.log and ml-events.jsonl for a fixture run."""
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    sequence = open_sequence()
    pack = workspace / PACK
    pack.parent.mkdir(parents=True, exist_ok=True)
    pack.write_text("{}\n", encoding="utf-8")
    front_office_call("essay.health", {})
    note_call(
        "essay.stage",
        {"essay_id": sequence, "stage": "4b", "confirmPhase": "read"},
        result={"ok": True, "essay_id": sequence, "wrote": False, "pack_path": PACK},
    )
    log_word_step("render", sequence, pack_path=PACK, stage="4b")
    exported = essay_debug_export()
    assert exported["ok"] is True
    assert exported["complete"] is True
    assert exported["ferry"] == "zip"
    assert exported["paste"] is False
    assert exported["sliced"] is False
    assert sequence in exported["essay_ids"]
    assert PACK in exported["pack_paths"]
    assert exported["ferry_tip"] == FERRY_ZIP_TIP
    archive_path = workspace / EXPORT_FILENAME
    with zipfile.ZipFile(archive_path) as archive:
        _assert_log_members_match_disk(archive, workspace)
        manifest = json.loads(archive.read(FERRY_FILENAME))
        assert manifest["complete"] is True
        assert manifest["paste"] is False
        assert manifest["sliced"] is False
        assert manifest["ferry"] == "zip"
        assert sequence in manifest["essay_ids"]
        assert PACK in manifest["pack_paths"]
        sequence_log = archive.read(f"Essay-writer/MOD1004AA/sequences/1/{LOG_FILENAME}")
        sequence_events = archive.read(f"Essay-writer/MOD1004AA/sequences/1/{ML_EVENTS_FILENAME}")
    assert sequence.encode() in sequence_log
    assert PACK.encode() in sequence_log
    assert sequence.encode() in sequence_events
    assert b"FERRY-TAIL" not in json.dumps(exported).encode()


def test_ac2_zip_contents_are_complete_not_a_truncated_stub(workspace, monkeypatch):
    """AC2. Zip members are the whole logs. A write clipped at the paste ceiling is refused."""
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    line = (
        b"ferry-pad essay_id=MOD1004AA-1 "
        b"pack_path=Essay-writer/MOD1004AA/sequences/1/pack.json\n"
    )
    blob = HEAD + (line * 800) + TAIL
    assert len(blob) > CHAT_PASTE_CEILING
    assert TAIL in blob[CHAT_PASTE_CEILING:]
    debug_log_path().write_bytes(blob)
    ml_events_path().write_bytes(blob)
    exported = essay_debug_export()
    assert exported["ok"] is True
    assert exported["sliced"] is False
    assert "MOD1004AA-1" in exported["essay_ids"]
    assert PACK in exported["pack_paths"]
    archive_path = workspace / EXPORT_FILENAME
    with zipfile.ZipFile(archive_path) as archive:
        for name in (LOG_FILENAME, ML_EVENTS_FILENAME):
            info = archive.getinfo(name)
            payload = archive.read(name)
            assert payload == blob
            assert payload.startswith(HEAD)
            assert payload.endswith(TAIL)
            assert info.file_size == len(blob)
            assert info.file_size > CHAT_PASTE_CEILING
            assert info.compress_size < info.file_size
        manifest = json.loads(archive.read(FERRY_FILENAME))
    assert manifest["chat_paste_ceiling"] == CHAT_PASTE_CEILING
    assert manifest["sliced"] is False
    logged = {item["name"]: item for item in manifest["members"]}
    assert logged[LOG_FILENAME]["bytes"] == len(blob)
    assert logged[LOG_FILENAME]["sha256"] == hashlib.sha256(blob).hexdigest()
    assert logged[ML_EVENTS_FILENAME]["bytes"] == len(blob)
    export_src = inspect.getsource(essay_debug_export)
    write_src = inspect.getsource(debug_log._write_debug_zip)
    assert "read_bytes" in export_src
    assert "CHAT_PASTE_CEILING" not in export_src
    assert "ZIP_DEFLATED" in write_src
    assert "[:CHAT_PASTE_CEILING]" not in write_src

    real_write = debug_log._write_debug_zip

    def _clip(path, members):
        real_write(path, [(name, payload[:CHAT_PASTE_CEILING]) for name, payload in members])

    monkeypatch.setattr(debug_log, "_write_debug_zip", _clip)
    refused = essay_debug_export()
    assert refused["ok"] is False
    assert refused["refused"] == "debug-export"
    assert refused["reason"] == INCOMPLETE_EXPORT_REASON
    assert not archive_path.exists()
    assert debug_log_path().read_bytes() == blob
    assert ml_events_path().read_bytes() == blob


def test_ac3_default_debug_stays_off_unless_setup_or_env(workspace, monkeypatch):
    """AC3. Cloud where stays off. ESSAY_WRITER_DEBUG or setup debug turns logs on. Explicit off wins."""
    _cloud_setup(workspace, monkeypatch)
    assert operator_debug_default() is False
    assert debug_enabled() is False
    report = front_office_call("essay.health", {})
    assert report["alive"] is True
    assert report["ferry_tip"] == FERRY_ZIP_TIP
    assert not debug_log_path().exists()
    assert not ml_events_path().exists()
    monkeypatch.setattr("essay_writer.debug_log.land_sha", lambda: "unknown")
    refused = essay_debug_export()
    assert refused["ok"] is False
    assert refused["refused"] == "debug-export"
    assert not (workspace / EXPORT_FILENAME).exists()

    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    assert debug_enabled() is True
    front_office_call("essay.health", {})
    assert "essay.health" in debug_log_path().read_text(encoding="utf-8")
    assert "essay.health" in ml_events_path().read_text(encoding="utf-8")

    debug_log_path().unlink()
    ml_events_path().unlink()
    monkeypatch.delenv("ESSAY_WRITER_DEBUG", raising=False)
    _cloud_setup(workspace, monkeypatch, debug=True)
    assert operator_debug_default() is False
    assert debug_enabled() is True
    front_office_call("essay.health", {})
    assert debug_log_path().is_file()
    assert ml_events_path().is_file()

    debug_log_path().unlink()
    ml_events_path().unlink()
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "0")
    assert debug_enabled() is False
    front_office_call("essay.health", {})
    note_call("essay.health", {}, result={"ok": True, "alive": True, "wrote": False})
    assert not debug_log_path().exists()
    assert not ml_events_path().exists()

    monkeypatch.delenv("ESSAY_WRITER_DEBUG", raising=False)
    _cloud_setup(workspace, monkeypatch, operator_e2e=True)
    assert operator_debug_default() is True
    assert debug_enabled() is True
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "0")
    assert debug_enabled() is False
    front_office_call("essay.health", {})
    assert not debug_log_path().exists()
    assert not ml_events_path().exists()


def test_ac4_fo_docs_health_tip_names_zip_for_ferry(workspace, monkeypatch):
    sha = ferry_tip_sha()
    assert sha == hashlib.sha256(FERRY_ZIP_TIP.encode("utf-8")).hexdigest()[:12]
    assert "zip-for-ferry" in FERRY_ZIP_TIP
    assert "Do not paste a truncated run log into chat." in FERRY_ZIP_TIP
    assert "essay.debug.export" in FERRY_ZIP_TIP
    assert "debug.log" not in FERRY_ZIP_TIP
    assert "Avery" not in FERRY_ZIP_TIP
    assert FERRY_ZIP_TIP in INSTRUCTIONS
    assert "debug.log" not in INSTRUCTIONS
    assert "ferry_tip on essay.health is operator-only" in INSTRUCTIONS
    assert "Do not say it in student chat." in INSTRUCTIONS
    bot = (REPO / "docs" / "templates" / "bot.md").read_text(encoding="utf-8")
    assert FERRY_ZIP_TIP in bot
    assert "ml-events.jsonl" not in bot
    door = next(item for item in DOORS if item["tool"] == "essay.debug.export")
    assert "zip-for-ferry" in door["description"]
    assert "Do not paste a truncated run log into chat." in door["description"]
    assert "Cursor" not in door["description"]
    assert "debug.log" not in door["description"]
    monkeypatch.delenv("ESSAY_WRITER_DEBUG", raising=False)
    report = essay_health()
    assert report["ferry_tip"] == FERRY_ZIP_TIP
    assert report["ferry_tip_sha"] == sha
    assert "debug.log" not in json.dumps(report)
    assert debug_enabled() is False
    assert not debug_log_path().exists()
    assert not ml_events_path().exists()


def test_ac5_mid_office_export_zip_opens_both_logs(workspace, monkeypatch):
    """AC5. Mid-office with debug on exports a zip. Cursor opens both logs. No paste."""
    from essay_writer.build_status import finish_mid_process, reset_status

    reset_status()
    try:
        _cloud_setup(workspace, monkeypatch)
        monkeypatch.setattr("essay_writer.cursor_office.spawn_agent", _started)
        monkeypatch.setattr("essay_writer.build_office.spawn_grok", _started)
        sequence = open_sequence()
        assert debug_enabled() is False
        cursor_off = start_stage_mid(sequence, "4b", launch=CURSOR_LAUNCH)
        finish_mid_process(sequence)
        build_off = start_stage_mid(sequence, "6", launch=GROK_LAUNCH)
        finish_mid_process(sequence)
        assert cursor_off["started"] is True and cursor_off["shell"] == "cursor"
        assert build_off["started"] is True and build_off["shell"] == "grok"
        assert not debug_log_path(sequence).exists()
        assert not ml_events_path(sequence).exists()

        monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
        assert debug_enabled() is True
        cursor_on = start_stage_mid(sequence, "4b", launch=CURSOR_LAUNCH)
        finish_mid_process(sequence)
        build_on = start_stage_mid(sequence, "6", launch=GROK_LAUNCH)
        finish_mid_process(sequence)
        assert cursor_on["started"] is True and cursor_on["shell"] == "cursor"
        assert build_on["started"] is True and build_on["shell"] == "grok"
        log_word_step("render", sequence, pack_path=PACK, stage="4b")
        pack = workspace / PACK
        pack.parent.mkdir(parents=True, exist_ok=True)
        pack.write_text("{}\n", encoding="utf-8")
        for path in (debug_log_path(sequence), ml_events_path(sequence)):
            original = path.read_bytes()
            blob = original + (b"ferry-pad\n" * 5000) + TAIL
            assert len(blob) > CHAT_PASTE_CEILING
            path.write_bytes(blob)

        exported = front_office_call("essay.debug.export", {})
        assert exported["ok"] is True
        assert exported["complete"] is True
        assert exported["ferry"] == "zip"
        assert exported["paste"] is False
        assert sequence in exported["essay_ids"]
        assert PACK in exported["pack_paths"]
        reply = json.dumps(exported).encode()
        assert TAIL not in reply
        assert b"ferry-pad" not in reply

        archive_path = workspace / EXPORT_FILENAME
        sequence_debug = f"Essay-writer/MOD1004AA/sequences/1/{LOG_FILENAME}"
        sequence_events = f"Essay-writer/MOD1004AA/sequences/1/{ML_EVENTS_FILENAME}"
        with zipfile.ZipFile(archive_path) as archive:
            _assert_log_members_match_disk(archive, workspace)
            debug_bytes = archive.read(sequence_debug)
            event_bytes = archive.read(sequence_events)
            assert archive.getinfo(sequence_debug).file_size > CHAT_PASTE_CEILING
            assert archive.getinfo(sequence_events).file_size > CHAT_PASTE_CEILING
            manifest = json.loads(archive.read(FERRY_FILENAME))
        assert b"Mid-office start Cursor." in debug_bytes
        assert b"Mid-office start Build." in debug_bytes
        assert PACK.encode() in debug_bytes
        assert debug_bytes.endswith(TAIL)
        assert event_bytes.endswith(TAIL)
        assert sequence.encode() in event_bytes
        assert manifest["paste"] is False
        assert manifest["sliced"] is False
        assert sequence in manifest["essay_ids"]
        assert PACK in manifest["pack_paths"]
        logged = {item["name"]: item["bytes"] for item in manifest["members"]}
        assert logged[sequence_debug] == len(debug_bytes)
        assert logged[sequence_events] == len(event_bytes)

        assert HANDLERS["essay.debug.export"] is essay_debug_export
        assert cursor_shell()["handlers"]["essay.debug.export"] is essay_debug_export
        assert front_office()["handlers"]["essay.debug.export"] is essay_debug_export
        build_src = (REPO / "src" / "essay_writer" / "build_office.py").read_text(encoding="utf-8")
        cursor_src = (REPO / "src" / "essay_writer" / "cursor_office.py").read_text(encoding="utf-8")
        assert "def essay_debug_export" not in build_src
        assert "def essay_debug_export" not in cursor_src
    finally:
        reset_status()
