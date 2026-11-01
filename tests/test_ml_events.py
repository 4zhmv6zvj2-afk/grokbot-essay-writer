"""Structured ML event stream. Off for students. On when debug is asked.

The lines are JSONL events, not a chat transcript. essay.debug.wipe clears
this file and debug.log together. There is no second wipe door.
"""

import hashlib
import inspect
import json
import os
from pathlib import Path

from helpers import open_sequence

from essay_writer.debug_log import (
    LOG_FILENAME,
    debug_enabled,
    debug_log_wipe_speech,
    essay_debug_wipe,
)
from essay_writer.debug_log import (
    ml_events_path as wipe_ml_events_path,
)
from essay_writer.doors import DOORS
from essay_writer.ml_events import (
    FILENAME,
    KINDS,
    events_enabled,
    ml_events_path,
    note_events,
)
from essay_writer.server import HANDLERS, INSTRUCTIONS
from essay_writer.setup import essay_setup
from essay_writer.shells import cursor_shell, front_office, front_office_call
from essay_writer.word import essay_pack_render_word

REPO = Path(__file__).resolve().parents[1]

CHAT = "Harbour chat transcript zebra quilt 8841. The student said the whole draft aloud."
PHRASES = (
    "delete the logs",
    "clear debug log",
    "Clear the debug log.",
    "wipe the run log",
    "please delete debug log",
)
_ALLOWED = {
    "outcome": {
        "kind",
        "t",
        "tool",
        "phase",
        "essay_id",
        "module",
        "ok",
        "wrote",
        "stored",
        "advanced",
        "refused",
        "error",
        "gate",
        "land",
        "flag",
        "outcome",
    },
    "stage": {
        "kind",
        "t",
        "tool",
        "phase",
        "essay_id",
        "stage",
        "stored",
        "advanced",
        "current",
        "next_stage",
    },
    "confirm": {
        "kind",
        "t",
        "tool",
        "phase",
        "essay_id",
        "stage",
        "card_action",
        "card_present",
        "stored",
        "advanced",
        "wrote",
    },
    "digest": {"kind", "t", "tool", "essay_id", "card_digest", "posted", "payload", "omitted", "chars"},
    "paths": {"kind", "t", "tool", "essay_id", "files", "local_count", "local_suffixes"},
    "shell": {
        "kind",
        "t",
        "tool",
        "essay_id",
        "shell",
        "event",
        "stage",
        "model",
        "reasoning",
        "fast",
        "context_window",
        "exit_code",
        "stderr",
    },
}
_FILE_KEYS = {"display", "exists", "mtime_ns", "sha256", "mounted"}


def _stream(workspace, essay_id=None):
    if essay_id:
        from essay_writer.paths import work_dir

        return work_dir(essay_id) / FILENAME
    return workspace / FILENAME


def _events(workspace, essay_id=None):
    path = _stream(workspace, essay_id)
    assert path.is_file()
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        assert line.startswith("{") and line.endswith("}")
        row = json.loads(line)
        assert row["kind"] in KINDS
        assert set(row) <= _ALLOWED[row["kind"]]
        if row["kind"] == "paths":
            for item in row["files"]:
                assert set(item) <= _FILE_KEYS
        rows.append(row)
    return rows


def test_wipe_speech_matches_one_phrase():
    for phrase in PHRASES:
        assert debug_log_wipe_speech(phrase) is True
    assert debug_log_wipe_speech("delete this module") is False
    assert debug_log_wipe_speech("") is False


def test_student_default_is_off(workspace, monkeypatch):
    monkeypatch.delenv("ESSAY_WRITER_DEBUG", raising=False)
    monkeypatch.delenv("ESSAY_WRITER_OPERATOR_E2E", raising=False)
    monkeypatch.setattr("essay_writer.paths.load_saved_setup", lambda: {"where": "user-local"})
    assert events_enabled() is False
    assert debug_enabled() is False
    front_office_call("essay.health", {})
    assert not _stream(workspace).exists()
    assert not (workspace / LOG_FILENAME).exists()
    assert ml_events_path is wipe_ml_events_path
    assert ml_events_path() == workspace / FILENAME


def test_cloud_where_stays_off_and_debug_or_e2e_turns_the_stream_on(workspace, monkeypatch):
    monkeypatch.delenv("ESSAY_WRITER_DEBUG", raising=False)
    monkeypatch.delenv("ESSAY_WRITER_OPERATOR_E2E", raising=False)
    monkeypatch.setattr(
        "essay_writer.paths.load_saved_setup",
        lambda: {"where": "grokbot-cloud-computer"},
    )
    assert events_enabled() is False
    assert events_enabled() is debug_enabled()
    front_office_call("essay.health", {})
    assert not _stream(workspace).exists()
    assert not (workspace / LOG_FILENAME).exists()

    monkeypatch.setattr("essay_writer.paths.load_saved_setup", lambda: {"debug": True})
    assert events_enabled() is True
    front_office_call("essay.health", {})
    rows = _events(workspace)
    assert any(row["kind"] == "outcome" and row["tool"] == "essay.health" for row in rows)
    assert CHAT not in _stream(workspace).read_text(encoding="utf-8")

    monkeypatch.setattr("essay_writer.paths.load_saved_setup", lambda: {"operator_e2e": True})
    assert events_enabled() is True
    monkeypatch.setattr("essay_writer.paths.load_saved_setup", lambda: None)
    monkeypatch.setenv("ESSAY_WRITER_OPERATOR_E2E", "1")
    assert events_enabled() is True
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "0")
    assert events_enabled() is False
    assert debug_enabled() is False


def test_explicit_off_writes_neither_file(workspace, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "0")
    monkeypatch.setattr(
        "essay_writer.paths.load_saved_setup",
        lambda: {"where": "grokbot-cloud-computer", "debug": True, "operator_e2e": True},
    )
    front_office_call("essay.health", {})
    assert not _stream(workspace).exists()
    assert not (workspace / LOG_FILENAME).exists()


def test_stage_confirm_digest_are_structured_and_leave_out_chat(workspace, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    sequence = open_sequence()
    draft = front_office_call(
        "essay.stage",
        {
            "essay_id": sequence,
            "stage": "1",
            "confirmPhase": "draft",
            "look": CHAT,
        },
    )
    assert draft["ok"] is True, draft
    saved = front_office_call(
        "essay.stage",
        {
            "essay_id": sequence,
            "stage": "1",
            "confirmPhase": "confirm",
            "cardAction": "confirm",
            "cardDigest": draft["cardDigest"],
            "look": CHAT,
        },
    )
    assert saved.get("stored") is True, saved
    text = _stream(workspace, sequence).read_text(encoding="utf-8")
    assert CHAT not in text
    assert "look" not in text
    rows = _events(workspace, sequence)
    kinds = {row["kind"] for row in rows}
    assert {"stage", "confirm", "digest", "outcome"} <= kinds
    confirm = [row for row in rows if row["kind"] == "confirm" and row.get("phase") == "confirm"]
    assert confirm
    assert confirm[-1]["card_action"] == "confirm"
    assert confirm[-1]["card_present"] is True
    digest = [row for row in rows if row["kind"] == "digest"]
    assert any(row.get("card_digest") == draft["cardDigest"] for row in digest)
    assert any(row.get("posted") == saved["card"]["digest"] for row in digest)
    assert all(len(row["card_digest"]) == 64 for row in digest if "card_digest" in row)
    assert "ml-events.jsonl" not in json.dumps(saved)


def test_prose_digest_and_local_paths_are_not_copied(workspace, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    prose = CHAT + " extra sentences about the tutorial."
    note_events(
        "essay.project.delete",
        {
            "confirmPhase": "confirm",
            "module": "MOD1004AA",
            "cardDigest": prose,
            "localPaths": [prose + ".docx", "/tmp/papers.zip"],
            "look": prose,
            "query": prose,
        },
        result={
            "ok": False,
            "refused": "debug-wipe",
            "reason": prose,
            "status": [prose],
            "next": prose,
            "messages": [{"role": "user", "content": prose}],
            "wrote": False,
        },
    )
    text = _stream(workspace).read_text(encoding="utf-8")
    assert prose not in text
    assert "Harbour chat transcript" not in text
    rows = _events(workspace)
    digest = next(row for row in rows if row["kind"] == "digest")
    assert digest["omitted"] is True
    assert digest["chars"] == len(prose)
    assert "card_digest" not in digest
    paths = next(row for row in rows if row["kind"] == "paths")
    assert paths["local_count"] == 2
    assert paths["local_suffixes"] == ["docx", "zip"]
    assert "files" in paths and paths["files"] == []
    outcome = next(row for row in rows if row["kind"] == "outcome")
    assert outcome["refused"] == "debug-wipe"
    assert "reason" not in outcome


def test_stage10_paths_name_the_file_not_its_bytes(workspace, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    sequence = open_sequence()
    from essay_writer.paths import work_dir

    target = work_dir(sequence) / "output" / f"{sequence}.docx"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = b"sequence-word-bytes"
    target.write_bytes(payload)
    note_events(
        "essay.stage",
        {"essay_id": sequence, "stage": "10", "confirmPhase": "confirm", "look": CHAT},
        result={"ok": True, "wrote": True, "stored": True, "advanced": False, "stage": "10"},
    )
    rows = _events(workspace, sequence)
    paths = [row for row in rows if row["kind"] == "paths"]
    assert paths
    files = paths[-1]["files"]
    sequence_file = next(item for item in files if item["display"].endswith(f"{sequence}.docx"))
    assert sequence_file["exists"] is True
    assert sequence_file["sha256"] == hashlib.sha256(payload).hexdigest()
    assert payload.decode() not in _stream(workspace, sequence).read_text(encoding="utf-8")
    documents = next(item for item in files if item["display"].startswith("Documents/"))
    assert documents["mounted"] is False
    assert documents["exists"] is False
    assert CHAT not in _stream(workspace, sequence).read_text(encoding="utf-8")


def test_cursor_and_build_share_one_stream(workspace, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    sequence = open_sequence()
    from essay_writer.cursor_office import start_stage_mid

    monkeypatch.setattr(
        "essay_writer.cursor_office.spawn_agent",
        lambda command: {"started": True, "reason": "", "pid": os.getpid(), "command": command, "stdout": None},
    )
    started = start_stage_mid(sequence, "6")
    assert started["started"] is True
    from essay_writer.stage_llm import stage_settings

    rules = stage_settings("6")["rules"]
    assert len(rules) > 80
    text = _stream(workspace, sequence).read_text(encoding="utf-8")
    assert rules[40:140] not in text
    assert CHAT not in text
    rows = _events(workspace, sequence)
    assert any(row["kind"] == "shell" and row["shell"] == "Cursor" and row["event"] == "start" for row in rows)
    assert not any(row["kind"] == "shell" and row["shell"] == "Build" for row in rows)
    from essay_writer.build_status import finish_mid_process

    finish_mid_process(sequence)

    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: "grok_build")
    monkeypatch.setattr(
        "essay_writer.build_office.spawn_grok",
        lambda command: {"started": True, "reason": "", "pid": os.getpid(), "command": command, "stdout": None},
    )
    built = start_stage_mid(sequence, "8")
    assert built["shell"] == "grok"
    rows = _events(workspace, sequence)
    assert any(row["kind"] == "shell" and row["shell"] == "Build" and row["event"] == "start" for row in rows)
    build_src = (REPO / "src" / "essay_writer" / "build_office.py").read_text(encoding="utf-8")
    cursor_src = (REPO / "src" / "essay_writer" / "cursor_office.py").read_text(encoding="utf-8")
    assert "ml-events.jsonl" not in build_src
    assert "ml-events.jsonl" not in cursor_src
    assert "ml_events" not in build_src
    assert "ml_events" not in cursor_src
    assert cursor_shell()["handlers"]["essay.debug.wipe"] is front_office()["handlers"]["essay.debug.wipe"]
    assert cursor_shell()["handlers"]["essay.debug.wipe"] is HANDLERS["essay.debug.wipe"]
    assert HANDLERS["essay.debug.wipe"] is essay_debug_wipe


def test_one_phrase_clears_debug_log_and_the_event_stream(workspace, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    front_office_call("essay.health", {})
    log_path = workspace / LOG_FILENAME
    stream = _stream(workspace)
    assert log_path.is_file() and log_path.stat().st_size > 0
    assert stream.is_file() and stream.stat().st_size > 0

    wiped = front_office_call("essay.debug.wipe", {"speech": "delete the logs"})
    assert wiped["ok"] is True
    assert wiped["cleared"] is True
    assert wiped["wrote"] is True
    assert wiped["cleared_debug"] is True
    assert wiped["cleared_ml_events"] is True
    assert not log_path.exists()
    assert not stream.exists()

    again = front_office_call("essay.debug.wipe", {"speech": "clear debug log"})
    assert again["ok"] is True
    assert again["cleared"] is False
    assert again["cleared_debug"] is False
    assert again["cleared_ml_events"] is False
    assert not log_path.exists()
    assert not stream.exists()
    reply = json.dumps(wiped) + json.dumps(again)
    assert "debug.log" not in reply
    assert "ml-events" not in reply
    assert wiped["next"] == "Cleared the run logs."

    stream.write_text('{"kind":"outcome"}\n', encoding="utf-8")
    only_stream = front_office_call("essay.debug.wipe", {"speech": "wipe the run log"})
    assert only_stream["cleared"] is True
    assert only_stream["cleared_ml_events"] is True
    assert only_stream["cleared_debug"] is False
    assert not stream.exists()
    assert not log_path.exists()


def test_refused_speech_leaves_both_files(workspace, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    front_office_call("essay.health", {})
    refused = front_office_call("essay.debug.wipe", {"speech": "archive the module"})
    assert refused["ok"] is False
    assert refused["refused"] == "debug-wipe"
    assert (workspace / LOG_FILENAME).is_file()
    assert _stream(workspace).is_file()


def test_no_second_wipe_door_or_button():
    tools = [door["tool"] for door in DOORS if "wipe" in door["tool"] or "jsonl" in door["tool"]]
    assert tools == ["essay.debug.wipe"]
    assert "essay.ml.wipe" not in HANDLERS
    setup_src = inspect.getsource(essay_setup)
    assert "wipe" not in setup_src.casefold()
    assert "essay.debug.wipe" in INSTRUCTIONS
    assert "no settings toggle" in INSTRUCTIONS.casefold()
    assert "no chat button" in INSTRUCTIONS.casefold()
    assert "ml-events.jsonl" not in INSTRUCTIONS
    door = next(item for item in DOORS if item["tool"] == "essay.debug.wipe")
    assert door["confirm"] is None
    assert "no chat card" in door["description"].casefold()
    assert "debug.log" not in door["description"]
    assert "ml-events.jsonl" not in door["description"]
    word = (REPO / "src" / "essay_writer" / "word.py").read_text(encoding="utf-8")
    assert "ml-events.jsonl" not in word
    assert "ml_events" not in word
    assert "ml-events.jsonl" not in inspect.getsource(essay_pack_render_word)
    note = (REPO / "docs" / "operator-log.md").read_text(encoding="utf-8")
    assert "ml-events.jsonl" in note
    assert FILENAME in (REPO / ".gitignore").read_text(encoding="utf-8")
    bot = (REPO / "docs" / "templates" / "bot.md").read_text(encoding="utf-8")
    assert "essay.debug.wipe" in bot
    assert "ml-events.jsonl" not in bot
