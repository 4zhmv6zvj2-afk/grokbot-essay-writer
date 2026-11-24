"""Always-on metadata for a refusal, an exception, a fallback, or a repair.

One JSON line in the app folder. The line has a code, a severity, and a
disposition. It does not have essay text, a prompt, a chat, a file body, a
path, or a secret. Debug logs stay on their own opt-in stream.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
import os
import re
import threading
import zipfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FILENAME = "incident.jsonl"
ROTATED_NAME = "incident.jsonl.1"
BUNDLE_NAME = "support.zip"
MODE = 0o600
MAX_LINES = 200
MAX_BYTES = 256 * 1024
# Exact exception text only. A free-form message is dropped. Redaction does
# not make essay or prompt text safe to store.
ALLOWED_MESSAGES = frozenset({"Windows is not supported."})
UNHANDLED = "unhandled"

_SEVERITY = frozenset({"warn", "info", "error"})
_DISPOSITION = frozenset({"retry", "fallback", "refuse"})
_CODE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_TOKEN = re.compile(r"^[a-z0-9._-]+$")
_STEP = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,31}$")
_STAGE = re.compile(r"^[0-9]{1,2}[a-z]?$")
_CLASS = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_LOCK = threading.Lock()
_CACHE: dict[str, str] = {}
_FRAME: contextvars.ContextVar[_Frame | None] = contextvars.ContextVar(
    "essay_writer_incident_frame",
    default=None,
)


class _Frame:
    def __init__(self, tool: str, sequence: str, stage: str) -> None:
        self.tool = tool
        self.sequence = sequence
        self.stage = stage
        self.seen: set[str] = set()


def incident_path() -> Path:
    from essay_writer.paths import workspace_root

    return workspace_root() / FILENAME


def rotated_path() -> Path:
    return incident_path().with_name(ROTATED_NAME)


@contextmanager
def call_frame(tool: str, arguments: Mapping[str, Any] | None) -> Iterator[None]:
    """One door call. The same code is written once inside this frame."""
    args = dict(arguments) if isinstance(arguments, Mapping) else {}
    frame = _Frame(tool if _TOKEN.fullmatch(tool) else "", _sequence(args), _stage_of(args))
    token = _FRAME.set(frame)
    try:
        yield
    finally:
        _FRAME.reset(token)


def note(
    code: str,
    *,
    severity: str,
    disposition: str,
    tool: str = "",
    step: str = "",
    exc: str = "",
    message: str = "",
    sequence: str = "",
) -> None:
    """Append one metadata line. A logging failure does not stop the student."""
    try:
        if severity not in _SEVERITY or disposition not in _DISPOSITION:
            return
        if not isinstance(code, str) or _CODE.fullmatch(code) is None:
            return
        frame = _FRAME.get()
        if frame is not None and code in frame.seen:
            return
        tool = _token(tool) or (frame.tool if frame is not None else "")
        step = _step(step) or (frame.stage if frame is not None else "")
        sequence = _kept_sequence(sequence) or (frame.sequence if frame is not None else "")
        if message not in ALLOWED_MESSAGES:
            message = ""
        if not isinstance(exc, str) or _CLASS.fullmatch(exc) is None:
            exc = ""
        payload = {
            "build": _build(),
            "code": code,
            "disposition": disposition,
            "exc": exc,
            "message": message,
            "prompt": _prompt(),
            "sequence": sequence,
            "severity": severity,
            "stage": step,
            "time": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "tool": tool,
        }
        line = json.dumps(payload, sort_keys=True) + "\n"
        wrote = _commit(line, code, tool, dedupe_file=frame is None)
        if wrote and frame is not None:
            frame.seen.add(code)
    except Exception:
        return


def note_exception(exc: BaseException) -> None:
    """Record the class and a stable code. The message is stored only when allowlisted."""
    try:
        raw = str(exc)
        name = type(exc).__name__
        note(
            UNHANDLED,
            severity="error",
            disposition="refuse",
            exc=name if _CLASS.fullmatch(name) else "Exception",
            message=raw if raw in ALLOWED_MESSAGES else "",
        )
    except Exception:
        return


def wipe_incident_files() -> bool:
    """Remove the live record and the rotated file. Missing files stay missing."""
    removed = False
    try:
        with _LOCK:
            root = incident_path().parent
            for name in (FILENAME, ROTATED_NAME):
                path = root / name
                try:
                    if path.is_file():
                        path.unlink()
                        removed = True
                except OSError:
                    pass
    except Exception:
        return removed
    return removed


def locked_incident_files() -> list[tuple[str, bytes]]:
    """Live and rotated records. The lock covers the read."""
    with _LOCK:
        return _read_pair()


def pack_support_zip(
    dest: Path,
    incident_members: list[tuple[str, bytes]],
    extra: list[tuple[str, bytes]],
) -> list[str]:
    """Zip the incident members, health, file hashes, extras, and the manifest."""
    counts, severity, soft = _counts([payload for _name, payload in incident_members])
    health = json.dumps(_health(), sort_keys=True).encode("utf-8") + b"\n"
    files = json.dumps(_file_hashes(), sort_keys=True).encode("utf-8") + b"\n"
    members: list[tuple[str, bytes]] = [
        *incident_members,
        ("health.json", health),
        ("files.json", files),
        *extra,
    ]
    manifest = {
        "counts": counts,
        "members": [name for name, _payload in members] + ["manifest.json"],
        "severity": severity,
        "soft": soft,
    }
    encoded = json.dumps(manifest, sort_keys=True).encode("utf-8") + b"\n"
    members.append(("manifest.json", encoded))
    _write_zip(dest, members)
    return [name for name, _payload in members]


def _commit(line: str, code: str, tool: str, *, dedupe_file: bool) -> bool:
    with _LOCK:
        path = incident_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_bytes() if path.is_file() else b""
        if dedupe_file and _last_matches(existing, code, tool):
            return False
        if _over_cap(existing):
            rotated = path.with_name(ROTATED_NAME)
            os.replace(path, rotated)
            try:
                os.chmod(rotated, MODE)
            except OSError:
                pass
        _append_bytes(path, line.encode("utf-8"))
        return True


def _over_cap(existing: bytes) -> bool:
    if not existing:
        return False
    if len(existing) >= MAX_BYTES:
        return True
    return len(existing.splitlines()) >= MAX_LINES


def _last_matches(existing: bytes, code: str, tool: str) -> bool:
    """A damaged last line is not a reason to drop the new one."""
    try:
        lines = existing.decode("utf-8").splitlines()
        if not lines:
            return False
        last = json.loads(lines[-1])
    except (UnicodeError, json.JSONDecodeError):
        return False
    return isinstance(last, dict) and last.get("code") == code and last.get("tool") == tool


def _append_bytes(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, MODE)
    try:
        try:
            os.fchmod(fd, MODE)
        except OSError:
            pass
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short write")
            view = view[written:]
    finally:
        os.close(fd)


def _read_pair() -> list[tuple[str, bytes]]:
    found: list[tuple[str, bytes]] = []
    for name, path in ((FILENAME, incident_path()), (ROTATED_NAME, rotated_path())):
        try:
            if path.is_file():
                found.append((name, path.read_bytes()))
        except OSError:
            continue
    return found


def _counts(blobs: list[bytes]) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    counts: dict[str, int] = {}
    severity = {"error": 0, "info": 0, "warn": 0}
    soft: dict[str, int] = {}
    for blob in blobs:
        for line in blob.decode("utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            code = row.get("code")
            level = row.get("severity")
            if not isinstance(code, str):
                continue
            counts[code] = counts.get(code, 0) + 1
            if level in severity:
                severity[level] += 1
            if level in {"info", "warn"}:
                soft[code] = soft.get(code, 0) + 1
    return counts, severity, soft


def _health() -> dict[str, Any]:
    from essay_writer import __version__
    from essay_writer.doors import DOORS

    return {
        "build": _build(),
        "doors": [door["tool"] for door in DOORS if isinstance(door.get("tool"), str)],
        "prompt": _prompt(),
        "version": __version__,
    }


def _file_hashes() -> list[dict[str, str]]:
    from essay_writer.paths import ESSAY_ID, SETUP_DIRNAME, workspace_root

    root = workspace_root() / SETUP_DIRNAME
    found: list[tuple[float, dict[str, str]]] = []
    if not root.is_dir():
        return []
    try:
        modules = list(root.iterdir())
    except OSError:
        return []
    for module in modules:
        if not module.is_dir() or ESSAY_ID.fullmatch(module.name) is None:
            continue
        states = [module / "state.json"]
        seq_root = module / "sequences"
        if seq_root.is_dir():
            try:
                numbers = list(seq_root.iterdir())
            except OSError:
                numbers = []
            for number in numbers:
                if number.is_dir() and number.name.isdigit():
                    states.append(number / "state.json")
        for state in states:
            row = _hash_row(module.name, state)
            if row is None:
                continue
            found.append(row)
    found.sort(key=lambda item: item[0], reverse=True)
    return [row for _mtime, row in found[:5]]


def _hash_row(module: str, state: Path) -> tuple[float, dict[str, str]] | None:
    if not state.is_file():
        return None
    try:
        data = state.read_bytes()
        mtime = state.stat().st_mtime
    except OSError:
        return None
    if state.parent.name == module:
        sequence = module
        pointer = state.parent / "tracking" / "stage.json"
    else:
        sequence = f"{module}-{state.parent.name}"
        pointer = state.parent / "tracking" / "stage.json"
    row = {"sequence": sequence, "state_sha256": hashlib.sha256(data).hexdigest()}
    try:
        if pointer.is_file():
            row["pointer_sha256"] = hashlib.sha256(pointer.read_bytes()).hexdigest()
    except OSError:
        pass
    return mtime, row


def _write_zip(dest: Path, members: list[tuple[str, bytes]]) -> None:
    partial = dest.with_name(dest.name + ".partial")
    try:
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, payload in members:
                archive.writestr(name, payload)
        os.replace(partial, dest)
    except Exception:
        try:
            if partial.is_file():
                partial.unlink()
        except OSError:
            pass
        raise


def _build() -> str:
    if "build" not in _CACHE:
        try:
            _CACHE["build"] = _read_build()
        except Exception:
            _CACHE["build"] = ""
    return _CACHE["build"]


def _read_build() -> str:
    from essay_writer import build_commit

    value = build_commit()
    return value if isinstance(value, str) else ""


def _prompt() -> str:
    if "prompt" not in _CACHE:
        try:
            _CACHE["prompt"] = _prompt_digest()
        except Exception:
            _CACHE["prompt"] = ""
    return _CACHE["prompt"]


def _prompt_digest() -> str:
    root = Path(__file__).resolve().parent / "prompts"
    if not root.is_dir():
        return ""
    hasher = hashlib.sha256()
    paths = sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix in {".md", ".json", ".toml"}
        and "__pycache__" not in path.parts
    )
    for path in paths:
        hasher.update(path.relative_to(root).as_posix().encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()[:12]


def _sequence(arguments: dict[str, Any]) -> str:
    from essay_writer.paths import ESSAY_ID, SEQUENCE_ID

    for key in ("sequence_id", "essay_id"):
        value = arguments.get(key)
        if isinstance(value, str) and (
            SEQUENCE_ID.fullmatch(value.strip()) or ESSAY_ID.fullmatch(value.strip())
        ):
            return value.strip()
    return ""


def _kept_sequence(value: str) -> str:
    from essay_writer.paths import ESSAY_ID, SEQUENCE_ID

    if not isinstance(value, str):
        return ""
    text = value.strip()
    if SEQUENCE_ID.fullmatch(text) or ESSAY_ID.fullmatch(text):
        return text
    return ""


def _stage_of(arguments: dict[str, Any]) -> str:
    for key in ("stage", "phase"):
        value = arguments.get(key)
        if isinstance(value, str) and _STAGE.fullmatch(value.strip()):
            return value.strip()
    return ""


def _token(value: str) -> str:
    if isinstance(value, str) and _TOKEN.fullmatch(value):
        return value
    return ""


def _step(value: str) -> str:
    if isinstance(value, str) and _STEP.fullmatch(value):
        return value
    return ""
