"""Mid-office child stdio and the exit code on the shell row.

AC1: a closed stdin exits 1 in the same second. The product spawn does not.
AC2: the shell row records exit_code and a short stderr line.
AC3: stage 5 still records that exit after the draft stores and the session closes.
AC4: the retry sentence is said only when the child exit code is non-zero.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest
from helpers import open_sequence

from essay_writer.build_status import (
    join_mid_readers,
    reply_status,
    reset_status,
    session_open,
    student_inbox,
)
from essay_writer.cursor_office import start_stage_mid
from essay_writer.mid_spawn import open_mid_child
from essay_writer.setup import SHELL_CURSOR, SHELL_GROK_BUILD

_RETRY = "try this step again"
_TTY_GUARD = """import os, sys
if not os.isatty(0) or not os.isatty(1):
    sys.stderr.write("closed-stdio\\n")
    raise SystemExit(1)
"""
_LOOK = "The first draft answers the assignment question in plain words."


@pytest.fixture(autouse=True)
def _clear_status():
    reset_status()
    yield
    join_mid_readers(2)
    reset_status()


def _write_script(path: Path, body: str) -> None:
    path.write_text("#!/usr/bin/env python3\n" + _TTY_GUARD + body, encoding="utf-8")
    path.chmod(0o755)


def _arm(monkeypatch, script: Path, shell: str) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    if shell == "grok":
        monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_GROK_BUILD)
        monkeypatch.setattr("essay_writer.setup.grokbuild_binary", lambda: str(script))
    else:
        monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_CURSOR)
        monkeypatch.setattr("essay_writer.setup.cursor_cli_binary", lambda: str(script))


def _rows(essay_id: str) -> list[dict]:
    from essay_writer.paths import work_dir

    path = work_dir(essay_id) / "ml-events.jsonl"
    assert path.is_file(), path
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _shells(essay_id: str, event: str, shell_name: str) -> list[dict]:
    return [
        row
        for row in _rows(essay_id)
        if row.get("kind") == "shell" and row.get("event") == event and row.get("shell") == shell_name
    ]


def _inbox(essay_id: str) -> str:
    return " ".join(student_inbox(essay_id)).casefold()


def test_ac1_spawn_does_not_exit_on_closed_stdin(requires_pty, workspace, monkeypatch, tmp_path):
    """AC1. Closed stdin exits 1 immediately. The product child runs past that second."""
    del workspace
    seq = open_sequence()
    spawn_src = Path(open_mid_child.__code__.co_filename).read_text(encoding="utf-8")
    assert "stdin=subprocess.DEVNULL" not in spawn_src
    assert "stderr=subprocess.DEVNULL" not in spawn_src
    for shell, shell_name in (("cursor", "Cursor"), ("grok", "Build")):
        reset_status()
        marker = tmp_path / f"ac1-{shell}"
        script = tmp_path / f"ac1-{shell}.py"
        _write_script(
            script,
            "import time\n"
            "from pathlib import Path\n"
            f"path = Path({str(marker)!r})\n"
            "path.write_text('running\\n', encoding='utf-8')\n"
            "sys.stdout.write('mid-phase: open_full\\n')\n"
            "sys.stdout.flush()\n"
            "time.sleep(1.1)\n"
            "path.write_text('running\\nfinished\\n', encoding='utf-8')\n"
            "raise SystemExit(0)\n",
        )
        broken = subprocess.run(
            [str(script)],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=3,
            check=False,
        )
        assert broken.returncode == 1
        assert b"closed-stdio" in broken.stderr
        assert not marker.exists()
        _arm(monkeypatch, script, shell)
        started_at = time.monotonic()
        started = start_stage_mid(seq, "4a")
        assert started["started"] is True, started
        assert started["shell"] == shell
        join_mid_readers(5)
        elapsed = time.monotonic() - started_at
        assert elapsed >= 1.0
        assert marker.read_text(encoding="utf-8") == "running\nfinished\n"
        inbox = _inbox(seq)
        assert "opens in full" in inbox
        assert _RETRY not in inbox
        assert "stopped before it finished" not in inbox
        done = _shells(seq, "done", shell_name)
        assert done
        assert done[-1]["exit_code"] == 0
        assert not any(row.get("exit_code") == 1 for row in _shells(seq, "exit", shell_name))


def test_ac2_ml_events_record_exit_code(requires_pty, workspace, monkeypatch, tmp_path):
    """AC2. A child exit stores exit_code and a short stderr line on the shell row."""
    del workspace
    seq = open_sequence()
    for shell, shell_name in (("cursor", "Cursor"), ("grok", "Build")):
        reset_status()
        script = tmp_path / f"ac2-{shell}.py"
        _write_script(
            script,
            "sys.stderr.write('model rejected\\n')\n"
            "sys.stderr.flush()\n"
            "raise SystemExit(2)\n",
        )
        _arm(monkeypatch, script, shell)
        started = start_stage_mid(seq, "6")
        assert started["started"] is True, started
        assert started["shell"] == shell
        join_mid_readers(4)
        exits = _shells(seq, "exit", shell_name)
        assert exits, _rows(seq)
        row = exits[-1]
        assert row["exit_code"] == 2
        assert row["stderr"] == "model rejected"
        assert "exit_code" in row
        prose = json.dumps(row)
        assert "Code 2" not in prose
        assert _RETRY in _inbox(seq)


def test_ac3_stage5_keeps_child_exit_after_draft_stores(requires_pty, workspace, monkeypatch, tmp_path):
    """AC3. Storing the stage 5 draft closes the session and still logs the child exit."""
    del workspace
    seq = open_sequence()
    for shell, shell_name in (("cursor", "Cursor"), ("grok", "Build")):
        reset_status()
        release = tmp_path / f"ac3-go-{shell}"
        script = tmp_path / f"ac3-{shell}.py"
        _write_script(
            script,
            "import time\n"
            "from pathlib import Path\n"
            f"release = Path({str(release)!r})\n"
            "sys.stderr.write('stage5 child ending\\n')\n"
            "sys.stderr.flush()\n"
            "for _ in range(50):\n"
            "    if release.exists():\n"
            "        break\n"
            "    time.sleep(0.1)\n"
            "else:\n"
            "    raise SystemExit(9)\n"
            "raise SystemExit(4)\n",
        )
        _arm(monkeypatch, script, shell)
        started = start_stage_mid(seq, "5")
        assert started["started"] is True, started
        assert started["shell"] == shell
        assert session_open(seq) is True
        reply_status(
            "essay.stage",
            {"essay_id": seq, "stage": "5", "confirmPhase": "draft", "look": _LOOK},
            {"ok": True, "stored": True, "essay_id": seq},
        )
        assert session_open(seq) is False
        release.write_text("go\n", encoding="utf-8")
        join_mid_readers(5)
        exits = _shells(seq, "exit", shell_name)
        assert exits, _rows(seq)
        row = exits[-1]
        assert row["exit_code"] == 4
        assert "stage5 child ending" in row["stderr"]
        assert session_open(seq) is False


def test_ac4_retry_message_only_when_child_failed(requires_pty, workspace, monkeypatch, tmp_path):
    """AC4. Exit 0 does not ask the student to try again. A real non-zero exit does."""
    del workspace
    seq = open_sequence()
    for shell in ("cursor", "grok"):
        reset_status()
        ok_script = tmp_path / f"ac4-ok-{shell}.py"
        _write_script(
            ok_script,
            "sys.stdout.write('mid-phase: open_full\\n')\n"
            "sys.stdout.flush()\n"
            "raise SystemExit(0)\n",
        )
        broken = subprocess.run(
            [str(ok_script)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False,
        )
        assert broken.returncode == 1
        _arm(monkeypatch, ok_script, shell)
        started = start_stage_mid(seq, "7")
        assert started["started"] is True, started
        join_mid_readers(4)
        assert _RETRY not in _inbox(seq)
        assert "stopped before it finished" not in _inbox(seq)

        reset_status()
        bad_script = tmp_path / f"ac4-bad-{shell}.py"
        _write_script(
            bad_script,
            "sys.stderr.write('model rejected\\n')\n"
            "sys.stderr.flush()\n"
            "raise SystemExit(2)\n",
        )
        _arm(monkeypatch, bad_script, shell)
        failed = start_stage_mid(seq, "9")
        assert failed["started"] is True, failed
        assert failed["shell"] == shell
        join_mid_readers(4)
        inbox = _inbox(seq)
        assert _RETRY in inbox
        assert "stopped before it finished" in inbox
