"""Short progress sentences while file work is running.

Cursor and Grok Build use the same tip sheet. The front office says those
lines. It does not invent a phase. There is no watch link.

A job starts with one start line when the mid path actually starts. A mid
tip is said only when that path signals a phase. If the path stays silent
for about five minutes, one calm still-working line is delivered without
another door reply, then the next line is a tip or the ready line. A short
job does not get that ping. No mid path means no working line. The session
ends when the process or the job ends.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from essay_writer.student_voice import say

# About five minutes of silence, once. Not a line on a fixed repeating clock.
HEARTBEAT_SECONDS = 300

# Operator text. The front office says these lines for every mid-office path.
# The door copy does not name a shell. Door text stays free of those names.
MID_BUILD_STATUS_ID = "mid-build-status"
_MID_BUILD_BODY = (
    "say a short start line when that work starts. "
    "Say a mid tip only when that path signals a phase, using the mid-status tip sheet, "
    "and do not invent a phase. "
    "If that path stays silent for about five minutes, say one calm line that work is still going, "
    "then wait for a tip or until the step is ready. "
    "Do not repeat that line on a fixed clock. "
    "A short job does not get that five-minute line. "
    "This is for every mid-office stage on the stage 1 to 10 line, not only research. "
    "When the step is ready, say so and give the next ask. "
    "Name the Confirm card only when that stage's card is in the latest door result and the artifact is ready to lock. "
    "Do not warn about a later stage's card while file work is still running. "
    "Use the status sentences on the reply. Say them in that same turn. "
    "Do not wait for another poke. "
    "A logging notification is not the chat line. "
    "Say a short start line when the reply includes status for a started job. "
    "A status line does not save the stage and does not replace the Confirm card. "
    "Do not add a watch link. "
    "If no mid-office path is running, do not say that work is still going. "
    "When file work stops early or the CLI exits with an error, say the short exit line from the tip sheet. "
    "Do not go quiet. "
    "When a tip names the standard, use the opening already printed for this assignment. "
    "A diary with a table uses How to score high and the printed top column. "
    "An essay or a report with a scheme uses what the mark scheme scores. "
    "If there is no scheme, use the brief and the assignment ask. "
    "Never invent a band. "
    "Do not rename a diary column to the words mark scheme."
)
MID_BUILD_STATUS = (
    "While Cursor CLI or Grok Build is doing the file work, and on any other mid-office path, "
    + _MID_BUILD_BODY
)
MID_BUILD_DOOR = "While file work is going, " + _MID_BUILD_BODY
TIP_SHEET = Path(__file__).resolve().parents[2] / "docs" / "templates" / "mid-status.md"

_ACTIVITIES = {
    "4a": "gathering",
    "4b": "notes",
    "5": "drafting",
}
_MILESTONE_ACTIVITY = {
    "sources": "gathering",
    "annotation": "annotating",
    "notes": "notes",
    "draft": "drafting",
}
_BANNED = re.compile(
    r"\b(?:cli|cursor|grok|paths?|reviews?|agent|heartbeat|milestones?|"
    r"doors?|dig|office|spawn|watch|shells?|argv|subprocess|mcp|residual)\b|"
    r"https?://|~/|(?:/[\w.-]+){2,}",
    re.IGNORECASE,
)
_PHASE_LINE = re.compile(r"^mid-phase:\s*([A-Za-z0-9_]+)\s*$", re.IGNORECASE)

_sessions: dict[str, dict[str, Any]] = {}
_pending: dict[str, list[str]] = {}
_delivered: dict[str, list[str]] = {}
_outbox: list[tuple[str, list[str]]] = []
_hooks: list[Callable[[str, list[str]], None]] = []
_known: set[str] = set()
_closed: set[str] = set()
_persisted: set[Path] = set()
_readers: list[threading.Thread] = []
_mcp_session: dict[str, Any] = {}
_lock = threading.RLock()
_clock_started = False
_sheet: dict[str, dict[str, str]] | None = None

_TIP_SECTIONS = ("sources", "deep_read", "draft", "quality", "ask_edit", "word_final", "phases")
_INDEX_NAME = "mid-sessions.json"
_SESSION_NAME = "mid-session.json"


def tip_sheet() -> dict[str, dict[str, str]]:
    """Templates the front office rephrases. Loaded from the tip sheet, not stage save."""
    global _sheet
    if _sheet is not None:
        return _sheet
    sections: dict[str, dict[str, str]] = {}
    current = ""
    for raw in TIP_SHEET.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("## "):
            current = line[3:].strip().casefold().replace(" ", "_")
            sections.setdefault(current, {})
            continue
        if not current or not line.startswith("- ") or ":" not in line:
            continue
        key, text = line[2:].split(":", 1)
        sections[current][key.strip()] = text.strip()
    _sheet = sections
    return _sheet


def _template(section: str, key: str) -> str:
    return tip_sheet().get(section, {}).get(key, "")


def _phase_template(kind: str) -> str:
    sheet = tip_sheet()
    for section in _TIP_SECTIONS:
        found = sheet.get(section, {}).get(kind)
        if found:
            return found
    return ""


def _now() -> float:
    return time.monotonic()


def _wall() -> float:
    return time.time()


def reset_status() -> None:
    """Drop open work. Tests call this so one run does not leak into the next."""
    with _lock:
        paths = list(_persisted)
        _sessions.clear()
        _pending.clear()
        _delivered.clear()
        _outbox.clear()
        _known.clear()
        _closed.clear()
        _persisted.clear()
        _readers.clear()
    index = _index_path()
    if index is not None:
        paths.append(index)
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            continue


def _usable_subject(subject: str, fallback: str) -> str:

    cleaned = " ".join(say(subject).split()) if isinstance(subject, str) else ""
    if not cleaned or _BANNED.search(cleaned):
        other = " ".join(fallback.split()) if isinstance(fallback, str) else ""
        if other and not _BANNED.search(other):
            return other
        return "your assignment"
    if len(cleaned) > 140:
        return cleaned[:137].rstrip() + "..."
    return cleaned


def _guard(text: str, subject: str) -> str:

    spoken = " ".join(say(text).split())
    if spoken and not _BANNED.search(spoken):
        return spoken
    safe_subject = subject if subject and not _BANNED.search(subject) else "your assignment"
    fallback = f"I am still working on {safe_subject}."
    if _BANNED.search(fallback):
        return "I am still working on your assignment."
    return fallback


def subject_for(essay_id: str) -> str:
    """Labeled Question or Task only. Otherwise the sequence id, never the whole brief."""
    question = ""
    try:
        from essay_writer.assignment_gate import read_assignment

        record = read_assignment(essay_id)
        found = record.get("question") if isinstance(record, dict) else None
        if isinstance(found, str):
            question = found.strip()
    except Exception:
        question = ""
    if question:
        return _usable_subject(question, essay_id or "your assignment")
    return _usable_subject(essay_id, "your assignment")


def basis_for(essay_id: str) -> str:
    """The shared opening when the assignment prints a standard.

    A diary says How to score high. An essay or a report says what the mark
    scheme scores. With no scheme, the brief and the assignment ask.
    A band is never invented. The diary line is not renamed to the mark scheme.
    """
    try:
        from essay_writer.assignment_gate import mark_scheme_text, read_assignment
        from essay_writer.brief_contract import FINDINGS_NONE
        from essay_writer.specialists.grok_bot import standard_opening

        record = read_assignment(essay_id)
    except Exception:
        return "the brief and the assignment ask"
    kind = record.get("findings_opening") if isinstance(record, dict) else None
    if kind not in (None, FINDINGS_NONE, ""):
        opening = standard_opening(essay_id).strip()
        if opening:
            return opening
    if isinstance(record, dict) and record.get("mark_scheme"):
        scheme = mark_scheme_text(essay_id).strip()
        line = next((item.strip() for item in scheme.splitlines() if item.strip()), "")
        cleaned = _usable_subject(line, "the mark scheme") if line else "the mark scheme"
        if cleaned == "your assignment":
            return "the mark scheme"
        return cleaned
    question = record.get("question") if isinstance(record, dict) else None
    if isinstance(question, str) and question.strip():
        return _usable_subject(question.strip(), "the brief and the assignment ask")
    return "the brief and the assignment ask"


def _fill(template: str, subject: str, basis: str) -> str:
    if not template:
        return ""
    return _guard(template.format(subject=subject, basis=basis), subject)


def start_sentence(activity: str, subject: str) -> str:
    subject = _usable_subject(subject, "your assignment")
    template = _template("starts", activity) or _template("starts", "work")
    return _fill(template, subject, subject)


def milestone_sentence(kind: str, subject: str, *, basis: str | None = None) -> str:
    subject = _usable_subject(subject, "your assignment")
    template = _phase_template(kind)
    if not template:
        return ""
    return _fill(template, subject, basis or subject)


def heartbeat_sentence(activity: str, subject: str) -> str:
    """One calm still-working line. The activity does not change the words."""
    del activity
    subject = _usable_subject(subject, "your assignment")
    return _fill(_template("any", "still"), subject, subject)


def ready_sentence(subject: str, *, confirm: bool = False) -> str:
    subject = _usable_subject(subject, "your assignment")
    key = "ready_confirm" if confirm else "ready"
    return _fill(_template("any", key) or _template("any", "ready"), subject, subject)


def mid_done_sentence(subject: str) -> str:
    subject = _usable_subject(subject, "your assignment")
    return _fill(_template("any", "done_mid"), subject, subject)


_SPAWN_EXIT_KEYS = {
    "agent-cli-missing": "exit_missing_tool",
    "grok-cli-missing": "exit_missing_tool",
    "remote-cloud-banned": "exit_stopped",
}


def exit_reason_sentence(subject: str, *, spawn_reason: str | None = None, exit_code: int | None = None) -> str:
    """Plain-English line when mid-office file work stops before the step is saved."""
    subject = _usable_subject(subject, "your assignment")
    if isinstance(spawn_reason, str) and spawn_reason.strip():
        key = _SPAWN_EXIT_KEYS.get(spawn_reason.strip(), "exit_stopped")
        line = _fill(_template("any", key), subject, subject)
        if line:
            return line
    if isinstance(exit_code, int) and exit_code != 0:
        return _fill(_template("any", "exit_stopped"), subject, subject)
    return ""


def saved_sentence(subject: str) -> str:
    """The step is already stored. This does not ask for the Confirm card."""
    subject = _usable_subject(subject, "your assignment")
    template = _template("any", "saved") or "{subject} is saved."
    return _fill(template, subject, subject)


def launch_status(stage: str) -> list[str]:
    """Start line for a mid-office launch. Same sentence the front office uses."""
    activity = _ACTIVITIES.get(stage)
    if activity is None:
        return []
    return [start_sentence(activity, "your assignment")]


def attach_launch_status(launch: dict[str, Any], stage: str) -> None:
    """Put the shared start line on a Cursor or Grok Build launch and arm the clock."""
    status = launch_status(stage)
    if status:
        launch["status"] = status
    pump_idle()


def _fresh_session(activity: str, subject: str) -> dict[str, Any]:
    return {
        "activity": activity,
        "subject": subject,
        "last": _now(),
        "wall": _wall(),
        "done": set(),
        "started": True,
        "stale_said": False,
        "pid": None,
        "stage": "",
        "shell": "",
    }


def begin_mid_build(essay_id: str, activity: str, *, subject: str | None = None) -> list[str]:
    """Say the start line once. Later calls only keep the clock."""
    arm_idle_clock()
    chosen = _usable_subject(subject or subject_for(essay_id), "your assignment")
    with _lock:
        _closed.discard(essay_id)
        _known.add(essay_id)
        session = _sessions.get(essay_id)
        if session is None:
            _sessions[essay_id] = _fresh_session(activity, chosen)
            lines = [start_sentence(activity, chosen)]
        else:
            previous = session.get("activity")
            session["activity"] = activity
            if subject:
                session["subject"] = chosen
            if not session.get("started") or previous != activity:
                session["started"] = True
                session["stale_said"] = False
                session["last"] = _now()
                session["wall"] = _wall()
                lines = [start_sentence(activity, session["subject"])]
            else:
                lines = None
    if lines is None:
        lines = due_lines(essay_id)
    else:
        _persist(essay_id)
    return lines


def bind_job(
    essay_id: str,
    *,
    pid: int | None = None,
    stage: str | None = None,
    shell: str | None = None,
) -> None:
    """Remember the process that owns this session. A dead pid ends the session."""
    with _lock:
        session = _sessions.get(essay_id)
        if session is None:
            return
        if isinstance(pid, int) and pid > 0:
            session["pid"] = pid
        if stage:
            session["stage"] = stage
        if shell:
            session["shell"] = shell
    _persist(essay_id)


def note_milestone(
    essay_id: str,
    kind: str,
    *,
    activity: str | None = None,
    subject: str | None = None,
) -> list[str]:
    """Say one finished step. An unknown kind does not move the silence clock."""
    if not _phase_template(kind):
        return []
    _ensure(essay_id)
    lines: list[str] = []
    with _lock:
        closed = essay_id in _closed and essay_id not in _sessions
        open_already = essay_id in _sessions
    if closed:
        return []
    if not open_already:
        lines.extend(
            begin_mid_build(
                essay_id,
                activity or _MILESTONE_ACTIVITY.get(kind, "gathering"),
                subject=subject,
            )
        )
    with _lock:
        session = _sessions.get(essay_id)
        if session is None:
            return _unique(lines)
        if subject:
            session["subject"] = _usable_subject(subject, session["subject"])
        session["done"].add(kind)
        if activity:
            session["activity"] = activity
        elif kind in _MILESTONE_ACTIVITY:
            session["activity"] = _MILESTONE_ACTIVITY[kind]
        session["last"] = _now()
        session["wall"] = _wall()
        session["stale_said"] = False
        subject_text = str(session["subject"])
        ended = kind == "draft"
        if ended:
            _sessions.pop(essay_id, None)
            _pending.pop(essay_id, None)
            _closed.add(essay_id)
    _persist(essay_id)
    sentence = milestone_sentence(kind, subject_text, basis=basis_for(essay_id))
    if sentence:
        lines.append(sentence)
    return _unique(lines)


def due_lines(essay_id: str) -> list[str]:
    """One calm line after about five minutes of silence. Not again until a tip or a start."""
    _ensure(essay_id)
    with _lock:
        session = _sessions.get(essay_id)
        if session is None or session.get("stale_said") is True:
            return []
        if _now() - float(session["last"]) < HEARTBEAT_SECONDS:
            return []
        session["stale_said"] = True
        session["last"] = _now()
        session["wall"] = _wall()
        subject = str(session["subject"])
    _persist(essay_id)
    return [heartbeat_sentence("", subject)]


def deliver_student(essay_id: str, lines: list[str]) -> list[str]:
    """Push lines to the student. A later door reply is not required."""
    fresh = [line for line in lines if isinstance(line, str) and line]
    if not fresh:
        return []
    with _lock:
        _delivered.setdefault(essay_id, []).extend(fresh)
        _outbox.append((essay_id, list(fresh)))
        hooks = list(_hooks)
    for hook in hooks:
        try:
            hook(essay_id, list(fresh))
        except Exception:
            continue
    return fresh


def student_inbox(essay_id: str) -> list[str]:
    """Lines already pushed for this sequence. No door reply is required."""
    with _lock:
        return list(_delivered.get(essay_id, []))


def register_delivery(hook: Callable[[str, list[str]], None]) -> Callable[[], None]:
    """Hear a pushed line. The returned call removes the hook."""
    with _lock:
        _hooks.append(hook)

    def _remove() -> None:
        with _lock:
            try:
                _hooks.remove(hook)
            except ValueError:
                return

    return _remove


def take_outbox() -> list[tuple[str, list[str]]]:
    with _lock:
        batch = list(_outbox)
        _outbox.clear()
        return batch


def bind_mcp_session(session: Any) -> None:
    """Keep the live client so a later stale line can be pushed without a new tool call."""
    _mcp_session["session"] = session


def bound_mcp_session() -> Any:
    return _mcp_session.get("session")


async def flush_student_push(send: Callable[[str, list[str]], Any]) -> list[str]:
    """Hand queued lines to send. This does not call a door."""
    spoken: list[str] = []
    for essay_id, lines in take_outbox():
        await send(essay_id, lines)
        spoken.extend(lines)
    return spoken


def pump_idle() -> list[str]:
    """Deliver due still-working lines. A door reply is not required."""
    restore_open_sessions()
    with _lock:
        essay_ids = list(_known)
    posted: list[str] = []
    for essay_id in essay_ids:
        lines = due_lines(essay_id)
        if not lines:
            continue
        deliver_student(essay_id, lines)
        with _lock:
            bucket = _pending.setdefault(essay_id, [])
            for line in lines:
                if line not in bucket:
                    bucket.append(line)
        posted.extend(lines)
    return posted


def take_idle(essay_id: str) -> list[str]:
    """Lines the idle clock already posted for this sequence."""
    with _lock:
        return list(_pending.pop(essay_id, []))


def arm_idle_clock() -> None:
    """Wake the five-minute line while chat is idle. Tests call pump_idle instead."""
    global _clock_started
    with _lock:
        if _clock_started or os.environ.get("PYTEST_CURRENT_TEST"):
            return
        _clock_started = True

    def _loop() -> None:
        while True:
            time.sleep(30)
            try:
                pump_idle()
            except Exception:
                continue

    threading.Thread(target=_loop, name="essay-writer-idle", daemon=True).start()


def session_open(essay_id: str) -> bool:
    _ensure(essay_id)
    with _lock:
        return essay_id in _sessions


def live_mid_job(essay_id: str) -> dict[str, Any] | None:
    """The mid-office process still running for this sequence.

    A session with no pid, or a pid that has already exited, is not live.
    Cursor and Grok Build share this check.
    """
    _ensure(essay_id)
    with _lock:
        session = _sessions.get(essay_id)
        if session is None:
            return None
        pid = session.get("pid")
        stage = session.get("stage")
        shell = session.get("shell")
    if isinstance(pid, bool) or not isinstance(pid, int) or not _pid_alive(pid):
        return None
    return {"pid": pid, "stage": str(stage or ""), "shell": str(shell or "")}


def signaled_phases(essay_id: str) -> list[str]:
    """Phases this job has actually signaled. Order follows the tip sheet."""
    _ensure(essay_id)
    with _lock:
        session = _sessions.get(essay_id)
        done = set(session["done"]) if session else set()
    ordered: list[str] = []
    for section in _TIP_SECTIONS:
        for key in tip_sheet().get(section, {}):
            if key in done and key not in ordered:
                ordered.append(key)
    return ordered


def saved_pack_status(essay_id: str) -> list[str]:
    """Copy lines for phases already signaled. Gathered and annotated are not invented."""
    done = set(signaled_phases(essay_id))
    with _lock:
        session = _sessions.get(essay_id)
        subject = str(session["subject"]) if session else ""
    if not subject:
        subject = subject_for(essay_id)
    lines: list[str] = []
    for kind in ("sources", "annotation"):
        if kind not in done:
            continue
        sentence = milestone_sentence(kind, subject, basis=basis_for(essay_id))
        if sentence:
            lines.append(sentence)
    return _unique(lines)


def _subject_of(essay_id: str) -> str:
    with _lock:
        session = _sessions.get(essay_id)
        if session is not None:
            return str(session["subject"])
    return subject_for(essay_id)


def _mark_closed(essay_id: str) -> None:
    with _lock:
        _sessions.pop(essay_id, None)
        _pending.pop(essay_id, None)
        _closed.add(essay_id)
    _persist(essay_id)


def complete_job(essay_id: str) -> list[str]:
    """The save already happened. Do not ask the student to open the Confirm card."""
    subject = _subject_of(essay_id)
    _mark_closed(essay_id)
    line = saved_sentence(subject)
    return [line] if line else []


def finish_step(essay_id: str, kind: str) -> list[str]:
    """Done line for a finished step. This turn does not say that work is starting."""
    subject = _subject_of(essay_id)
    _mark_closed(essay_id)
    sentence = milestone_sentence(kind, subject, basis=basis_for(essay_id))
    return [sentence] if sentence else []


def spawn_exit_status(essay_id: str, spawn_reason: str) -> list[str]:
    """A failed mid-office start. No session is opened."""
    reason = spawn_reason.strip()
    if not reason or reason in {"skipped-under-test", "no-mid-stage", "not-cursor-cli", "not-grok-build"}:
        return []
    line = exit_reason_sentence(subject_for(essay_id), spawn_reason=reason)
    return [line] if line else []


def finish_mid_process(
    essay_id: str,
    *,
    exit_code: int | None = None,
    shell: str | None = None,
    stderr_line: str = "",
) -> list[str]:
    """The child exited. Record the code even if stage 5 already stored the draft.

    Closing the session when the draft stores must not drop the exit. A
    non-zero code is a real stop and is said to the student. A zero code
    after that store does not add a second retry line.
    """
    code = 0 if exit_code is None else int(exit_code)
    with _lock:
        session = _sessions.get(essay_id)
        if session is not None:
            stage = str(session.get("stage") or "")
            subject = str(session.get("subject") or "your assignment")
            if not shell:
                shell = str(session.get("shell") or "")
        else:
            stage = ""
            subject = subject_for(essay_id)
    office = {"grok": "Build", "cursor": "Cursor"}.get(str(shell or ""))
    if session is not None:
        _mark_closed(essay_id)
    if office:
        from essay_writer.debug_log import note_mid_office

        if code != 0:
            note_mid_office(
                "exit",
                essay_id,
                office,
                reason=exit_reason_sentence(subject, exit_code=code),
                exit_code=code,
                stderr_line=stderr_line,
            )
        else:
            note_mid_office("done", essay_id, office, exit_code=code, stderr_line=stderr_line)
    if code != 0:
        line = exit_reason_sentence(subject, exit_code=code)
        if not line:
            return []
        deliver_student(essay_id, [line])
        return [line]
    if session is None:
        return []
    if stage == "5":
        line = milestone_sentence("draft", subject, basis=basis_for(essay_id))
    else:
        line = mid_done_sentence(subject) or ready_sentence(subject, confirm=False)
    if not line:
        return []
    deliver_student(essay_id, [line])
    return [line]


def parse_phase_line(line: str) -> tuple[str, bool] | None:
    """A mid-phase marker, and whether that name is on the tip sheet.

    Other stdout is ignored. The front office does not invent a phase from it.
    """
    if not isinstance(line, str):
        return None
    match = _PHASE_LINE.match(line.strip())
    if match is None:
        return None
    kind = match.group(1).casefold()
    return kind, bool(_phase_template(kind))


def _stderr_tail(stderr: Any, sink: list[str]) -> None:
    """Drain a child stderr pipe so it cannot fill and stall the process."""
    if stderr is None or not hasattr(stderr, "readline"):
        return
    try:
        while True:
            raw = stderr.readline()
            if not raw:
                break
            text = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
            text = " ".join(text.split())
            if text:
                sink.append(text)
                del sink[:-4]
    except Exception:
        return


def follow_mid_process(
    essay_id: str,
    stdout: Any,
    *,
    report: Callable[[str, str], list[str]],
    proc: Any = None,
    shell: str | None = None,
) -> threading.Thread:
    """Read phase lines from a live Cursor CLI or Grok Build process.

    shell is captured here. Stage 5 can store the draft and close the
    session before the child exits. The exit record still uses this shell.
    """

    def _run() -> None:
        exit_code: int | None = None
        stderr_chunks: list[str] = []
        drainer: threading.Thread | None = None
        stderr = getattr(proc, "stderr", None) if proc is not None else None
        if stderr is not None:
            drainer = threading.Thread(
                target=_stderr_tail,
                args=(stderr, stderr_chunks),
                name="essay-writer-mid-err",
                daemon=True,
            )
            drainer.start()
        try:
            if stdout is not None and hasattr(stdout, "readline"):
                while True:
                    raw = stdout.readline()
                    if not raw:
                        break
                    text = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
                    parsed = parse_phase_line(text)
                    if parsed is None:
                        continue
                    kind, known = parsed
                    if not known:
                        note_milestone(essay_id, kind)
                        continue
                    try:
                        lines = report(essay_id, kind)
                    except Exception:
                        continue
                    if lines:
                        deliver_student(essay_id, lines)
        finally:
            try:
                if proc is not None and hasattr(proc, "wait"):
                    exit_code = int(proc.wait())
            except Exception:
                exit_code = exit_code if exit_code is not None else 1
            if drainer is not None:
                drainer.join(timeout=2.0)
            try:
                if stdout is not None and hasattr(stdout, "close"):
                    stdout.close()
            except Exception:
                pass
            try:
                finish_mid_process(
                    essay_id,
                    exit_code=exit_code,
                    shell=shell,
                    stderr_line=" ".join(stderr_chunks),
                )
            except Exception:
                return

    thread = threading.Thread(target=_run, name="essay-writer-mid", daemon=True)
    with _lock:
        _readers.append(thread)
    thread.start()
    return thread


def join_mid_readers(timeout: float = 2.0) -> None:
    with _lock:
        readers = list(_readers)
    for thread in readers:
        thread.join(timeout)


def forget_process_memory() -> None:
    """Drop the in-process copy. A restarted server loads the session file."""
    with _lock:
        _sessions.clear()
        _pending.clear()
        _closed.clear()
        _known.clear()


def _finished_draft(stage: str, phase: str, arguments: dict[str, Any], result: dict[str, Any]) -> bool:
    """True when this reply stores the first draft.

    Stage 5 stores on the draft and starts stage 6. The finished sentence
    follows that draft. It does not wait for a confirm phase, and it does
    not add a Confirm card. A stored confirm still counts if a caller sends one.
    """
    if stage != "5" or result.get("stored") is not True:
        return False
    look = arguments.get("look")
    if not isinstance(look, str) or not look.strip():
        return False
    if phase == "draft":
        from essay_writer.spine import advances_without_confirm

        return advances_without_confirm(stage) is not None
    return phase == "confirm"


def _prior_or_start(result: dict[str, Any], essay_id: str, activity: str) -> list[str]:
    """Keep a start line the door already stored. Otherwise say it only if the job started."""
    prior = result.get("status")
    if isinstance(prior, list) and any(isinstance(line, str) and line for line in prior):
        return [line for line in prior if isinstance(line, str) and line]
    if result.get("mid_started") is True:
        return begin_mid_build(essay_id, activity)
    return []


def signal_phase(
    essay_id: str,
    kind: str,
    *,
    activity: str | None = None,
    subject: str | None = None,
) -> list[str]:
    """A mid path finished a real phase. The front office does not invent this call."""
    return note_milestone(essay_id, kind, activity=activity, subject=subject)


def _signaled_lines(essay_id: str, result: dict[str, Any]) -> list[str]:
    """Tips for phases the mid path named on this reply. Missing names are skipped."""
    phases = result.get("mid_phases")
    if not isinstance(phases, list):
        return []
    lines: list[str] = []
    for kind in phases:
        if isinstance(kind, str) and kind.strip():
            lines.extend(signal_phase(essay_id, kind.strip()))
    return lines


def _close_session(essay_id: str) -> None:
    _mark_closed(essay_id)


def reply_status(name: str, arguments: dict[str, Any], result: dict[str, Any]) -> list[str]:
    """Lines the front office says for this door reply. Empty when no mid path is open."""
    if result.get("ok") is not True:
        return []
    essay_id = arguments.get("essay_id")
    if not isinstance(essay_id, str) or not essay_id.strip():
        found = result.get("essay_id")
        essay_id = found if isinstance(found, str) else ""
    essay_id = essay_id.strip()
    if not essay_id:
        return []
    phase = arguments.get("confirmPhase")
    if not isinstance(phase, str):
        phase = result.get("confirmPhase") if isinstance(result.get("confirmPhase"), str) else ""
    lines: list[str] = []
    if name == "essay.stage":
        stage = arguments.get("stage")
        if not isinstance(stage, str):
            stage = result.get("stage") if isinstance(result.get("stage"), str) else ""
        stage_text = stage if isinstance(stage, str) else ""
        phase_text = phase if isinstance(phase, str) else ""
        if _finished_draft(stage_text, phase_text, arguments, result):
            lines.extend(finish_step(essay_id, "draft"))
        elif stage == "4a" and phase == "draft":
            lines.extend(_prior_or_start(result, essay_id, "gathering"))
            lines.extend(_signaled_lines(essay_id, result))
        elif stage == "4b" and phase == "draft":
            lines.extend(_prior_or_start(result, essay_id, "notes"))
            lines.extend(_signaled_lines(essay_id, result))
        elif stage == "5" and phase == "draft":
            lines.extend(_prior_or_start(result, essay_id, "drafting"))
            lines.extend(_signaled_lines(essay_id, result))
        elif stage in {"4a", "4b"} and phase == "confirm" and result.get("stored") is True:
            lines.extend(_signaled_lines(essay_id, result))
            lines.extend(complete_job(essay_id))
        else:
            lines.extend(_signaled_lines(essay_id, result))
            lines.extend(due_lines(essay_id))
    elif name in {"essay.revise", "essay.review"} and result.get("stored") is True and result.get("quiet") is not True:
        prior = result.get("status")
        if isinstance(prior, list) and any(isinstance(line, str) and line for line in prior):
            lines.extend(line for line in prior if isinstance(line, str) and line)
        else:
            lines.extend(complete_job(essay_id))
    else:
        # A signaled phase is spoken. Silence pings only while a mid path is open.
        # A chat reply with no open path and no signal stays quiet.
        lines.extend(_signaled_lines(essay_id, result))
        lines.extend(due_lines(essay_id))
    return _unique(lines)


def _unique(lines: list[str]) -> list[str]:
    kept: list[str] = []
    for line in lines:
        if isinstance(line, str) and line and line not in kept:
            kept.append(line)
    return kept


def _pid_alive(pid: int) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _index_path() -> Path | None:
    try:
        from essay_writer.paths import workspace_root

        root = workspace_root()
    except Exception:
        return None
    if not root.is_dir():
        return None
    return root / _INDEX_NAME


def _session_path(essay_id: str) -> Path | None:
    try:
        from essay_writer.paths import work_dir

        folder = work_dir(essay_id)
    except Exception:
        return None
    if not folder.is_dir():
        return None
    return folder / _SESSION_NAME


def _read_index() -> dict[str, str]:
    path = _index_path()
    if path is None or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items() if isinstance(key, str)}


def _write_index(index: dict[str, str]) -> None:
    path = _index_path()
    if path is None:
        return
    try:
        path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with _lock:
            _persisted.add(path)
    except OSError:
        return


def _persist(essay_id: str) -> None:
    path = _session_path(essay_id)
    with _lock:
        session = _sessions.get(essay_id)
    if path is None:
        return
    if session is None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        index = _read_index()
        if essay_id in index:
            index.pop(essay_id, None)
            _write_index(index)
        return
    payload = {
        "activity": session.get("activity"),
        "subject": session.get("subject"),
        "wall": session.get("wall"),
        "done": sorted(session.get("done") or []),
        "started": bool(session.get("started")),
        "stale_said": bool(session.get("stale_said")),
        "pid": session.get("pid"),
        "stage": session.get("stage") or "",
        "shell": session.get("shell") or "",
    }
    try:
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return
    with _lock:
        _persisted.add(path)
    index = _read_index()
    index[essay_id] = str(path)
    _write_index(index)


def _load_payload(essay_id: str) -> dict[str, Any] | None:
    path = _session_path(essay_id)
    if path is None or not path.is_file():
        index = _read_index()
        raw = index.get(essay_id)
        if not raw:
            return None
        path = Path(raw)
        if not path.is_file():
            return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    pid = data.get("pid")
    if isinstance(pid, int) and pid > 0 and not _pid_alive(pid):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return None
    wall = data.get("wall")
    age = 0.0
    if isinstance(wall, (int, float)):
        age = max(0.0, _wall() - float(wall))
    done = data.get("done")
    return {
        "activity": data.get("activity") or "work",
        "subject": data.get("subject") or "your assignment",
        "last": _now() - age,
        "wall": wall if isinstance(wall, (int, float)) else _wall(),
        "done": set(item for item in done if isinstance(item, str)) if isinstance(done, list) else set(),
        "started": bool(data.get("started")),
        "stale_said": bool(data.get("stale_said")),
        "pid": pid if isinstance(pid, int) else None,
        "stage": data.get("stage") or "",
        "shell": data.get("shell") or "",
    }


def _ensure(essay_id: str) -> None:
    with _lock:
        if essay_id in _sessions or essay_id in _closed:
            return
    loaded = _load_payload(essay_id)
    if loaded is None:
        return
    with _lock:
        if essay_id not in _sessions and essay_id not in _closed:
            _sessions[essay_id] = loaded
            _known.add(essay_id)


def restore_open_sessions() -> None:
    """Load sessions a previous process left on disk. This does not write stage.json."""
    for essay_id in list(_read_index()):
        _ensure(essay_id)
