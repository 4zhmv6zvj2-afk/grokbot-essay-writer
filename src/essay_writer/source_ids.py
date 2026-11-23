"""A source id names one stored work, and it does not follow list order.

The same paper keeps the same id when the list is rebuilt or reordered.
Two different papers do not share an id. A short in-text form and a
surname-plus-year are not ids.
"""

from __future__ import annotations

import re
from typing import Any


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


def stable_source_id(record: dict[str, Any]) -> str:
    """Id of this work. Empty when the record has nothing stable to name.

    A DOI is the id. Without a DOI, the author, title, and year are the id.
    A file locator is next. List position is never an id.
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
        return f"work:{author}|{title}|{year}"
    locator = _text(record.get("locator")).replace("\\", "/")
    if locator:
        return "loc:" + locator.casefold()
    return ""


def source_ids_for(records: list[dict[str, Any]]) -> list[str]:
    """One stable id per record, in the same order as ``records``.

    Reordering the records does not change the id of a paper. Two papers
    that are not the same work do not receive one id. The same work keeps
    one id, including when it is listed twice.
    """
    return [stable_source_id(record) for record in records]
