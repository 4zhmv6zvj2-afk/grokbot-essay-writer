"""A source id names one stored work, and it does not follow list order.

The same paper keeps the same id when the list is rebuilt or reordered.
Two different papers do not share an id. A short in-text form and a
surname-plus-year are not ids.

A supplied id is kept when it is at most 80 characters and uses only
letters, digits, and the marks ``. _ : / -``. Any other supplied id is
ignored, and one is minted from the work. The minted id is stored for
that file on first sight. A later look-up that fills a DOI, an author,
or a title does not mint a second id.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

_ID_LIMIT = 80
_TITLE_KEEP = 48
_SUPPLIED = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,79}$")


def _text(value: object) -> str:
    if isinstance(value, bool) or value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    return ""


def _doi(value: object) -> str:
    text = _text(value)
    if not text:
        return ""
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^doi:\s*", "", text, flags=re.IGNORECASE)
    return text.strip().rstrip(".").casefold()


def _fold(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _author(record: dict[str, Any]) -> str:
    authors = record.get("authors")
    if isinstance(authors, list):
        names = [item.strip() for item in authors if isinstance(item, str) and item.strip()]
        if names:
            return " and ".join(names)
    return _text(record.get("author"))


def _year(record: dict[str, Any]) -> str:
    year = record.get("year")
    if isinstance(year, bool) or year is None:
        return ""
    if isinstance(year, int):
        return str(year)
    text = _text(year)
    return text if text.isdigit() else ""


def valid_source_id(value: object) -> str:
    """The supplied id when it is safe to persist, otherwise empty."""
    text = _text(value)
    if not _SUPPLIED.fullmatch(text):
        return ""
    if ".." in text.split("/"):
        return ""
    return text


def _title_token(title: str) -> str:
    if len(title) <= _TITLE_KEEP:
        return title
    return hashlib.sha256(title.encode()).hexdigest()[:20]


def _fit_work(author: str, title: str, year: str) -> str:
    body = f"{author}|{_title_token(title)}|{year}"
    ident = f"work:{body}"
    if len(ident) <= _ID_LIMIT:
        return ident
    return "work:" + hashlib.sha256(body.encode()).hexdigest()[:24]


def stable_source_id(record: dict[str, Any]) -> str:
    """Id of this work. Empty when the record has nothing stable to name.

    A DOI is the id. Without a DOI, the author, title, and year are the id.
    A long title is hashed so the filename stays short. A file locator is
    next. List position is never an id. A supplied id is not read here.
    """
    if not isinstance(record, dict):
        return ""
    doi = _doi(record.get("doi"))
    if doi:
        return "doi:" + doi
    title = _fold(_text(record.get("title")))
    year = _year(record)
    author = _fold(_author(record))
    if title and year and author:
        return _fit_work(author, title, year)
    locator = _text(record.get("locator")).replace("\\", "/")
    if locator:
        return "loc:" + locator.casefold()
    return ""


def saved_source_id(essay_id: str, locator: str) -> str:
    """The id already stored for this file, or empty when this is the first sight."""
    text = _text(locator).replace("\\", "/")
    if not _text(essay_id) or not text:
        return ""
    from essay_writer.paths import work_dir
    from essay_writer.records import read_json

    root = work_dir(essay_id)
    listed = read_json(root / "citation-list.json")
    if isinstance(listed, dict):
        for entry in listed.get("entries") or []:
            if not isinstance(entry, dict):
                continue
            if _text(entry.get("locator")).replace("\\", "/") != text:
                continue
            ident = _text(entry.get("source_id"))
            if ident:
                return ident
    folder = root / "output" / "source-records"
    if not folder.is_dir():
        return ""
    for path in sorted(folder.glob("*.record.json")):
        data = read_json(path)
        if not isinstance(data, dict):
            continue
        if _text(data.get("locator")).replace("\\", "/") != text:
            continue
        ident = _text(data.get("source_id"))
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
