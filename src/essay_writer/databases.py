"""Brief-named databases and a slot for a file the student holds.

Names come from the brief. No look-up runs. A directory path is not stored.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from essay_writer.paths import BRIEF_NAMES, essay_dir, work_dir
from essay_writer.programme import PAID_RESOLVERS

_SLOT = "student-held file"
_LINE = re.compile(r"(?im)^\s*databases?\s*:\s*(.+)$")


def _brief_text(essay_id: str) -> str:
    from essay_writer.invent import read_gathered_text

    folder = essay_dir(essay_id)
    chunks: list[str] = []
    if not folder.is_dir():
        return ""
    for name in sorted(BRIEF_NAMES):
        path = folder / name
        if not path.is_file():
            continue
        try:
            chunks.append(read_gathered_text(path, essay_id))
        except ValueError:
            continue
    return "\n".join(chunks)


def _clean_part(part: str) -> str:
    text = part.strip(" \t.;")
    text = re.sub(r"(?i)^and\s+", "", text).strip(" \t.;")
    return text


def names_from_brief(text: str) -> list[str]:
    """Database names the brief writes. Nothing is added that the brief omits."""
    if not isinstance(text, str) or not text.strip():
        return []
    names: list[str] = []
    for match in _LINE.finditer(text):
        chunk = match.group(1).split("\n", 1)[0]
        for part in re.split(r",|;|\band\b", chunk):
            cleaned = _clean_part(part)
            if not cleaned:
                continue
            if cleaned.casefold() in {"database", "databases"}:
                continue
            if any(cleaned.casefold() == item.casefold() for item in names):
                continue
            names.append(cleaned)
    lowered = text.casefold()
    for token in sorted(PAID_RESOLVERS, key=len, reverse=True):
        if token not in lowered:
            continue
        if any(token in item.casefold() for item in names):
            continue
        names.append(token)
    return names


def _slot_path(essay_id: str):
    return work_dir(essay_id) / "tracking" / "databases.json"


def _load(essay_id: str) -> dict[str, Any] | None:
    path = _slot_path(essay_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def held_filename(raw: object) -> str:
    """File name only. A directory path is dropped."""
    if not isinstance(raw, str):
        return ""
    text = raw.strip().replace("\\", "/")
    if not text:
        return ""
    name = text.split("/")[-1].strip()
    if name in {"", ".", ".."}:
        return ""
    return name


def database_view(essay_id: str) -> dict[str, Any]:
    """Names from the brief, plus the student-held file slot."""
    stored = _load(essay_id)
    live = names_from_brief(_brief_text(essay_id))
    if stored is None:
        names = live
        held = ""
    else:
        saved = stored.get("names")
        names = [item for item in saved if isinstance(item, str) and item.strip()] if isinstance(saved, list) else live
        if not names:
            names = live
        held = held_filename(stored.get("held_file"))
    return {
        "names": names,
        "held_file": held,
        "slot": _SLOT,
        "path_stored": False,
    }


def remember_databases(essay_id: str, held_file: object = None) -> dict[str, Any]:
    """Store brief names and a file name. Never a student directory path."""
    current = _load(essay_id) or {}
    names = names_from_brief(_brief_text(essay_id))
    if not names and isinstance(current.get("names"), list):
        names = [item for item in current["names"] if isinstance(item, str) and item.strip()]
    held = held_filename(held_file)
    if not held:
        held = held_filename(current.get("held_file"))
    if not names and not held:
        return database_view(essay_id)
    payload = {"names": names, "held_file": held, "slot": _SLOT, "path_stored": False}
    path = _slot_path(essay_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return database_view(essay_id)
