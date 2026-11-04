"""Mid-office status lines. Stable ids: AC1–AC6.

Live Cursor CLI and Grok Build can signal a phase. A five-minute silence
delivers one still-working line without another tool call. Mid-office stages
arm when the job starts. A failed start leaves no session. Stored confirm
does not ask for the Confirm card. Copy-to-mac does not invent phases.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys

import pytest
from helpers import ESSAY, open_sequence, picked, plant_gathered_source, write_upload

from essay_writer.build_office import report_phase as build_report_phase
from essay_writer.build_office import spawn_grok
from essay_writer.build_status import (
    HEARTBEAT_SECONDS,
    begin_mid_build,
    complete_job,
    due_lines,
    finish_mid_process,
    finish_step,
    flush_student_push,
    forget_process_memory,
    heartbeat_sentence,
    join_mid_readers,
    milestone_sentence,
    note_milestone,
    pump_idle,
    register_delivery,
    reply_status,
    reset_status,
    saved_pack_status,
    saved_sentence,
    session_open,
    start_sentence,
    student_inbox,
)
from essay_writer.cursor_office import report_phase, spawn_agent, start_stage_mid
from essay_writer.late_chain import STAGE6_OPEN
from essay_writer.paths import work_dir
from essay_writer.review import essay_review
from essay_writer.revise import essay_revise
from essay_writer.server import INSTRUCTIONS
from essay_writer.setup import SHELL_GROK_BUILD
from essay_writer.shells import front_office_call
from essay_writer.specialists.writer import FIRST_DRAFT_NOTE
from essay_writer.stage_track import load_pointer
from essay_writer.state import load_state, save_state

QUESTION = "How should Inditex manage its supply chain?"
LOOK = (
    "No mark scheme is on this module.\n"
    "Format: report.\n"
    f"Question: {QUESTION}\n"
    "This report asks how Inditex should manage its supply chain."
)
_PHASE_SCRIPT = (
    "import sys\n"
    "sys.stdout.write('noise\\nmid-phase: open_full\\nmid-phase: not_a_real_phase\\n')\n"
    "sys.stdout.flush()\n"
)


@pytest.fixture(autouse=True)
def _clear_status():
    reset_status()
    yield
    reset_status()


def _clock(monkeypatch, clock: dict[str, float]) -> None:
    monkeypatch.setattr("essay_writer.build_status._now", lambda: clock["t"])


def _started(command):
    return {"started": True, "reason": "", "pid": 17, "command": list(command)}


def _skipped(command):
    return {"started": False, "reason": "skipped-under-test", "command": list(command)}


def test_ac1_live_stdout_signals_a_real_phase_for_both_shells(
    requires_pty, workspace, monkeypatch
):
    """AC1: Cursor CLI and Grok Build can signal a tip-sheet phase. Absent names are not invented."""
    seq = open_sequence()
    real_popen = subprocess.Popen
    seen: list[str] = []

    def popen(argv, **kwargs):
        assert kwargs.get("shell") is False
        assert kwargs.get("stderr") is subprocess.PIPE
        assert kwargs.get("stdin") not in (None, subprocess.DEVNULL)
        assert kwargs.get("stdout") == kwargs.get("stdin")
        os.environ["PYTEST_CURRENT_TEST"] = "mid-status"
        return real_popen(
            [sys.executable, "-c", _PHASE_SCRIPT],
            stdout=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(
        "shutil.which",
        lambda name: sys.executable if name in {"agent", "grok"} else None,
    )

    def cursor_report(essay_id, kind):
        seen.append(f"cursor:{kind}")
        return report_phase(essay_id, kind)

    def grok_report(essay_id, kind):
        seen.append(f"grok:{kind}")
        return build_report_phase(essay_id, kind)

    monkeypatch.setattr("essay_writer.cursor_office.report_phase", cursor_report)
    monkeypatch.setattr("essay_writer.build_office.report_phase", grok_report)

    for shell in ("cursor", "grok"):
        reset_status()
        seen.clear()
        if shell == "grok":
            monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_GROK_BUILD)
        else:
            monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: "cursor")
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        started = start_stage_mid(seq, "4a")
        join_mid_readers(3)
        assert started["started"] is True, started
        assert started["shell"] == shell
        assert started["command"][0] == ("grok" if shell == "grok" else "agent")
        inbox = " ".join(student_inbox(seq))
        assert "opens in full" in inbox
        assert "not_a_real_phase" not in inbox
        assert any(item.endswith(":open_full") for item in seen)
        assert not any("not_a_real_phase" in item for item in seen)
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "mid-status")

    reset_status()
    absent = reply_status(
        "essay.stage",
        {"essay_id": seq, "stage": "8", "confirmPhase": "draft"},
        {"ok": True, "essay_id": seq},
    )
    assert absent == []
    assert "opens in full" not in " ".join(absent)


def test_ac2_stale_line_is_delivered_without_a_tool_poke(monkeypatch):
    """AC2: after about five minutes, the still-working line is pushed with no door call."""
    clock = {"t": 0.0}
    _clock(monkeypatch, clock)
    heard: list[tuple[str, list[str]]] = []
    remove = register_delivery(lambda essay_id, lines: heard.append((essay_id, list(lines))))
    begin_mid_build("MOD1004AA-2", "gathering", subject="the Inditex question")
    clock["t"] = HEARTBEAT_SECONDS - 1
    assert pump_idle() == []
    assert heard == []
    assert student_inbox("MOD1004AA-2") == []
    clock["t"] = HEARTBEAT_SECONDS
    line = heartbeat_sentence("gathering", "the Inditex question")
    assert pump_idle() == [line]
    assert student_inbox("MOD1004AA-2") == [line]
    assert heard == [("MOD1004AA-2", [line])]
    sent: list[list[str]] = []

    async def _send(essay_id, lines):
        del essay_id
        sent.append(list(lines))

    assert asyncio.run(flush_student_push(_send)) == [line]
    assert sent == [[line]]
    clock["t"] = HEARTBEAT_SECONDS * 2
    assert pump_idle() == []
    assert student_inbox("MOD1004AA-2") == [line]
    remove()


def test_ac3_mid_stages_arm_when_the_job_starts_and_4b_does_not_fake_it(workspace, monkeypatch):
    """AC3: stages that run mid arm for start, stale, and done. A 4b card with no process does not."""
    clock = {"t": 0.0}
    _clock(monkeypatch, clock)
    seq = open_sequence()
    monkeypatch.setattr("essay_writer.cursor_office.spawn_agent", _started)
    monkeypatch.setattr("essay_writer.build_office.spawn_grok", _started)

    for stage in ("4a", "4b", "5", "6", "7", "8", "9", "10"):
        reset_status()
        clock["t"] = 0.0
        started = start_stage_mid(seq, stage)
        assert started["started"] is True, started
        assert started["runner"] == "cursor-cli"
        assert started["status"]
        assert started["status"][0].startswith("I have started ")
        assert session_open(seq)
        clock["t"] = HEARTBEAT_SECONDS
        stale = due_lines(seq)
        assert stale == [heartbeat_sentence("", "your assignment")] or stale[0].startswith("I am still working on ")
        if stage == "5":
            done = finish_step(seq, "draft")
            assert done == [milestone_sentence("draft", done[0].split(" for ")[-1].rstrip("."))] or "ready" in done[0]
        else:
            done = complete_job(seq)
            assert done[0].endswith("is saved.")
            assert "Open the Confirm card" not in done[0]
        assert session_open(seq) is False
        clock["t"] = HEARTBEAT_SECONDS * 2
        assert due_lines(seq) == []

    reset_status()
    clock["t"] = 0.0
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_GROK_BUILD)
    grok = start_stage_mid(seq, "6")
    assert grok["started"] is True
    assert grok["runner"] == "grok-build"
    assert grok["command"][0] == "grok"
    assert grok["status"][0].startswith("I have started ")
    assert session_open(seq)
    complete_job(seq)

    monkeypatch.setattr("essay_writer.cursor_office.spawn_agent", _skipped)
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: "cursor")
    reset_status()
    clock["t"] = 0.0
    idle = start_stage_mid(seq, "4b")
    assert idle["started"] is False
    assert idle["status"] == []
    assert session_open(seq) is False
    clock["t"] = HEARTBEAT_SECONDS
    assert due_lines(seq) == []
    assert student_inbox(seq) == []

    reset_status()
    clock["t"] = 0.0
    reviewed = essay_review(seq, "6", "FAIL", "draft", seat="reviewer")
    assert reviewed["ok"] is True, reviewed
    assert any(line.startswith("I have started work on ") for line in reviewed["status"])
    assert session_open(seq)
    clock["t"] = HEARTBEAT_SECONDS
    assert due_lines(seq)
    stored = essay_review(seq, "6", "FAIL", "confirm", seat="reviewer")
    assert stored["ok"] is True, stored
    assert stored["stored"] is True
    assert any(line.endswith("is saved.") for line in stored["status"])
    assert "Open the Confirm card" not in " ".join(stored["status"])
    assert session_open(seq) is False

    state = load_state(seq)
    state["word"] = {"name": f"{seq}.docx"}
    save_state(seq, state)
    edited = essay_revise(seq, "Tighten the opening. Do not add sources.", "draft")
    assert edited["ok"] is True, edited
    assert edited.get("quiet") is not True
    assert any(line.startswith("I have started work on ") for line in edited["status"])
    assert session_open(seq)
    saved = essay_revise(seq, "Tighten the opening. Do not add sources.", "confirm")
    assert saved["ok"] is True, saved
    assert any(line.endswith("is saved.") for line in saved["status"])
    assert session_open(seq) is False


def test_ac4_failed_spawn_does_not_stick_and_exit_clears_the_session(workspace, monkeypatch):
    """AC4: a failed start leaves no session. Exit clears it, so later silence is not still-working."""
    seq = open_sequence()
    clock = {"t": 0.0}
    _clock(monkeypatch, clock)
    monkeypatch.setattr("essay_writer.cursor_office.spawn_agent", _skipped)
    failed = start_stage_mid(seq, "4a")
    assert failed["started"] is False
    assert failed["status"] == []
    assert session_open(seq) is False
    clock["t"] = HEARTBEAT_SECONDS
    assert due_lines(seq) == []

    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_GROK_BUILD)
    grok_failed = start_stage_mid(seq, "4a")
    assert grok_failed["command"][0] == "grok"
    assert grok_failed["command"][0] != "agent"
    assert grok_failed["started"] is False
    assert grok_failed["status"] == []
    assert session_open(seq) is False

    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: "cursor")
    monkeypatch.setattr("essay_writer.cursor_office.spawn_agent", _started)
    clock["t"] = 0.0
    running = start_stage_mid(seq, "4a")
    assert running["status"]
    assert session_open(seq)
    finish_mid_process(seq)
    assert session_open(seq) is False
    clock["t"] = HEARTBEAT_SECONDS
    assert due_lines(seq) == []
    assert not any("still working" in line.casefold() for line in student_inbox(seq))

    monkeypatch.setattr("essay_writer.build_office.spawn_grok", _started)
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_GROK_BUILD)
    clock["t"] = 0.0
    grok_running = start_stage_mid(seq, "8")
    assert grok_running["started"] is True
    assert grok_running["shell"] == "grok"
    assert session_open(seq)
    finish_mid_process(seq)
    assert session_open(seq) is False


def test_ac5_stored_confirm_and_stage5_quiet_use_the_done_line(workspace, monkeypatch):
    """AC5: after the save, do not say to open the Confirm card. Stage 5 quiet does not also say a start."""
    seq = open_sequence()
    for stage in ("4a", "4b"):
        reset_status()
        begin_mid_build(seq, "gathering" if stage == "4a" else "notes", subject=QUESTION)
        done = reply_status(
            "essay.stage",
            {"essay_id": seq, "stage": stage, "confirmPhase": "confirm", "look": LOOK},
            {"ok": True, "stored": True, "essay_id": seq},
        )
        assert done == [saved_sentence(QUESTION)]
        assert "Open the Confirm card" not in done[0]
        assert "gathered the sources" not in done[0]
        assert "written a note" not in done[0]
        assert session_open(seq) is False

    brief = workspace / "Essay-writer" / ESSAY / "brief.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(f"Format: report\nQuestion: {QUESTION}\n", encoding="utf-8")
    reset_status()
    finished = reply_status(
        "essay.stage",
        {"essay_id": seq, "stage": "5", "confirmPhase": "draft", "look": LOOK},
        {"ok": True, "stored": True, "essay_id": seq, "started": {"stage": "6"}},
    )
    assert finished == [milestone_sentence("draft", QUESTION)]
    assert start_sentence("drafting", QUESTION) not in finished
    assert "Open the Confirm card" not in finished[0]
    assert session_open(seq) is False

    assert "On a quiet reply, say the chat line." in INSTRUCTIONS
    assert "Do not say that work is starting on the turn that finishes it." in INSTRUCTIONS
    assert "say the chat line" in FIRST_DRAFT_NOTE
    assert "say only the chat line" not in FIRST_DRAFT_NOTE
    assert "Do not say that the step is starting on the turn that finishes it." in FIRST_DRAFT_NOTE

    write_upload(workspace)
    fresh = open_sequence()
    for stage in ("1", "2", "3", "4a", "4b"):
        draft = front_office_call(
            "essay.stage",
            {"essay_id": fresh, "stage": stage, "confirmPhase": "draft", "look": LOOK},
        )
        assert draft["ok"] is True, draft
        if stage == "4a":
            plant_gathered_source(fresh)
        if stage == "5":
            continue
        saved = front_office_call(
            "essay.stage",
            {"essay_id": fresh, "stage": stage, "confirmPhase": "confirm", "look": LOOK, **picked(draft)},
        )
        assert saved["ok"] is True, saved
    stage5 = front_office_call(
        "essay.stage",
        {"essay_id": fresh, "stage": "5", "confirmPhase": "draft", "look": LOOK},
    )
    assert stage5["ok"] is True, stage5
    assert stage5["quiet"] is True
    assert stage5["chat"] == STAGE6_OPEN
    assert stage5["status"] == [milestone_sentence("draft", QUESTION)]
    assert start_sentence("drafting", QUESTION) not in stage5["status"]
    assert "Open the Confirm card" not in " ".join(stage5["status"])
    assert load_pointer(fresh)["current"] == "6"


def test_ac6_copy_repeat_unknown_and_session_file(workspace, monkeypatch):
    """AC6: no invented copy phases, repeat still speaks, unknown does not reset, session survives restart."""
    seq = open_sequence()
    assert saved_pack_status(seq) == []
    assert "gathered" not in " ".join(saved_pack_status(seq))
    assert "annotated" not in " ".join(saved_pack_status(seq))

    begin_mid_build(seq, "gathering", subject=QUESTION)
    note_milestone(seq, "sources")
    note_milestone(seq, "annotation", activity="annotating")
    pack = saved_pack_status(seq)
    assert milestone_sentence("sources", QUESTION) in pack
    assert milestone_sentence("annotation", QUESTION) in pack
    assert start_sentence("gathering", QUESTION) not in pack

    clock = {"t": 0.0}
    _clock(monkeypatch, clock)
    reset_status()
    begin_mid_build(seq, "notes", subject=QUESTION)
    first = note_milestone(seq, "open_full")
    second = note_milestone(seq, "open_full")
    assert first and second
    assert "opens in full" in first[-1]
    assert "opens in full" in second[-1]
    clock["t"] = 50
    assert note_milestone(seq, "not_a_real_phase") == []
    clock["t"] = HEARTBEAT_SECONDS
    stale = due_lines(seq)
    assert stale == [heartbeat_sentence("", QUESTION)]

    reset_status()
    pointer = work_dir(seq) / "tracking" / "stage.json"
    existed = pointer.is_file()
    before = pointer.read_bytes() if existed else None
    begin_mid_build(seq, "gathering", subject=QUESTION)
    session_file = work_dir(seq) / "mid-session.json"
    assert session_file.is_file()
    assert session_file.name != "stage.json"
    forget_process_memory()
    assert session_open(seq) is True
    assert pointer.is_file() is existed
    if existed:
        assert pointer.read_bytes() == before

    holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        from essay_writer.build_status import bind_job

        bind_job(seq, pid=holder.pid, stage="4a", shell="cursor")
        holder.kill()
        holder.wait(timeout=5)
        forget_process_memory()
        assert session_open(seq) is False
    finally:
        if holder.poll() is None:
            holder.kill()


def test_spawn_keeps_stdout_for_both_shells():
    """The live reader is attached by both spawn paths. Stdout is not discarded."""
    import inspect

    from essay_writer.mid_spawn import open_mid_child

    cursor = inspect.getsource(spawn_agent)
    grok = inspect.getsource(spawn_grok)
    spawn = inspect.getsource(open_mid_child)
    assert "open_mid_child" in cursor
    assert "open_mid_child" in grok
    assert "stdin=subprocess.DEVNULL" not in spawn
    assert "stderr=subprocess.DEVNULL" not in spawn
    assert "stderr=subprocess.PIPE" in spawn
    assert "pty.openpty" in spawn
    assert "follow_mid_process" in inspect.getsource(start_stage_mid)
