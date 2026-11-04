"""EndNote and CSL come from the checked handbook file, not from script memory."""

from __future__ import annotations

import re
from pathlib import Path

from essay_writer.known_paths import repo_root

_ENDNOTE = re.compile(r"(?im)EndNote style to select:\s*\*\*(.+?)\*\*")
_CSL = re.compile(r"(?im)^[-*]\s*CSL file:\s*(.+?)\s*$")
_NONE = re.compile(r"(?i)^(?:none|no\b|not )")


def handbook_path() -> Path:

    return repo_root() / "docs" / "referencing-harvard.md"


def read_handbook(path: Path | None = None) -> dict[str, object]:
    """Read EndNote and CSL from the handbook file. A missing line stays blank."""
    target = path if path is not None else handbook_path()
    record: dict[str, object] = {
        "handbook": str(target),
        "checked": False,
        "endnote": None,
        "csl": None,
        "csl_reason": "No checked CSL file is named in the handbook.",
    }
    if not target.is_file():
        record["csl_reason"] = "The handbook file is not on disk. EndNote and CSL were not taken from memory."
        return record
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        record["csl_reason"] = "The handbook file could not be read. EndNote and CSL were not taken from memory."
        return record
    record["checked"] = True
    endnote = _ENDNOTE.search(text)
    if endnote:
        name = endnote.group(1).strip()
        record["endnote"] = name or None
    else:
        record["csl_reason"] = "The handbook file does not name an EndNote style. None was invented."
    named = _CSL.search(text)
    if named is None:
        return record
    value = named.group(1).strip().strip("*").strip()
    if not value or _NONE.match(value):
        record["csl_reason"] = "The handbook says no CSL file is checked in. None was invented."
        return record
    candidate = (target.parent / value).resolve()
    if candidate.is_file():
        record["csl"] = str(candidate)
        record["csl_reason"] = ""
        return record
    record["csl_reason"] = "The handbook names a CSL file that is not on disk. It was not invented."
    return record
