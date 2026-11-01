"""Clear Mac quarantine and provenance on a Documents deliverable.

Called from the handoff copy before that copy is treated as delivered.
When the mark is not on the file, or this system has no xattr support,
the file is left unchanged.
"""

from __future__ import annotations

import os
from pathlib import Path

QUARANTINE_ATTRS = ("com.apple.quarantine", "com.apple.provenance")


def clear_mac_quarantine(path: Path) -> dict[str, object]:
    """Drop quarantine and provenance on one file. Absent marks are a no-op."""
    target = Path(path)
    if not target.is_file():
        return {"ok": True, "cleared": [], "absent": list(QUARANTINE_ATTRS), "noop": True}
    cleared: list[str] = []
    absent: list[str] = []
    remover = getattr(os, "removexattr", None)
    if remover is None:
        return {
            "ok": True,
            "cleared": [],
            "absent": list(QUARANTINE_ATTRS),
            "noop": True,
        }
    for name in QUARANTINE_ATTRS:
        try:
            remover(target, name)
        except OSError:
            absent.append(name)
            continue
        cleared.append(name)
    return {"ok": True, "cleared": cleared, "absent": absent, "noop": not cleared}
