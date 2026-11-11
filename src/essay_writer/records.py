"""One JSON record store: tolerant read, guarded writer-unique atomic write.

Every small store on the sequence tree repeats the same three steps. This
module is that shape once, so the stores keep their own defaults and their
own validation but not their own error handling or temp-file naming.

A write lands through `tempfile.mkstemp` in the target folder and
`os.replace`, so two writers of the same record never share a temp file and
a reader never sees a half-written record. The temp name carries a random
suffix, not the fixed `.json.tmp` name the hand-rolled writers used.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from essay_writer.known_paths import refuse_repo_write


def read_json(
    path: Path | str,
    default: dict[str, Any] | None = None,
    *,
    validate: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, Any] | None:
    """Read one JSON object, or return default.

    A missing file, an unreadable file, invalid JSON, and a non-object all
    return default. `validate` is the store's own structural check: a record
    that fails it is treated as absent. That keeps each store's read
    semantics while the error handling is shared.
    """
    target = Path(path)
    if not target.is_file():
        return default
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
    if not isinstance(data, dict):
        return default
    if validate is not None and not validate(data):
        return default
    return data


def write_json(
    path: Path | str,
    record: dict[str, Any],
    *,
    mkdir: bool = False,
    guard: bool = True,
) -> None:
    """Write one JSON object atomically.

    `guard` refuses a destination in the code checkout before anything is
    written. `mkdir` creates the parent folder for callers whose store lives
    in a folder that may not exist yet. The temp file is writer-unique and is
    removed if the write or replace fails.
    """
    target = Path(path)
    if guard:
        refuse_repo_write(target)
    if mkdir:
        target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(record, indent=2, ensure_ascii=False) + "\n"
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
