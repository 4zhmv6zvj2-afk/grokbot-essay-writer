"""Easy Cursor CLI FO status tips and early exit. Stable ids: AC1–AC5."""

from __future__ import annotations

import inspect
import io
from pathlib import Path

import pytest
from helpers import ESSAY, open_sequence, plant_gathered_source, write_upload

from essay_writer.build_office import report_phase as build_report_phase
from essay_writer.build_office import spawn_grok
from essay_writer.build_status import (
    HEARTBEAT_SECONDS,
    MID_BUILD_STATUS_ID,
    begin_mid_build,
    due_lines,
    exit_reason_sentence,
    finish_mid_process,
    join_mid_readers,
    reply_status,
    reset_status,
    spawn_exit_status,
    start_sentence,
    student_inbox,
)
from essay_writer.cursor_office import report_phase, spawn_agent, start_stage_mid
from essay_writer.debug_log import debug_log_path, note_mid_office
from essay_writer.setup import SHELL_GROK_BUILD
from essay_writer.shells import front_office_call

REPO = Path(__file__).resolve().parents[1]
QUESTION = "How should Inditex manage its supply chain?"
LOOK = (
    "No mark scheme is on this module.\n"
    f"Format: report.\nQuestion: {QUESTION}\n"
    "This report asks how Inditex should manage its supply chain."
)


@pytest.fixture(autouse=True)
def _clear_status():
    reset_status()
    yield
    reset_status()


def _plain(line: str) -> None:
    folded = line.casefold()
    for banned in ("cli", "cursor", "grok", "agent", "heartbeat", "milestone"):
        assert banned not in folded


def test_ac1_start_tip_on_cursor_cli_kickoff(workspace, monkeypatch):
    """AC1. Start tip fires when Cursor CLI mid-office kicks off."""
    monkeypatch.setattr(
        "essay_writer.cursor_office.spawn_agent",
        lambda command: {"started": True, "reason": "", "pid": 12, "command": list(command), "stdout": None},
    )
    seq = open_sequence()
    run = start_stage_mid(seq, "4a")
    assert run["started"] is True
    assert run["status"] == [start_sentence("gathering", seq)]
    assert QUESTION.casefold() in run["status"][0].casefold() or seq in run["status"][0]
    for line in run["status"]:
        _plain(line)


def test_ac2_mid_tips_only_when_mid_path_signals(workspace):
    """AC2. Mid tips only when mid path signals; FO never invents phases."""
    seq = open_sequence()
    tipped = reply_status(
        "essay.stage",
        {"essay_id": seq, "stage": "4b", "confirmPhase": "draft", "look": LOOK},
        {"ok": True, "essay_id": seq, "mid_phases": ["open_full"]},
    )
    assert any("opens in full" in line for line in tipped)
    invented = reply_status(
        "essay.stage",
        {"essay_id": seq, "stage": "4a", "confirmPhase": "draft", "look": LOOK},
        {"ok": True, "essay_id": seq},
    )
    assert invented == []
    reset_status()
    quiet = reply_status(
        "essay.stage",
        {"essay_id": seq, "stage": "4b", "confirmPhase": "confirm", "look": LOOK},
        {"ok": True, "stored": True, "essay_id": seq},
    )
    assert not any("written a note" in line for line in quiet)


def test_ac3_stale_only_on_long_silent_jobs_no_fixed_heartbeat_on_short(workspace, monkeypatch):
    """AC3. Stale-only ~5 min when silent on long jobs; no fixed heartbeat on short jobs."""
    clock = {"t": 0.0}
    monkeypatch.setattr("essay_writer.build_status._now", lambda: clock["t"])
    seq = open_sequence()
    assert due_lines(seq) == []
    begin_mid_build(seq, "gathering", subject=QUESTION)
    clock["t"] = HEARTBEAT_SECONDS - 1
    assert due_lines(seq) == []
    clock["t"] = HEARTBEAT_SECONDS
    stale = due_lines(seq)
    assert stale and "still working" in stale[0].casefold() and "Inditex" in stale[0]
    clock["t"] = HEARTBEAT_SECONDS * 2
    assert due_lines(seq) == []
    reset_status()
    assert due_lines(seq) == []


def test_ac4_early_exit_surfaces_exit_reason_to_fo_and_logs(workspace, monkeypatch):
    """AC4. Early exit (incl. 4a/4b) surfaces exit reason to FO/logs."""
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    seq = open_sequence()
    monkeypatch.setattr(
        "essay_writer.cursor_office.spawn_agent",
        lambda command: {"started": False, "reason": "agent-cli-missing", "command": list(command)},
    )
    missed = start_stage_mid(seq, "4a")
    assert missed["started"] is False
    assert missed["status"]
    assert "writing tool" in missed["status"][0].casefold()
    _plain(missed["status"][0])

    log_path = debug_log_path(seq)
    assert not log_path.exists()

    write_upload(workspace)
    brief = workspace / "Essay-writer" / ESSAY / "brief.md"
    brief.write_text(f"Format: report\nQuestion: {QUESTION}\n", encoding="utf-8")
    for stage in ("1", "2", "3"):
        draft = front_office_call(
            "essay.stage",
            {"essay_id": seq, "stage": stage, "confirmPhase": "draft", "look": LOOK},
        )
        front_office_call(
            "essay.stage",
            {
                "essay_id": seq,
                "stage": stage,
                "confirmPhase": "confirm",
                "look": LOOK,
                **{k: draft[k] for k in ("cardAction", "cardDigest") if k in draft},
            },
        )
    plant_gathered_source(seq)
    door = front_office_call(
        "essay.stage",
        {"essay_id": seq, "stage": "4a", "confirmPhase": "draft", "look": LOOK},
    )
    assert door["ok"] is True
    assert door.get("status")
    assert "writing tool" in " ".join(door["status"]).casefold()

    reset_status()
    monkeypatch.setattr(
        "essay_writer.cursor_office.spawn_agent",
        lambda command: {
            "started": True,
            "reason": "",
            "pid": 0,
            "command": list(command),
            "stdout": io.BytesIO(b""),
            "proc": type("P", (), {"wait": lambda self: 2})(),
        },
    )
    failed = start_stage_mid(seq, "4b")
    assert failed["started"] is True
    join_mid_readers()
    inbox = student_inbox(seq)
    assert any("stopped before it finished" in line.casefold() for line in inbox)

    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_GROK_BUILD)
    reset_status()
    monkeypatch.setattr(
        "essay_writer.build_office.spawn_grok",
        lambda command: {
            "started": True,
            "reason": "",
            "pid": 0,
            "command": list(command),
            "stdout": io.BytesIO(b""),
            "proc": type("P", (), {"wait": lambda self: 1})(),
        },
    )
    grok_run = start_stage_mid(seq, "4b")
    assert grok_run["shell"] == "grok"
    join_mid_readers()
    assert any("stopped before it finished" in line.casefold() for line in student_inbox(seq))

    reset_status()
    begin_mid_build(seq, "notes", subject=QUESTION)
    finish_mid_process(seq, exit_code=3)
    assert exit_reason_sentence(QUESTION, exit_code=3).casefold() in " ".join(student_inbox(seq)).casefold()

    note_mid_office("exit", seq, "Cursor", reason="File work stopped.", exit_code=2)
    text = log_path.read_text(encoding="utf-8")
    assert "Mid-office exit Cursor." in text
    assert "Code 2." in text


def test_ac5_build_covered_cursor_and_grok_share_rules():
    """AC5. Build covered — PR body opens with Build covered; repo-test asserts."""
    assert MID_BUILD_STATUS_ID == "mid-build-status"
    cursor = inspect.getsource(start_stage_mid)
    assert "follow_mid_process" in cursor
    assert "spawn_exit_status" in cursor
    assert inspect.getsource(spawn_agent).count("proc") >= 1
    assert inspect.getsource(spawn_grok).count("proc") >= 1
    assert report_phase.__module__ != build_report_phase.__module__
    assert spawn_exit_status("MOD1004AA-2", "agent-cli-missing") == spawn_exit_status(
        "MOD1004AA-2", "grok-cli-missing"
    )
