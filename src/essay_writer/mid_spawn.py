"""Stdio for a mid-office child. Cursor and Grok Build share this opener.

The Cursor agent treats a process as headless when stdin is not a terminal
or stdout is not a terminal. Headless mode exits with code 1 in the same
second (workspace trust, or no prompt). `stdin=DEVNULL` is that closed
stdin. `stdout=PIPE` is not a terminal either. `stderr=DEVNULL` drops the
CLI error, so the student only sees a generic retry line.

A pseudo-terminal keeps stdin and stdout as terminals so the child can run
file work. stderr stays a pipe so the exit record can keep a short line.
"""

from __future__ import annotations

import os
import pty
import subprocess
from typing import IO


def open_mid_child(argv: list[str]) -> tuple[subprocess.Popen[bytes], IO[bytes]]:
    """Start argv with a terminal on stdin and stdout, and a pipe on stderr.

    The caller reads the returned stream for mid-phase lines. On OSError the
    terminal is closed and the error is re-raised. This does not fall back
    to a closed stdin.
    """
    master, slave = pty.openpty()
    try:
        proc = subprocess.Popen(
            argv,
            stdin=slave,
            stdout=slave,
            stderr=subprocess.PIPE,
            start_new_session=True,
            close_fds=True,
            shell=False,
        )
    except Exception:
        os.close(master)
        os.close(slave)
        raise
    os.close(slave)
    existing = proc.stdout
    stream: IO[bytes]
    if existing is None:
        stream = os.fdopen(master, "rb", buffering=0)
    else:
        os.close(master)
        stream = existing
    return proc, stream
