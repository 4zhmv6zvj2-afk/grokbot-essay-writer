"""EndNote and CSL come from the checked handbook file, not from script memory."""

from __future__ import annotations

import re
from pathlib import Path

from essay_writer.known_paths import repo_root
from essay_writer.runtime_data import handbook_text

_ENDNOTE = re.compile(r"(?im)EndNote style to select:\s*\*\*(.+?)\*\*")
_CSL = re.compile(r"(?im)^[-*]\s*CSL file:\s*(.+?)\s*$")
_NONE = re.compile(r"(?i)^(?:none|no\b|not )")


def handbook_path() -> Path:
    """Checkout docs path. A wheel install falls through to the packaged handbook."""
    return repo_root() / "docs" / "referencing-harvard.md"


def handbook_body(path: Path | None = None) -> tuple[str, str, Path | None] | None:
    """Handbook text, label, and parent dir. None when nothing readable.

    A concrete ``path``, or a real file from ``handbook_path``, wins. Otherwise
    the packaged handbook is used so an installed wheel still works.
    """
    target = path if path is not None else handbook_path()
    if path is not None or target.is_file():
        if not target.is_file():
            return None
        try:
            return target.read_text(encoding="utf-8"), str(target), target.parent
        except OSError:
            return None
    try:
        return (
            handbook_text(),
            "essay_writer.runtime/referencing-harvard.md",
            None,
        )
    except OSError:
        return None


def _parse_handbook(text: str, *, label: str, parent: Path | None) -> dict[str, object]:
    record: dict[str, object] = {
        "handbook": label,
        "checked": True,
        "endnote": None,
        "csl": None,
        "csl_reason": "No checked CSL file is named in the handbook.",
    }
    endnote = _ENDNOTE.search(text)
    if endnote:
        name = endnote.group(1).strip()
        record["endnote"] = name or None
    else:
        record["csl_reason"] = (
            "The handbook file does not name an EndNote style. None was invented."
        )
    named = _CSL.search(text)
    if named is None:
        return record
    value = named.group(1).strip().strip("*").strip()
    if not value or _NONE.match(value):
        record["csl_reason"] = "The handbook says no CSL file is checked in. None was invented."
        return record
    if parent is None:
        record["csl_reason"] = (
            "The handbook names a CSL file that is not on disk. It was not invented."
        )
        return record
    candidate = (parent / value).resolve()
    if candidate.is_file():
        record["csl"] = str(candidate)
        record["csl_reason"] = ""
        return record
    record["csl_reason"] = "The handbook names a CSL file that is not on disk. It was not invented."
    return record


def read_handbook(path: Path | None = None) -> dict[str, object]:
    """Read EndNote and CSL from the handbook file. A missing line stays blank.

    When ``path`` is omitted, a checkout docs file is preferred when present so
    tests can redirect ``handbook_path``. An installed wheel with no checkout
    docs uses the packaged handbook.
    """
    empty: dict[str, object] = {
        "handbook": "",
        "checked": False,
        "endnote": None,
        "csl": None,
        "csl_reason": "No checked CSL file is named in the handbook.",
    }
    loaded = handbook_body(path)
    if loaded is None:
        if path is not None:
            empty["handbook"] = str(path)
            empty["csl_reason"] = (
                "The handbook file is not on disk. EndNote and CSL were not taken from memory."
                if not path.is_file()
                else "The handbook file could not be read. EndNote and CSL were not taken from memory."
            )
        else:
            empty["handbook"] = "essay_writer.runtime/referencing-harvard.md"
            empty["csl_reason"] = (
                "The handbook file could not be read. EndNote and CSL were not taken from memory."
            )
        return empty
    text, label, parent = loaded
    return _parse_handbook(text, label=label, parent=parent)
