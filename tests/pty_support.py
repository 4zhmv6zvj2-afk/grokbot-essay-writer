"""Real pseudo-terminal support for the mid-office spawn tests.

The product puts a terminal on the child's stdin and stdout. That contract
needs a pty. This host can refuse one: a restricted runner may deny
/dev/ptmx, and macOS has a small pty cap. In that case the ACs that need a
real terminal skip with the host's own reason instead of a bare failure.

Linux CI sets CI=true, and there a missing pty is a failure rather than a
skip, so those ACs cannot quietly stop running there.
"""

from __future__ import annotations

import os
import pty

_PROBE: tuple[bool, str] | None = None


def pty_required() -> bool:
    """True when this run must have a real terminal (CI, or an explicit opt-in)."""
    for name in ("ESSAY_WRITER_REQUIRE_PTY", "CI"):
        value = os.environ.get(name, "").strip().casefold()
        if value in {"1", "true", "yes", "on"}:
            return True
    return False


def pty_reason() -> str | None:
    """None when a pty opens. Otherwise a sentence naming the host error."""
    global _PROBE
    if _PROBE is None:
        try:
            master, slave = pty.openpty()
        except OSError as exc:
            detail = exc.strerror or str(exc) or exc.__class__.__name__
            _PROBE = (False, f"this host cannot open a pseudo-terminal (openpty: {detail})")
        else:
            os.close(master)
            os.close(slave)
            _PROBE = (True, "")
    return None if _PROBE[0] else _PROBE[1]
