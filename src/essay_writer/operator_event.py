from __future__ import annotations

import json
import os
import re
import sys
import threading
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Required, TypedDict

from essay_writer.debug_log import (
    LOG_FILENAME,
    ML_EVENTS_FILENAME,
    debug_enabled,
    debug_log_path,
    land_sha,
    redact_text,
    scrub,
)
from essay_writer.paths import ESSAY_ID, SEQUENCE_ID

MAX_LINES = 200
MAX_BYTES = 256 * 1024
QUERY_LIMIT = 80
TITLE_LIMIT = 120
REASON_LIMIT = 160
STDERR_LIMIT = 160
TAIL_LIMIT = 50
WIPE_TOOL = "essay.debug.wipe"
LAND_TOOL = "essay-writer.land"
LOG_ROTATED = "debug.log.1"
EVENTS_ROTATED = "ml-events.jsonl.1"

_LOCK = threading.Lock()
_PHASES = frozenset({"draft", "confirm", "read"})
_HANDOFFS = frozenset({"copy_only", "rebuilt", "refused"})
_SHELLS = frozenset({"Cursor", "Build"})
_SHELL_EVENTS = frozenset({"start", "done", "exit"})
_SHA = re.compile(r"^[a-f0-9]{64}$")
_TOKEN = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")
_CLASS = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_STAGE = re.compile(r"^(?:eqr|[0-9]{1,2}[a-z]?)$")
_FLAG = re.compile(r"^--[a-z0-9-]{1,40}$")
_LAND = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_STATE = re.compile(r"^[A-Za-z0-9._-]{1,40}$")
_GATE = re.compile(r"^(?:[a-z][a-z0-9._-]{0,48}|[0-9]{1,2})$")
_LIMITS = {
    "query": QUERY_LIMIT,
    "title": TITLE_LIMIT,
    "reason": REASON_LIMIT,
    "stderr": STDERR_LIMIT,
}


class OperatorEvent(TypedDict, total=False):
    """Closed record. Only keys that are set are written."""

    t: Required[str]
    tool: Required[str]
    phase: str
    essay_id: str
    stage: str
    ok: bool
    wrote: bool
    stored: bool
    advanced: bool
    refused: str
    error: str
    refs_n: int
    sources_n: int
    sha256: str
    land: str
    flag: str
    handoff: str
    shell: str
    shell_event: str
    exit_code: int
    digest: str
    card_present: bool
    gate: str
    module: str
    parent: str
    saved_pack: str
    chain_armed: bool
    cover_n: int
    cover_sequence_id: int
    cover_title_line: int
    cover_counted_words: int
    query: str
    title: str
    reason: str
    stderr: str


_KEYS = frozenset(
    {
        "t",
        "tool",
        "phase",
        "essay_id",
        "stage",
        "ok",
        "wrote",
        "stored",
        "advanced",
        "refused",
        "error",
        "refs_n",
        "sources_n",
        "sha256",
        "land",
        "flag",
        "handoff",
        "shell",
        "shell_event",
        "exit_code",
        "digest",
        "card_present",
        "gate",
        "module",
        "parent",
        "saved_pack",
        "chain_armed",
        "cover_n",
        "cover_sequence_id",
        "cover_title_line",
        "cover_counted_words",
        "query",
        "title",
        "reason",
        "stderr",
    }
)
_BOOLS = frozenset({"ok", "wrote", "stored", "advanced", "card_present", "chain_armed"})
_COUNTS = frozenset(
    {
        "refs_n",
        "sources_n",
        "exit_code",
        "cover_n",
        "cover_sequence_id",
        "cover_title_line",
        "cover_counted_words",
    }
)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _essay_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if ESSAY_ID.fullmatch(text) or SEQUENCE_ID.fullmatch(text):
        return text
    return None


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _content(key: str, value: object) -> str | None:
    cleaned = _text(value)
    if cleaned is None:
        return None
    cleaned = scrub(cleaned)
    if not cleaned:
        return None
    limit = _LIMITS[key]
    if len(cleaned) > limit:
        return cleaned[:limit]
    return cleaned


def _count(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _store(event: Mapping[str, object]) -> dict[str, object] | None:
    tool = event.get("tool")
    if not isinstance(tool, str) or _TOKEN.fullmatch(tool) is None:
        tool = "unknown"
    if tool == WIPE_TOOL:
        return None
    stamp = _text(event.get("t")) or _now()
    kept: dict[str, object] = {"t": stamp, "tool": tool}
    for key in _KEYS:
        if key in {"t", "tool"} or key not in event:
            continue
        value = event[key]
        if key in _LIMITS:
            text = _content(key, value)
            if text is not None:
                kept[key] = text
            continue
        if key in _BOOLS:
            if isinstance(value, bool):
                kept[key] = value
            continue
        if key in _COUNTS:
            number = _count(value)
            if number is not None:
                kept[key] = number
            continue
        if key == "phase" and value in _PHASES:
            kept[key] = value
        elif key == "handoff" and value in _HANDOFFS:
            kept[key] = value
        elif key == "shell" and value in _SHELLS:
            kept[key] = value
        elif key == "shell_event" and value in _SHELL_EVENTS:
            kept[key] = value
        elif key in {"essay_id", "parent", "module"}:
            found = _essay_id(value)
            if found is not None:
                kept[key] = found
        elif key == "stage" and isinstance(value, str) and _STAGE.fullmatch(value):
            kept[key] = value
        elif key in {"sha256", "digest"} and isinstance(value, str) and _SHA.fullmatch(value):
            kept[key] = value
        elif key == "flag" and isinstance(value, str) and _FLAG.fullmatch(value):
            kept[key] = value
        elif key == "land" and isinstance(value, str) and _LAND.fullmatch(value.strip()):
            kept[key] = value.strip()
        elif key == "saved_pack" and isinstance(value, str) and _STATE.fullmatch(value.strip()):
            kept[key] = value.strip()
        elif key == "error" and isinstance(value, str) and _CLASS.fullmatch(value):
            kept[key] = value
        elif key in {"refused", "gate"} and isinstance(value, str) and _GATE.fullmatch(value):
            kept[key] = value
    return kept


def _render_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def render(event: Mapping[str, object]) -> str:
    kept = _store(event)
    if kept is None:
        return ""
    tool = str(kept.pop("tool"))
    stamp = str(kept.pop("t"))
    parts = [stamp, tool]
    for key in sorted(kept):
        parts.append(f"{key}={_render_value(kept[key])}")
    return " ".join(parts)


def _over(payload: bytes) -> bool:
    if not payload:
        return False
    if len(payload) >= MAX_BYTES:
        return True
    return len(payload.splitlines()) >= MAX_LINES


def _read(path: Path) -> bytes | None:
    if not path.is_file():
        return b""
    try:
        return path.read_bytes()
    except OSError:
        return None


def _can_append(debug_path: Path, events_path: Path) -> bool:
    debug_bytes = _read(debug_path)
    event_bytes = _read(events_path)
    if debug_bytes is None or event_bytes is None:
        return False
    if not (_over(debug_bytes) or _over(event_bytes)):
        return True
    for live in (debug_path, events_path):
        if not live.is_file():
            continue
        rotated = LOG_ROTATED if live.name == LOG_FILENAME else EVENTS_ROTATED
        try:
            os.replace(live, live.with_name(rotated))
        except OSError:
            return False
    return True


def _write_pair(debug_path: Path, events_path: Path, record: Mapping[str, object]) -> None:
    prose = render(record)
    raw = json.dumps(record, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(raw + "\n")
    with debug_path.open("a", encoding="utf-8") as handle:
        handle.write(prose + "\n")


def _land_record(essay_id: str) -> dict[str, object] | None:
    record = _store(
        {
            "t": _now(),
            "tool": LAND_TOOL,
            "essay_id": essay_id,
            "land": land_sha(),
        }
    )
    return record


def _append(folder: Path, record: dict[str, object], essay_id: str | None) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    debug_path = folder / LOG_FILENAME
    events_path = folder / ML_EVENTS_FILENAME
    if not _can_append(debug_path, events_path):
        return
    if essay_id and not events_path.is_file():
        land = _land_record(essay_id)
        if land is not None:
            _write_pair(debug_path, events_path, land)
    _write_pair(debug_path, events_path, record)


def emit(event: Mapping[str, object]) -> None:
    """Append one JSON line and one rendered line. Never raises."""
    try:
        if not debug_enabled():
            return
        if event.get("tool") == WIPE_TOOL:
            return
        payload = dict(event)
        payload["t"] = _now()
        record = _store(payload)
        if record is None:
            return
        essay_id = record.get("essay_id")
        found = essay_id if isinstance(essay_id, str) else None
        with _LOCK:
            _append(debug_log_path(found).parent, record, found)
    except Exception:
        return


def _json_lines(path: Path) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8")
    rows: list[dict[str, object]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def debug_tail(sequence: str | None = None, limit: int = TAIL_LIMIT) -> int:
    """Print recent rendered lines. Does not enable debug or create a file.

    A missing live file prints nothing and returns 0, including when only
    the rotated file is present. An unreadable file returns 1.
    """
    found = _essay_id(sequence) if isinstance(sequence, str) else None
    live = debug_log_path(found).parent / ML_EVENTS_FILENAME
    if not live.exists():
        return 0
    if not live.is_file():
        return 1
    try:
        rows = _json_lines(live)
    except (OSError, UnicodeError):
        return 1
    if len(rows) < limit:
        rotated = live.with_name(EVENTS_ROTATED)
        if rotated.is_file():
            try:
                older = _json_lines(rotated)
            except (OSError, UnicodeError):
                return 1
            need = limit - len(rows)
            rows = older[-need:] + rows
        window = rows
    else:
        window = rows[-limit:]
    for row in window:
        line = redact_text(render(row))
        if line:
            sys.stdout.write(line + "\n")
    return 0
