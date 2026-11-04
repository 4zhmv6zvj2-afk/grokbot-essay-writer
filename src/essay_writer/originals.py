"""List and read one essay's uploads and brief. No cross-essay reads."""

from __future__ import annotations

from typing import Any

from essay_writer.canon import file_sha256
from essay_writer.confirm import refuse
from essay_writer.invent import read_gathered_text
from essay_writer.paths import (
    BRIEF_NAMES,
    confine,
    essay_dir,
    relative,
    target_error,
    uploads_dir,
)

READ_CHAR_CAP = 200_000


def _files(folder) -> list[dict[str, Any]]:
    if not folder.is_dir():
        return []
    found: list[dict[str, Any]] = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in path.relative_to(folder).parts):
            continue
        found.append(
            {
                "name": path.relative_to(folder).as_posix(),
                "locator": relative(path),
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    return found


def material_locators(essay_id: str) -> list[str]:
    locators = [item["locator"] for item in _files(uploads_dir(essay_id))]
    folder = essay_dir(essay_id)
    if folder.is_dir():
        for name in sorted(BRIEF_NAMES):
            path = folder / name
            if path.is_file():
                locators.append(relative(path))
    return locators


def essay_originals(
    essay_id: str,
    action: str = "list",
    name: str | None = None,
    kind: str = "upload",
) -> dict[str, object]:
    error = target_error(essay_id)
    if error:
        return refuse("essay-id", error)
    if action not in {"list", "read"}:
        return refuse("originals", "action must be list or read")
    if kind not in {"upload", "brief"}:
        return refuse("originals", "kind must be upload or brief")
    if action == "list":
        from essay_writer.databases import database_view

        return {
            "ok": True,
            "essay_id": essay_id,
            "read_only": True,
            "uploads": _files(uploads_dir(essay_id)),
            "brief": [
                item
                for item in _files(essay_dir(essay_id))
                if item["name"].lower() in BRIEF_NAMES
            ],
            "databases": database_view(essay_id),
        }
    if not name:
        return refuse("originals", "read needs the file name inside this essay")
    try:
        base = uploads_dir(essay_id) if kind == "upload" else essay_dir(essay_id)
        path = confine(base, name)
    except ValueError as exc:
        return refuse("cross-essay" if "escape" in str(exc) else "originals", str(exc))
    if kind == "brief" and path.name.lower() not in BRIEF_NAMES:
        return refuse("originals", "brief read only opens brief.md, brief.txt, or brief.docx")
    if not path.is_file():
        return refuse("originals", "that file is not in this essay")
    try:
        from essay_writer.known_paths import research_file

        if research_file(essay_id, str(path)) is None:
            return refuse("invented", "Do not invent a student folder path.")
        text = read_gathered_text(path, essay_id)
    except ValueError as exc:
        return {
            "ok": True,
            "essay_id": essay_id,
            "read_only": True,
            "locator": relative(path),
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
            "text": None,
            "reason": str(exc),
        }
    truncated = len(text) > READ_CHAR_CAP
    if truncated:
        text = text[:READ_CHAR_CAP]
    return {
        "ok": True,
        "essay_id": essay_id,
        "read_only": True,
        "locator": relative(path),
        "sha256": file_sha256(path),
        "bytes": path.stat().st_size,
        "text": text,
        "truncated": truncated,
    }
