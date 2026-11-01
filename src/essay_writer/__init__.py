"""University homework essay-writer MCP. Confirm-gated Word door."""

from __future__ import annotations

import os
from pathlib import Path

__version__ = "0.1.0"

# A build writes this file next to the package modules, with the commit the
# copy was built from. The environment value wins when a label is set for one run.
BUILD_MARKER = "BUILD-COMMIT"
BUILD_ENV = "ESSAY_WRITER_BUILD"


def build_commit(package_dir: Path | str | None = None) -> str:
    """The commit this copy was built from. Empty when the copy carries no marker."""
    value = os.environ.get(BUILD_ENV, "").strip()
    if value:
        return value
    base = Path(package_dir) if package_dir is not None else Path(__file__).resolve().parent
    marker = base / BUILD_MARKER
    try:
        if marker.is_file():
            return marker.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return ""
