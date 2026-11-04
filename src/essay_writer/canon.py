"""Canonical JSON for Confirm identity. Same arguments, same digest."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(dump(value).encode("utf-8")).hexdigest()


def file_sha256(path: Any) -> str:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()
