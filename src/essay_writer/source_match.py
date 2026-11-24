"""Whether two gathered rows name the same work. Short tokens do not match."""

from __future__ import annotations

import re
from typing import Any


def _slug(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _equal_token(left: object, right: object) -> bool:
    if not isinstance(left, str) or not isinstance(right, str):
        return False
    a = left.strip()
    b = right.strip()
    if len(a) < 6 or len(b) < 6:
        return False
    if a.casefold() == b.casefold():
        return True
    sa = _slug(a)
    sb = _slug(b)
    return len(sa) >= 6 and sa == sb


def same_source(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """True when two rows name the same gathered source. Short tokens do not match."""
    for key in ("doi", "url", "title", "id"):
        if _equal_token(left.get(key), right.get(key)):
            return True
    for record, other in ((left, right), (right, left)):
        doi = record.get("doi")
        url = other.get("url")
        if not isinstance(doi, str) or not isinstance(url, str):
            continue
        token = _slug(doi)
        if len(token) >= 6 and token in _slug(url):
            return True
    return False
