"""Mid-office terminal boundary. These ACs run without a real pty.

A restricted host can refuse pty.openpty. The spawn contract still has to
hold, so these tests put a stand-in pair in front of the terminal layer and
check what the product does with it.

AC1: the child gets the terminal slave as stdin and stdout, stderr stays a
     pipe, and the parent closes its copy of the slave.
AC2: a failed start closes both ends and re-raises.
AC3: a host that cannot open a terminal gets the error, not a silent fallback.
AC4: the reader closes the terminal stream when the child ends.
"""

from __future__ import annotations

import errno
import os
import subprocess
from pathlib import Path

import pytest

from essay_writer.build_status import follow_mid_process, join_mid_readers, reset_status
from essay_writer.mid_spawn import open_mid_child


class _Proc:
    pid = 4242
    stdout = None
    stderr = None

    def wait(self) -> int:
        return 0


class _Stream:
    def __init__(self) -> None:
        self.lines = [b"mid-phase: open_full\n", b""]
        self.closed = False

    def readline(self) -> bytes:
        return self.lines.pop(0) if self.lines else b""

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_terminal(monkeypatch):
    master, slave = os.pipe()
    monkeypatch.setattr("essay_writer.mid_spawn.pty.openpty", lambda: (master, slave))
    yield master, slave
    for fd in (master, slave):
        try:
            os.close(fd)
        except OSError:
            pass


def _closed(fd: int) -> bool:
    try:
        os.fstat(fd)
    except OSError:
        return True
    return False


def test_ac1_child_gets_the_terminal_slave_as_stdin_and_stdout(
    monkeypatch, fake_terminal
):
    """AC1. The start passes the slave to both stdio slots and closes its copy."""
    master, slave = fake_terminal
    calls: list[tuple[list[str], dict]] = []

    def fake_popen(argv, **kwargs):
        calls.append((list(argv), kwargs))
        return _Proc()

    monkeypatch.setattr("essay_writer.mid_spawn.subprocess.Popen", fake_popen)
    proc, stream = open_mid_child(["agent", "--model", "grok-4.7-high"])
    try:
        assert proc.pid == 4242
        argv, kwargs = calls[0]
        assert argv == ["agent", "--model", "grok-4.7-high"]
        assert kwargs["stdin"] == slave
        assert kwargs["stdout"] == slave
        assert kwargs["stderr"] is subprocess.PIPE
        assert kwargs["start_new_session"] is True
        assert kwargs["close_fds"] is True
        assert kwargs["shell"] is False
        assert stream.fileno() == master
        assert _closed(slave) is True
    finally:
        stream.close()


def test_ac2_failed_start_closes_both_ends(monkeypatch, fake_terminal):
    """AC2. A start that raises does not leave the terminal pair open."""
    master, slave = fake_terminal

    def fake_popen(argv, **kwargs):
        raise OSError(errno.EACCES, "start refused")

    monkeypatch.setattr("essay_writer.mid_spawn.subprocess.Popen", fake_popen)
    with pytest.raises(OSError):
        open_mid_child(["agent"])
    assert _closed(master) is True
    assert _closed(slave) is True


def test_ac3_missing_terminal_is_raised_not_hidden(monkeypatch):
    """AC3. No pty means the error is raised. The child is never started without one."""
    started: list[object] = []

    def no_terminal():
        raise OSError(errno.ENXIO, "out of pty devices")

    def fake_popen(argv, **kwargs):
        started.append(argv)
        return _Proc()

    monkeypatch.setattr("essay_writer.mid_spawn.pty.openpty", no_terminal)
    monkeypatch.setattr("essay_writer.mid_spawn.subprocess.Popen", fake_popen)
    with pytest.raises(OSError) as caught:
        open_mid_child(["agent"])
    assert "out of pty devices" in str(caught.value)
    assert started == []
    source = Path(open_mid_child.__code__.co_filename).read_text(encoding="utf-8")
    assert "stdin=subprocess.DEVNULL" not in source
    assert "stderr=subprocess.DEVNULL" not in source


def test_ac4_reader_closes_the_terminal_stream_when_the_child_ends(workspace):
    """AC4. The reader closes the terminal stream after the last line."""
    del workspace
    reset_status()
    try:
        stream = _Stream()
        follow_mid_process(
            "MOD1010AA-9",
            stream,
            report=lambda *_args: [],
            proc=_Proc(),
            shell="cursor",
        )
        join_mid_readers(3.0)
        assert stream.closed is True
    finally:
        reset_status()
