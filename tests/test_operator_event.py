from __future__ import annotations

import json
import zipfile

import pytest
from conversations.shell import FakeShell
from helpers import ESSAY, open_sequence

from essay_writer.confirm import refuse
from essay_writer.debug_log import (
    debug_enabled,
    debug_log_path,
    essay_debug_export,
    ml_events_path,
    note_call,
    support_bundle,
)
from essay_writer.incident import incident_path, note, rotated_path
from essay_writer.operator_event import MAX_BYTES, MAX_LINES, debug_tail, emit
from essay_writer.paths import essay_dir
from essay_writer.server import main
from essay_writer.specialists.grok_bot import read_basics_opening

SENTINEL = "ZEBRASENTINEL"
SECRET = "github_pat_" + ("a" * 22)
HOME = "/Users/student/Documents/essay"
SEQUENCE = "MOD1004AA-1"


def _lines(path) -> list[str]:
    if not path.is_file():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _rows(path) -> list[dict]:
    return [json.loads(line) for line in _lines(path)]


def test_debug_on_writes_one_row_and_one_line(workspace, monkeypatch) -> None:
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    note_call(
        "essay.dig",
        {"confirmPhase": "read", "query": "chokepoints " + ("Q" * 100)},
        result={
            "ok": False,
            "wrote": False,
            "title": "T" * 200,
            "reason": "R" * 200,
            "refused": "setup",
            "mid_office": "exit",
            "mid_shell": "Cursor",
            "mid_stderr": "E" * 200,
        },
    )
    rows = _rows(ml_events_path())
    assert len(rows) == 1
    row = rows[0]
    assert row["tool"] == "essay.dig"
    assert row["query"] == ("chokepoints " + ("Q" * 100))[:80]
    assert row["title"] == "T" * 120
    assert row["reason"] == "R" * 160
    assert row["stderr"] == "E" * 160
    assert len(_lines(debug_log_path())) == 1
    line = _lines(debug_log_path())[0]
    assert "essay.dig" in line
    assert f"query={row['query']}" in line
    assert f"title={row['title']}" in line
    assert f"reason={row['reason']}" in line
    assert f"stderr={row['stderr']}" in line
    assert _rows(ml_events_path()).count(row) == 1


def test_debug_off_creates_neither_file(workspace, monkeypatch) -> None:
    monkeypatch.delenv("ESSAY_WRITER_DEBUG", raising=False)
    assert debug_enabled() is False
    emit({"t": "", "tool": "essay.health", "phase": "read", "query": SENTINEL})
    note_call("essay.dig", {"query": SENTINEL}, result={"ok": True, "title": SENTINEL})
    assert debug_enabled() is False
    assert not debug_log_path().exists()
    assert not ml_events_path().exists()
    assert not debug_log_path().with_name("debug.log.1").exists()
    assert not ml_events_path().with_name("ml-events.jsonl.1").exists()


def test_debug_tail_prints_views_without_enabling_debug(workspace, monkeypatch, capsys) -> None:
    monkeypatch.delenv("ESSAY_WRITER_DEBUG", raising=False)
    main(["--debug-tail"])
    assert capsys.readouterr().out == ""
    assert debug_enabled() is False
    assert not ml_events_path().exists()
    assert not debug_log_path().exists()
    assert not incident_path().exists()

    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    emit(
        {
            "t": "",
            "tool": "essay.health",
            "phase": "read",
            "query": HOME,
            "reason": SECRET,
        }
    )
    emit(
        {
            "t": "",
            "tool": "essay.dig",
            "phase": "read",
            "essay_id": SEQUENCE,
            "query": "sequence-mark",
        }
    )
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "0")
    assert debug_enabled() is False
    main(["--debug-tail"])
    printed = capsys.readouterr().out
    assert "essay.health" in printed
    assert "<home>" in printed
    assert "/Users/student" not in printed
    assert SECRET not in printed
    assert "[redacted]" in printed
    assert "sequence-mark" not in printed
    assert debug_enabled() is False
    assert not incident_path().exists()

    main(["--debug-tail", SEQUENCE])
    sequenced = capsys.readouterr().out
    assert "sequence-mark" in sequenced
    assert "essay-writer.land" in sequenced
    assert "essay.health" not in sequenced
    assert debug_enabled() is False

    main(["--debug-tail", "not a sequence"])
    assert "essay.health" in capsys.readouterr().out


def test_debug_tail_missing_is_quiet_and_unreadable_exits(workspace, monkeypatch) -> None:
    monkeypatch.delenv("ESSAY_WRITER_DEBUG", raising=False)
    assert debug_tail(None) == 0
    assert not ml_events_path().exists()
    live = ml_events_path()
    live.parent.mkdir(parents=True, exist_ok=True)
    live.mkdir()
    with pytest.raises(SystemExit) as caught:
        main(["--debug-tail"])
    assert caught.value.code == 1
    assert debug_enabled() is False
    assert not incident_path().exists()


def test_tail_reads_rotated_then_live(workspace, monkeypatch, capsys) -> None:
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    folder = debug_log_path().parent
    folder.mkdir(parents=True, exist_ok=True)
    older = [
        {"t": "2026-01-01T00:00:00+00:00", "tool": "essay.health", "query": "older-a"},
        {"t": "2026-01-01T00:00:01+00:00", "tool": "essay.health", "query": "older-b"},
    ]
    live = {"t": "2026-01-01T00:00:02+00:00", "tool": "essay.dig", "query": "live-c"}
    (folder / "ml-events.jsonl.1").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in older),
        encoding="utf-8",
    )
    (folder / "ml-events.jsonl").write_text(json.dumps(live, sort_keys=True) + "\n", encoding="utf-8")
    assert debug_tail(None, limit=2) == 0
    printed = capsys.readouterr().out.splitlines()
    assert len(printed) == 2
    assert "query=older-b" in printed[0]
    assert "query=live-c" in printed[1]
    assert "query=older-a" not in "\n".join(printed)


def test_rotation_renames_both_files_at_the_line_cap(workspace, monkeypatch) -> None:
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    for index in range(MAX_LINES):
        emit({"t": "", "tool": "essay.health", "phase": "read", "ok": True, "query": f"row-{index}"})
    assert len(_lines(ml_events_path())) == MAX_LINES
    assert not ml_events_path().with_name("ml-events.jsonl.1").exists()
    emit({"t": "", "tool": "essay.dig", "phase": "read", "query": "after-cap"})
    assert len(_lines(ml_events_path().with_name("ml-events.jsonl.1"))) == MAX_LINES
    assert len(_lines(debug_log_path().with_name("debug.log.1"))) == MAX_LINES
    live = _rows(ml_events_path())
    assert len(live) == 1
    assert live[0]["query"] == "after-cap"
    assert len(_lines(debug_log_path())) == 1
    assert "after-cap" in _lines(debug_log_path())[0]
    assert "row-0" in _lines(debug_log_path().with_name("debug.log.1"))[0]


def test_rotation_renames_both_files_at_the_byte_cap(workspace, monkeypatch) -> None:
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    debug_log_path().parent.mkdir(parents=True, exist_ok=True)
    debug_log_path().write_bytes(b"x" * MAX_BYTES)
    ml_events_path().write_text(
        '{"t":"2026-01-01T00:00:00+00:00","tool":"essay.health"}\n',
        encoding="utf-8",
    )
    emit({"t": "", "tool": "essay.dig", "phase": "read", "query": "byte-cap"})
    assert debug_log_path().with_name("debug.log.1").read_bytes() == b"x" * MAX_BYTES
    rotated = ml_events_path().with_name("ml-events.jsonl.1").read_text(encoding="utf-8")
    assert "essay.health" in rotated
    assert "byte-cap" not in rotated
    assert _rows(ml_events_path())[0]["query"] == "byte-cap"
    assert "byte-cap" in debug_log_path().read_text(encoding="utf-8")


def test_a_failed_rename_skips_the_append(workspace, monkeypatch) -> None:
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    debug_log_path().parent.mkdir(parents=True, exist_ok=True)
    debug_log_path().write_bytes(b"x" * MAX_BYTES)
    ml_events_path().write_text('{"tool":"essay.health"}\n', encoding="utf-8")

    def _fail(*_args: object, **_kwargs: object) -> None:
        raise OSError("rename failed")

    monkeypatch.setattr("essay_writer.operator_event.os.replace", _fail)
    emit({"t": "", "tool": "essay.dig", "phase": "read", "query": "skipped"})
    assert debug_log_path().read_bytes() == b"x" * MAX_BYTES
    assert ml_events_path().read_text(encoding="utf-8") == '{"tool":"essay.health"}\n'
    assert not debug_log_path().with_name("debug.log.1").exists()


def test_one_emit_does_not_write_a_second_row(workspace, monkeypatch) -> None:
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    emit({"t": "", "tool": "essay.health", "phase": "read", "query": "once"})
    assert len(_rows(ml_events_path())) == 1
    assert len(_lines(debug_log_path())) == 1
    emit(
        {
            "t": "",
            "tool": "essay.dig",
            "phase": "draft",
            "essay_id": SEQUENCE,
            "query": "door-once",
        }
    )
    tools = [row["tool"] for row in _rows(ml_events_path(SEQUENCE))]
    assert tools == ["essay-writer.land", "essay.dig"]
    assert tools.count("essay.dig") == 1
    assert len(_lines(debug_log_path(SEQUENCE))) == 2


def test_export_redacts_a_home_path_and_a_secret(workspace, monkeypatch) -> None:
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    debug_log_path().parent.mkdir(parents=True, exist_ok=True)
    debug_log_path().write_text(f"query={HOME} reason={SECRET}\n", encoding="utf-8")
    debug_log_path().with_name("debug.log.1").write_text(f"title={HOME}\n", encoding="utf-8")
    ml_events_path().write_text('{"tool":"essay.health"}\n', encoding="utf-8")
    exported = essay_debug_export()
    assert exported["ok"] is True
    archive = workspace / "debug.zip"
    with zipfile.ZipFile(archive) as zipped:
        names = zipped.namelist()
        assert "debug.log" in names
        assert "debug.log.1" in names
        assert "ml-events.jsonl" in names
        blob = b"\n".join(zipped.read(name) for name in names).decode("utf-8")
    assert "/Users/student" not in blob
    assert "<home>" in blob
    assert SECRET not in blob
    assert "[redacted]" in blob


def test_sentinel_stays_on_the_opt_in_record(workspace, monkeypatch) -> None:
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    note_call(
        "essay.dig",
        {"confirmPhase": "read", "query": SENTINEL},
        result={
            "ok": False,
            "wrote": False,
            "title": SENTINEL,
            "reason": SENTINEL,
            "refused": "setup",
            "mid_office": "done",
            "mid_shell": "Build",
            "mid_stderr": SENTINEL,
        },
    )
    refuse("sentinel-check", SENTINEL)
    for index in range(MAX_LINES):
        note(f"n-{index}", severity="info", disposition="fallback")
    assert incident_path().is_file()
    assert rotated_path().is_file()
    bundled = support_bundle()
    assert bundled["ok"] is True
    opt_in = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (debug_log_path(), ml_events_path())
        if path.is_file()
    )
    assert opt_in.count(SENTINEL) >= 4
    row = _rows(ml_events_path())[0]
    for key in ("query", "title", "reason", "stderr"):
        assert row[key] == SENTINEL
    incident_text = incident_path().read_text(encoding="utf-8")
    rotated_text = rotated_path().read_text(encoding="utf-8")
    assert SENTINEL not in incident_text
    assert SENTINEL not in rotated_text
    with zipfile.ZipFile(workspace / "support.zip") as zipped:
        names = zipped.namelist()
        assert "debug.log" not in names
        assert "debug.log.1" not in names
        assert "ml-events.jsonl" not in names
        assert "ml-events.jsonl.1" not in names
        blob = b"\n".join(zipped.read(name) for name in names)
    assert SENTINEL.encode() not in blob


def test_guidance_only_door_fills_tool_and_stage(workspace) -> None:
    folder = essay_dir(ESSAY)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(
        "Genre: report\nQuestion: How should the firm manage the corridor?\n",
        encoding="utf-8",
    )
    seq = open_sequence()
    before = [
        row for row in _rows(incident_path()) if row.get("code") == "guidance-only"
    ]
    look = "\n".join(read_basics_opening(seq).lines)
    reply = FakeShell().call(
        "essay.stage",
        essay_id=seq,
        stage="1",
        confirmPhase="draft",
        look=look,
    )
    assert reply["refused"] == "guidance-only"
    matched = [
        row for row in _rows(incident_path()) if row.get("code") == "guidance-only"
    ]
    assert len(matched) == len(before) + 1
    fresh = matched[-1]
    assert fresh["tool"] == "essay.stage"
    assert fresh["stage"] == "1"
    assert fresh["sequence"] == seq
    assert fresh["severity"] == "error"
    assert fresh["disposition"] == "refuse"

    bare = refuse("bare-frame", "Ask again.")
    assert bare["refused"] == "bare-frame"
    framed = [row for row in _rows(incident_path()) if row.get("code") == "bare-frame"]
    assert len(framed) == 1
    assert framed[0]["tool"] == ""
    assert framed[0]["stage"] == ""
