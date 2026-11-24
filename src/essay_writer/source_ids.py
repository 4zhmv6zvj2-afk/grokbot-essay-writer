"""A source id names one stored work, and it does not follow list order.

The same paper keeps the same id when the list is rebuilt or reordered.
Two different papers do not share an id. A short in-text form and a
surname-plus-year are not ids.

A supplied id is kept when it is at most 80 characters and uses only
letters, digits, and the marks ``. _ : / -``. Any other supplied id is
ignored, and one is minted from the work. The minted id is stored for
that file on first sight. A later look-up that fills a DOI, an author,
or a title does not mint a second id.

Minting itself lives in ``sources.py``. This module reads the id already
stored for a file and does not derive a second one.
"""

from __future__ import annotations

from typing import Any

from essay_writer.sources import stable_source_id, text, valid_source_id

__all__ = [
    "saved_source_id",
    "source_ids_for",
    "stable_source_id",
    "valid_source_id",
]


def saved_source_id(essay_id: str, locator: str) -> str:
    """The id already stored for this file, or empty when this is the first sight."""
    raw = text(locator).replace("\\", "/")
    if not text(essay_id) or not raw:
        return ""
    from essay_writer.paths import work_dir
    from essay_writer.records import read_json

    root = work_dir(essay_id)
    listed = read_json(root / "citation-list.json")
    if isinstance(listed, dict):
        for entry in listed.get("entries") or []:
            if not isinstance(entry, dict):
                continue
            if text(entry.get("locator")).replace("\\", "/") != raw:
                continue
            ident = text(entry.get("source_id"))
            if ident:
                return ident
    folder = root / "output" / "source-records"
    if not folder.is_dir():
        return ""
    for path in sorted(folder.glob("*.record.json")):
        data = read_json(path)
        if not isinstance(data, dict):
            continue
        if text(data.get("locator")).replace("\\", "/") != raw:
            continue
        ident = text(data.get("source_id"))
        if ident:
            return ident
    return ""


def source_ids_for(records: list[dict[str, Any]]) -> list[str]:
    """One stable id per record, in the same order as ``records``.

    Reordering the records does not change the id of a paper. Two papers
    that are not the same work do not receive one id. The same work keeps
    one id, including when it is listed twice.
    """
    return [stable_source_id(record) for record in records]
