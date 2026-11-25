"""Easy Cursor CLI FO status tips and early exit. Stable ids: AC1–AC5."""

from __future__ import annotations

import inspect
import io
import os
import threading
from pathlib import Path

import pytest
from helpers import ESSAY, open_sequence, plant_gathered_source, write_upload

from essay_writer.build_office import report_phase as build_report_phase
from essay_writer.build_office import spawn_grok
from essay_writer.build_status import (
    HEARTBEAT_SECONDS,
    MID_BUILD_STATUS_ID,
    begin_mid_build,
    bind_job,
    due_lines,
    exit_reason_sentence,
    finish_mid_process,
    follow_mid_process,
    join_mid_readers,
    live_mid_job,
    reply_status,
    reset_status,
    session_open,
    spawn_exit_status,
    start_sentence,
    student_inbox,
)
from essay_writer.cursor_office import report_phase, spawn_agent, start_stage_mid
from essay_writer.debug_log import debug_log_path, note_mid_office
from essay_writer.paths import work_dir, workspace_root_lock
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
        lambda command: {
            "started": True,
            "reason": "",
            "pid": 12,
            "command": list(command),
            "stdout": None,
        },
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
    assert "Cursor" in missed["status"][0]
    assert "safe" in missed["status"][0].casefold()
    assert "writing tool" not in missed["status"][0].casefold()

    log_path = debug_log_path(seq)
    assert not log_path.exists()

    write_upload(workspace)
    brief = workspace / "Essay-writer" / ESSAY / "brief.md"
    brief.write_text(f"Format: report\nQuestion: {QUESTION}\n", encoding="utf-8")
    for stage in ("1", "2", "3"):
        draft = front_office_call(
            "essay.stage",
            {
                "essay_id": seq,
                "stage": stage,
                "confirmPhase": "draft",
                "look": f"{LOOK} This sentence belongs to stage {stage}.",
            },
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
    joined = " ".join(door["status"])
    assert "Cursor" in joined
    assert "safe" in joined.casefold()
    assert "writing tool" not in joined.casefold()

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
    assert (
        exit_reason_sentence(QUESTION, exit_code=3).casefold()
        in " ".join(student_inbox(seq)).casefold()
    )

    note_mid_office("exit", seq, "Cursor", reason="File work stopped.", exit_code=2)
    text = log_path.read_text(encoding="utf-8")
    assert "shell=Cursor" in text and "shell_event=exit" in text
    assert "exit_code=2" in text


class _Hold:
    """A child that stays open until the test releases it, then exits non-zero."""

    stderr = None

    def __init__(self, code: int = 2) -> None:
        self.code = code
        self.entered = threading.Event()
        self.go = threading.Event()

    def wait(self) -> int:
        self.entered.set()
        self.go.wait(timeout=5)
        return self.code


def _hold_reader(seq: str, shell: str, code: int = 2) -> tuple[_Hold, threading.Thread]:
    """Start a reader whose child has not exited yet."""
    hold = _Hold(code)
    thread = follow_mid_process(
        seq,
        io.BytesIO(b""),
        report=lambda *_args: [],
        proc=hold,
        shell=shell,
    )
    assert hold.entered.wait(timeout=5)
    return hold, thread


def _move_root(workspace: Path, monkeypatch) -> Path:
    """Point ESSAY_WRITER_ROOT at a second, empty run folder."""
    later = workspace / "later-run"
    (later / "uploads").mkdir(parents=True)
    (later / "Essay-writer").mkdir()
    with workspace_root_lock():
        monkeypatch.setenv("ESSAY_WRITER_ROOT", str(later))
    return later


def _finish_reader(hold: _Hold, thread: threading.Thread) -> None:
    hold.go.set()
    thread.join(timeout=5)
    assert thread.is_alive() is False


def _no_stop_line(seq: str) -> None:
    inbox = " ".join(student_inbox(seq)).casefold()
    assert "stopped before it finished" not in inbox
    assert "try this step again" not in inbox


def test_reader_log_stays_on_the_workspace_that_started_it(workspace, monkeypatch):
    """essay-midlog-a1. A Cursor reader keeps its log on the folder that started it.

    The reader finishes only after ESSAY_WRITER_ROOT points at another folder.
    Its debug log and exit line stay on the first folder. The new folder gets
    no debug log, no sequence directory, and no spoken stop line. A later
    sequence open there is not refused and does not see a log already present.
    Later work on the new folder follows the new folder.
    """
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    seq = open_sequence()
    original = debug_log_path(seq)
    assert not original.exists()

    hold, thread = _hold_reader(seq, "cursor")
    later = _move_root(workspace, monkeypatch)
    _finish_reader(hold, thread)

    assert original.is_file()
    original_text = original.read_text(encoding="utf-8")
    assert "shell=Cursor" in original_text and "shell_event=exit" in original_text
    assert "exit_code=2" in original_text
    assert not (later / "Essay-writer" / ESSAY).exists()
    assert list(later.rglob("debug.log")) == []
    assert not (later / "debug.log").exists()
    _no_stop_line(seq)

    opened = open_sequence()
    assert opened == f"{ESSAY}-1"
    assert not debug_log_path(opened).exists()

    later_log = debug_log_path(opened)
    hold, thread = _hold_reader(opened, "cursor")
    _finish_reader(hold, thread)
    assert later_log.is_file()
    later_text = later_log.read_text(encoding="utf-8")
    assert "shell=Cursor" in later_text and "shell_event=exit" in later_text
    assert original_text == original.read_text(encoding="utf-8")


def test_reader_log_stays_on_its_folder_for_build(workspace, monkeypatch):
    """essay-midlog-a2. The same hold is true for Grok Build, not only Cursor."""
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    seq = open_sequence()
    original = debug_log_path(seq)

    hold, thread = _hold_reader(seq, "grok")
    later = _move_root(workspace, monkeypatch)
    _finish_reader(hold, thread)

    assert original.is_file()
    original_text = original.read_text(encoding="utf-8")
    assert "shell=Build" in original_text and "shell_event=exit" in original_text
    assert "shell=Cursor" not in original_text
    assert "exit_code=2" in original_text
    assert not (later / "Essay-writer" / ESSAY).exists()
    assert list(later.rglob("debug.log")) == []
    _no_stop_line(seq)

    opened = open_sequence()
    assert opened == f"{ESSAY}-1"
    assert not debug_log_path(opened).exists()


def test_a_reader_does_not_close_the_session_opened_after_reset(workspace):
    """Resetting status starts a new session. The old reader must not close it."""
    del workspace
    seq = open_sequence()
    begin_mid_build(seq, "work")
    bind_job(seq, pid=os.getpid(), stage="6", shell="cursor")
    hold, thread = _hold_reader(seq, "cursor")
    reset_status()
    begin_mid_build(seq, "work")
    bind_job(seq, pid=os.getpid(), stage="7", shell="cursor")

    _finish_reader(hold, thread)

    live = live_mid_job(seq)
    assert live is not None
    assert live["stage"] == "7"


def test_a_finishing_reader_leaves_a_newer_session_open(workspace, monkeypatch):
    """A reader from the previous run must not clear the next session.

    Sequence ids start again at the same name in the next workspace. The
    reader is still bound to the folder it started in. When it exits, the
    session opened for that same id in the new run stays live. Stage 7 can
    then keep the Confirm line instead of replacing it with the wait line.
    """
    seq = open_sequence()
    begin_mid_build(seq, "work")
    bind_job(seq, pid=os.getpid(), stage="6", shell="cursor")
    hold, thread = _hold_reader(seq, "cursor")
    _move_root(workspace, monkeypatch)
    reset_status()
    begin_mid_build(seq, "work")
    bind_job(seq, pid=os.getpid(), stage="7", shell="cursor")

    _finish_reader(hold, thread)

    live = live_mid_job(seq)
    assert live is not None
    assert live["stage"] == "7"
    assert live["pid"] == os.getpid()


def test_reader_log_stays_put_when_the_folder_does_not_move(workspace, monkeypatch):
    """essay-midlog-a3. With no root change the reader still writes its exit on that folder."""
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    seq = open_sequence()
    log_path = debug_log_path(seq)

    hold, thread = _hold_reader(seq, "cursor")
    _finish_reader(hold, thread)

    assert log_path.is_file()
    text = log_path.read_text(encoding="utf-8")
    assert "shell=Cursor" in text and "shell_event=exit" in text
    assert "exit_code=2" in text
    assert student_inbox(seq)


def test_reader_that_cannot_log_still_leaves_the_new_folder_clean(workspace, monkeypatch):
    """essay-midlog-b1. A refused exit write on the start folder writes nothing on the new one."""
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    seq = open_sequence()

    blocked = debug_log_path(seq)
    blocked.mkdir(parents=True)
    assert blocked.is_dir()

    hold, thread = _hold_reader(seq, "cursor")
    later = _move_root(workspace, monkeypatch)
    _finish_reader(hold, thread)

    assert blocked.is_dir()
    assert list(blocked.iterdir()) == []
    assert not (later / "Essay-writer" / ESSAY).exists()
    assert list(later.rglob("debug.log")) == []
    assert list(later.rglob("*.tmp")) == []
    _no_stop_line(seq)

    opened = open_sequence()
    assert opened == f"{ESSAY}-1"
    assert not debug_log_path(opened).exists()


def test_bound_reader_closes_its_session_where_it_started(workspace, monkeypatch):
    """essay-midlog2-a1. A bound reader closes its open session on the folder that started it.

    This is the production setup: the launch opens a session before the reader.
    After the run folder moves and the reader finishes, that sequence has no
    open session. A new start in the new folder makes a fresh session with no
    old subject or stage. The old folder's session file is closed and the new
    folder has none. The log and folder facts still hold.
    """
    from essay_writer import build_status

    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    seq = open_sequence()
    original_log = debug_log_path(seq)
    original_session = work_dir(seq) / "mid-session.json"
    begin_mid_build(seq, "gathering", subject="The earlier subject")
    bind_job(seq, pid=os.getpid(), stage="6", shell="cursor")
    assert original_session.is_file()

    hold, thread = _hold_reader(seq, "cursor")
    later = _move_root(workspace, monkeypatch)
    _finish_reader(hold, thread)

    assert seq not in build_status._sessions
    assert session_open(seq) is False
    assert original_session.is_file() is False
    assert list(later.rglob("mid-session.json")) == []

    assert original_log.is_file()
    moved = original_log.read_text(encoding="utf-8")
    assert "shell=Cursor" in moved and "shell_event=exit" in moved
    assert not (later / "Essay-writer" / ESSAY).exists()
    assert list(later.rglob("debug.log")) == []
    _no_stop_line(seq)

    opened = open_sequence()
    assert opened == f"{ESSAY}-1"
    begin_mid_build(opened, "notes")
    fresh = build_status._sessions[opened]
    assert fresh["subject"] != "The earlier subject"
    assert "The earlier subject" not in str(fresh["subject"])
    assert fresh["stage"] == ""
    assert fresh["shell"] == ""
    assert not debug_log_path(opened).exists()


def test_bound_session_closes_with_no_move_and_unknown_shell(workspace, monkeypatch):
    """essay-midlog2-a2. The session closes when the folder stays and when the shell is unknown."""
    from essay_writer import build_status

    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    seq = open_sequence()
    session_file = work_dir(seq) / "mid-session.json"
    begin_mid_build(seq, "gathering", subject=QUESTION)
    assert session_file.is_file()

    hold, thread = _hold_reader(seq, "cursor")
    _finish_reader(hold, thread)
    assert seq not in build_status._sessions
    assert session_open(seq) is False
    assert session_file.is_file() is False
    bound = debug_log_path(seq).read_text(encoding="utf-8")
    assert "shell=Cursor" in bound and "shell_event=exit" in bound

    reset_status()
    begin_mid_build(seq, "gathering", subject=QUESTION)
    assert session_file.is_file()
    unknown_log = debug_log_path(seq)
    before = unknown_log.read_text(encoding="utf-8") if unknown_log.is_file() else ""

    hold, thread = _hold_reader(seq, "")
    later = _move_root(workspace, monkeypatch)
    _finish_reader(hold, thread)

    assert seq not in build_status._sessions
    assert session_open(seq) is False
    assert session_file.is_file() is False
    now = unknown_log.read_text(encoding="utf-8") if unknown_log.is_file() else ""
    assert now == before
    assert "shell=Build" not in now
    assert not (later / "Essay-writer" / ESSAY).exists()
    assert list(later.rglob("debug.log")) == []
    assert list(later.rglob("mid-session.json")) == []
    _no_stop_line(seq)


def test_bound_reader_closes_its_session_when_the_log_write_fails(workspace, monkeypatch):
    """essay-midlog2-b1. A refused exit write still closes the session and leaves the new folder clean."""
    from essay_writer import build_status

    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    seq = open_sequence()
    session_file = work_dir(seq) / "mid-session.json"
    begin_mid_build(seq, "gathering", subject=QUESTION)
    assert session_file.is_file()

    blocked = debug_log_path(seq)
    blocked.mkdir(parents=True)
    assert blocked.is_dir()

    hold, thread = _hold_reader(seq, "cursor")
    later = _move_root(workspace, monkeypatch)
    _finish_reader(hold, thread)

    assert seq not in build_status._sessions
    assert session_open(seq) is False
    assert session_file.is_file() is False
    assert blocked.is_dir()
    assert list(blocked.iterdir()) == []
    assert not (later / "Essay-writer" / ESSAY).exists()
    assert list(later.rglob("debug.log")) == []
    assert list(later.rglob("mid-session.json")) == []
    assert list(later.rglob("*.tmp")) == []
    _no_stop_line(seq)

    opened = open_sequence()
    assert opened == f"{ESSAY}-1"
    begin_mid_build(opened, "notes")
    assert build_status._sessions[opened]["stage"] == ""


def test_build_covered_one_bind_for_both_shells():
    """essay-midlog-c1. Build covered. Cursor and Grok Build share one bind rule.

    The pull request body says Build covered. The launch has one reader call,
    and that reader binds the run folder before it writes any exit line.
    """
    launch = inspect.getsource(start_stage_mid)
    assert launch.count("follow_mid_process(") == 1
    reader = inspect.getsource(follow_mid_process)
    assert "bind_workspace_root(home)" in reader
    assert "live_workspace_root()" in reader
    assert "if shell" not in reader


def test_ac5_build_covered_cursor_and_grok_share_rules():
    """AC5. Build covered — PR body opens with Build covered; repo-test asserts."""
    assert MID_BUILD_STATUS_ID == "mid-build-status"
    cursor = inspect.getsource(start_stage_mid)
    assert "follow_mid_process" in cursor
    assert "spawn_exit_status" in cursor
    assert inspect.getsource(spawn_agent).count("proc") >= 1
    assert inspect.getsource(spawn_grok).count("proc") >= 1
    assert report_phase.__module__ != build_report_phase.__module__
    cursor_missing = spawn_exit_status("MOD1004AA-2", "agent-cli-missing")
    grok_missing = spawn_exit_status("MOD1004AA-2", "grok-cli-missing")
    assert cursor_missing != grok_missing
    assert "Cursor" in cursor_missing[0]
    assert "Grok Build" in grok_missing[0]
