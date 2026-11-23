"""Look-up fields stored on a saved abstract or PDF. Nothing is invented."""

from __future__ import annotations

import json
from typing import Any

from essay_writer.paths import work_dir

_KEPT_ON_ABSTRACT = (
    "author",
    "year",
    "title",
    "doi",
    "oa_url",
    "pdf_url",
    "journal",
    "pages",
    "volume",
    "url",
)


def _doi_key(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().removeprefix("https://doi.org/").casefold()


def same_lookup_value(field: str, claimed: str, stored: str) -> bool:
    """True when the claimed value is the one the look-up already stored."""
    if field == "doi":
        return bool(_doi_key(stored)) and _doi_key(claimed) == _doi_key(stored)
    return claimed.strip() == stored.strip()


def _fields_on_row(row: dict[str, Any]) -> dict[str, str]:
    kept: dict[str, str] = {}
    for field in _KEPT_ON_ABSTRACT:
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            kept[field] = value.strip()
    return kept


def _matching_lookup_row(rows: object, wanted: str) -> dict[str, str] | None:
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        found = row.get("locator")
        if not isinstance(found, str) or found.strip().replace("\\", "/") != wanted:
            continue
        return _fields_on_row(row)
    return None


def abstract_lookup_fields(essay_id: str, locator: str) -> dict[str, str]:
    """Bibliographic fields stored when this file was saved from a look-up.

    A saved abstract and a kept PDF use the same record. Only fields the
    look-up returned are present. Nothing is invented.
    """
    if not isinstance(locator, str) or not locator.strip():
        return {}
    wanted = locator.strip().replace("\\", "/")
    path = work_dir(essay_id) / "dig-card.json"
    if not path.is_file():
        return {}
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(stored, dict):
        return {}
    for key in ("abstract_files", "pdf_files"):
        matched = _matching_lookup_row(stored.get(key), wanted)
        if matched is not None:
            return matched
    return {}
