"""Opt-in run log for the shells.

Grok Bot, Cursor, and Grok Build read this file when they diagnose a run.
Students do not. The door reply does not mention it, and Word does not
contain it. It stays off until ESSAY_WRITER_DEBUG is set or the setup
record has debug true. A cloud-computer where does not turn it on.
"""

from __future__ import annotations

import functools
import hashlib
import inspect
import os
import re
import subprocess
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from essay_writer import paths as essay_paths
from essay_writer.confirm import refuse
from essay_writer.diary import _cover_stored_title, _real_title
from essay_writer.paths import (
    ESSAY_ID,
    SEQUENCE_ID,
    SETUP_DIRNAME,
    module_code,
    relative,
    sequence_number,
    work_dir,
    workspace_root,
)
from essay_writer.student_voice import speak

LOG_FILENAME = "debug.log"
ML_EVENTS_FILENAME = "ml-events.jsonl"
OPERATOR_LOG_FILENAMES = (LOG_FILENAME, ML_EVENTS_FILENAME)
DEBUG_ENV = "ESSAY_WRITER_DEBUG"
DEBUG_RECORD_KEY = "debug"
OPERATOR_E2E_ENV = "ESSAY_WRITER_OPERATOR_E2E"
OPERATOR_E2E_RECORD = "operator_e2e"
_LAND_SHA: str | None = None
_LAND_SHA_FILE = ".land-sha"

_ON = frozenset({"1", "true", "on", "yes"})
_OFF = frozenset({"0", "false", "off", "no"})
_SECRET_NAMES = frozenset(
    {
        "consensus_api_key",
        "unpaywall_email",
        "api_key",
        "apikey",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "password",
        "secret",
        "email",
        "bearer",
    }
)
_ENV_SECRETS = ("CONSENSUS_API_KEY", "ESSAY_WRITER_UNPAYWALL_EMAIL")
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_BEARER = re.compile(r"Bearer\s+\S+", re.IGNORECASE)
_TOKEN = re.compile(r"\b(?:sk|pk)[_-][A-Za-z0-9_\-]{8,}\b")
_DEBUG_WIPE_SPEECH = re.compile(
    r"^(?:please\s+)?(?:"
    r"delete\s+(?:the\s+)?(?:debug\s+)?logs?"
    r"|clear\s+(?:the\s+)?(?:debug\s+)?(?:run\s+)?logs?"
    r"|wipe\s+(?:the\s+)?(?:debug\s+)?(?:run\s+)?logs?"
    r"|clear\s+(?:the\s+)?debug\s+log"
    r"|delete\s+(?:the\s+)?debug\s+log"
    r"|wipe\s+(?:the\s+)?debug\s+log"
    r")\s*[.!]?$",
    re.IGNORECASE,
)
DEBUG_WIPE_TOOL = "essay.debug.wipe"
DEBUG_EXPORT_TOOL = "essay.debug.export"
EXPORT_FILENAME = "debug.zip"
SNAPSHOT_FILENAME = "health-land.json"
FERRY_FILENAME = "ferry.json"
# Chat paste truncates near this size. Zip members are never sliced to it.
CHAT_PASTE_CEILING = 32 * 1024
FERRY_ZIP_TIP = (
    "For a Cursor research run, use zip-for-ferry: call essay.debug.export "
    "and hand over that zip. Do not paste a truncated run log into chat."
)
EMPTY_EXPORT_REASON = "Nothing to export. The run logs are not on disk."
INCOMPLETE_EXPORT_REASON = "The export was incomplete. The zip was not kept."
COLLIDING_EXPORT_REASON = "The export names collided. The zip was not kept."
_KV_ESSAY = re.compile(r"\b(?:essay_id|sequence_id)=([A-Za-z0-9-]+)")
_JSON_ESSAY = re.compile(r'"(?:essay_id|sequence_id)"\s*:\s*"([^"]+)"')
_FOR_ESSAY = re.compile(r"\bfor ([A-Za-z0-9-]+)\b")
_KV_PACK = re.compile(r"\bpack_path=(\S+)")
_JSON_PACK = re.compile(r'"pack_path"\s*:\s*"([^"]+)"')
_PROSE_PACK = re.compile(r"Pack path ([^.]+)\.")


def _valid_log_essay_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()

    if ESSAY_ID.fullmatch(text) or SEQUENCE_ID.fullmatch(text):
        return text
    return None


def call_essay_id(
    arguments: dict[str, Any] | None = None,
    result: Any = None,
) -> str | None:
    """Sequence id for per-essay operator logs. None keeps the short install log."""
    args = arguments if isinstance(arguments, dict) else {}
    for key in ("essay_id", "sequence_id"):
        found = _valid_log_essay_id(args.get(key))
        if found:
            return found
    body = _body(result)
    if isinstance(body, dict):
        return _valid_log_essay_id(body.get("essay_id")) or _valid_log_essay_id(body.get("sequence_id"))
    return None


def debug_log_path(essay_id: str | None = None) -> Path:
    """debug.log in the app folder. Long runs use work_dir(essay_id); health stays global."""

    found = _valid_log_essay_id(essay_id) if essay_id is not None else None
    if found:
        return work_dir(found) / LOG_FILENAME
    return workspace_root() / LOG_FILENAME


def ml_events_path(essay_id: str | None = None) -> Path:
    """Structured ML JSONL. Per-sequence when essay_id is set; else the short install log."""

    found = _valid_log_essay_id(essay_id) if essay_id is not None else None
    if found:
        return work_dir(found) / ML_EVENTS_FILENAME
    return workspace_root() / ML_EVENTS_FILENAME


def _sequence_operator_log_paths() -> list[Path]:

    root = workspace_root()
    essay_root = root / SETUP_DIRNAME
    if not essay_root.is_dir():
        return []
    found: list[Path] = []
    for name in OPERATOR_LOG_FILENAMES:
        for path in essay_root.rglob(name):
            if path.is_file():
                found.append(path)
    return found


def operator_log_paths() -> tuple[Path, ...]:
    """App-folder operator logs FO wipe clears together (global and per-sequence)."""
    seen: set[Path] = set()
    ordered: list[Path] = []
    for path in (debug_log_path(), ml_events_path(), *_sequence_operator_log_paths()):
        key = path.resolve()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(path)
    return tuple(ordered)


def _export_archive_name(path: Path) -> str:

    if path.parent.resolve() == workspace_root().resolve():
        return path.name
    return relative(path)


def wipe_operator_log_files() -> dict[str, bool]:
    """Remove operator log files when present. Idempotent when a file is missing."""
    removed: dict[str, bool] = {LOG_FILENAME: False, ML_EVENTS_FILENAME: False}
    for path in operator_log_paths():
        if path.is_file():
            path.unlink()
            removed[path.name] = True
    return removed


def debug_log_wipe_speech(text: str) -> bool:
    """True when operator speech clearly means wipe the app-folder run log."""
    if not isinstance(text, str) or not text.strip():
        return False
    token = re.sub(r"\s+", " ", text).strip().strip(" .!\"'`")
    return bool(_DEBUG_WIPE_SPEECH.fullmatch(token))


def wipe_debug_log_file() -> bool:
    """Remove debug.log when it exists. Prefer wipe_operator_log_files for FO wipe."""
    return wipe_operator_log_files().get(LOG_FILENAME, False)


def _health_land_snapshot() -> bytes | None:
    """Short alive and land record. None when land is unknown or health is down."""
    land = land_sha()
    if not isinstance(land, str) or not land.strip() or land.strip().casefold() == "unknown":
        return None
    try:
        from essay_writer.health import essay_health

        health = essay_health()
    except Exception:
        return None
    if not isinstance(health, dict) or health.get("alive") is not True:
        return None
    import json

    payload = {"alive": True, "land": land.strip(), "tools": _tool_count()}
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def ferry_tip_sha() -> str:
    """Stable id for the zip-for-ferry tip. PR bodies cite this."""
    return hashlib.sha256(FERRY_ZIP_TIP.encode("utf-8")).hexdigest()[:12]


def _clean_export_token(value: str) -> str:
    return value.strip().strip("\"'").rstrip(".,;")


def _essay_ids_in_text(text: str) -> set[str]:
    found: set[str] = set()
    for pattern in (_KV_ESSAY, _JSON_ESSAY, _FOR_ESSAY):
        for match in pattern.finditer(text):
            valid = _valid_log_essay_id(_clean_export_token(match.group(1)))
            if valid:
                found.add(valid)
    return found


def _pack_paths_in_text(text: str) -> set[str]:
    found: set[str] = set()
    for pattern in (_KV_PACK, _JSON_PACK, _PROSE_PACK):
        for match in pattern.finditer(text):
            token = _clean_export_token(match.group(1))
            if not token or ".." in token or len(token) > 240:
                continue
            if "/" not in token and not token.endswith("pack.json"):
                continue
            found.add(token)
    return found


def _disk_pack_paths(essay_ids: set[str]) -> set[str]:

    found: set[str] = set()
    for essay_id in essay_ids:
        path = work_dir(essay_id) / "pack.json"
        try:
            if path.is_file():
                found.add(relative(path))
        except OSError:
            continue
    return found


def _health_run_ids() -> tuple[set[str], set[str]]:
    """Essay and pack ids already on the health record. Empty when health is down."""
    try:
        from essay_writer.health import essay_health

        health = essay_health()
    except Exception:
        return set(), set()
    if not isinstance(health, dict) or health.get("alive") is not True:
        return set(), set()
    essay_ids: set[str] = set()
    pack_paths: set[str] = set()
    for item in health.get("packs") or []:
        if not isinstance(item, dict):
            continue
        for key in ("essay_id", "sequence_id", "last_sequential_id"):
            valid = _valid_log_essay_id(item.get(key))
            if valid:
                essay_ids.add(valid)
    for item in health.get("local_packs") or []:
        if not isinstance(item, dict):
            continue
        valid = _valid_log_essay_id(item.get("essay_id"))
        if valid:
            essay_ids.add(valid)
        name = item.get("name")
        if isinstance(name, str):
            token = name.strip()
            if token and ".." not in token and len(token) <= 240:
                pack_paths.add(token)
    return essay_ids, pack_paths


def _ids_from_members(members: list[tuple[str, bytes]]) -> tuple[list[str], list[str]]:
    essay_ids: set[str] = set()
    pack_paths: set[str] = set()
    for name, payload in members:
        if name == SNAPSHOT_FILENAME:
            continue
        text = payload.decode("utf-8", errors="replace")
        essay_ids |= _essay_ids_in_text(text)
        pack_paths |= _pack_paths_in_text(text)
    health_ids, health_packs = _health_run_ids()
    essay_ids |= health_ids
    pack_paths |= health_packs
    pack_paths |= _disk_pack_paths(essay_ids)
    return sorted(essay_ids), sorted(pack_paths)


def _ferry_manifest(members: list[tuple[str, bytes]]) -> tuple[bytes, list[str], list[str]]:
    """Ids and member hashes. The manifest does not include its own bytes."""
    import json

    essay_ids, pack_paths = _ids_from_members(members)
    records = [
        {
            "bytes": len(payload),
            "name": name,
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        for name, payload in members
    ]
    body = {
        "chat_paste_ceiling": CHAT_PASTE_CEILING,
        "complete": True,
        "essay_ids": essay_ids,
        "ferry": "zip",
        "members": records,
        "pack_paths": pack_paths,
        "paste": False,
        "sliced": False,
    }
    raw = (json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return raw, essay_ids, pack_paths


def _write_debug_zip(path: Path, members: list[tuple[str, bytes]]) -> None:
    """Deflate every member whole. Callers verify the archive against these bytes."""
    import zipfile

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".zip.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, payload in members:
                archive.writestr(name, payload)
        os.replace(temporary, path)
    finally:
        if temporary.is_file():
            temporary.unlink()


def _zip_matches(path: Path, members: list[tuple[str, bytes]]) -> bool:
    """True when every stored member equals the bytes that were packed."""
    import zipfile

    try:
        with zipfile.ZipFile(path) as archive:
            if archive.namelist() != [name for name, _payload in members]:
                return False
            for name, payload in members:
                info = archive.getinfo(name)
                if info.file_size != len(payload):
                    return False
                if archive.read(name) != payload:
                    return False
    except (OSError, zipfile.BadZipFile, KeyError):
        return False
    return True


def essay_debug_export() -> dict[str, Any]:
    """Pack operator logs that are already on disk into one debug.zip.

    A missing log stays missing. The zip is refused when it would be empty.
    Members are deflated whole. They are not sliced to the chat paste ceiling.
    A zip that does not match those bytes is deleted and refused.
    Cursor, Grok Build, and the essay-writer CLI call this function.
    """

    members: list[tuple[str, bytes]] = []
    seen: set[str] = set()
    for path in operator_log_paths():
        if not path.is_file():
            continue
        name = _export_archive_name(path)
        if name in seen:
            return refuse("debug-export", COLLIDING_EXPORT_REASON)
        seen.add(name)
        try:
            payload = path.read_bytes()
        except OSError:
            return refuse("debug-export", "The export could not be written.")
        members.append((name, payload))
    snapshot = _health_land_snapshot()
    if snapshot:
        if SNAPSHOT_FILENAME in seen:
            return refuse("debug-export", COLLIDING_EXPORT_REASON)
        members.append((SNAPSHOT_FILENAME, snapshot))
    if not members:
        return refuse("debug-export", EMPTY_EXPORT_REASON)
    ferry, essay_ids, pack_paths = _ferry_manifest(members)
    if FERRY_FILENAME in {name for name, _payload in members}:
        return refuse("debug-export", COLLIDING_EXPORT_REASON)
    members.append((FERRY_FILENAME, ferry))
    dest = debug_log_path().parent / EXPORT_FILENAME
    try:
        _write_debug_zip(dest, members)
    except OSError:
        return refuse("debug-export", "The export could not be written.")
    if not _zip_matches(dest, members):
        try:
            if dest.is_file():
                dest.unlink()
        except OSError:
            pass
        return refuse("debug-export", INCOMPLETE_EXPORT_REASON)
    return speak(
        {
            "ok": True,
            "wrote": True,
            "name": EXPORT_FILENAME,
            "path": relative(dest),
            "entries": [name for name, _payload in members],
            "complete": True,
            "ferry": "zip",
            "paste": False,
            "sliced": False,
            "essay_ids": essay_ids,
            "pack_paths": pack_paths,
            "member_bytes": {name: len(payload) for name, payload in members},
            "ferry_tip": FERRY_ZIP_TIP,
            "ferry_tip_sha": ferry_tip_sha(),
            "next": "Exported the run logs.",
        }
    )


def essay_debug_wipe(speech: str | None = None) -> dict[str, Any]:
    """Wipe app-folder operator logs when speech matches. One path for every shell."""

    if not debug_log_wipe_speech(speech or ""):
        if not isinstance(speech, str) or not speech.strip():
            return refuse(
                "debug-wipe",
                "Say what you want cleared, such as delete the logs or clear debug log.",
            )
        return refuse("debug-wipe", "That request does not clear the run log.")
    removed = wipe_operator_log_files()
    cleared = any(removed.values())
    next_line = "Cleared the run logs." if cleared else "The run logs were already empty."
    return speak(
        {
            "ok": True,
            "wrote": cleared,
            "cleared": cleared,
            "cleared_debug": removed[LOG_FILENAME],
            "cleared_ml_events": removed[ML_EVENTS_FILENAME],
            "next": next_line,
        }
    )


def _flag_on(raw: str | None) -> bool:
    return isinstance(raw, str) and raw.strip().casefold() in _ON


def operator_debug_default() -> bool:
    """True when an operator end-to-end flag is on. A student install stays false.

    Setup `where` grokbot-cloud-computer does not turn the log on.
    `where` user-local does not either. ESSAY_WRITER_DEBUG and setup
    `debug` true are read in debug_enabled.
    """
    if _flag_on(os.environ.get(OPERATOR_E2E_ENV)):
        return True

    saved = essay_paths.load_saved_setup()
    if not isinstance(saved, dict):
        return False
    return saved.get(OPERATOR_E2E_RECORD) is True


def debug_enabled() -> bool:
    """Student installs stay off, including a cloud-computer save.

    An explicit off wins. An explicit on or setup `debug` true turns the
    log on. Setup `where` alone does not. The operator end-to-end flag does.
    """
    raw = os.environ.get(DEBUG_ENV)
    if raw is not None and raw.strip():
        folded = raw.strip().casefold()
        if folded in _ON:
            return True
        if folded in _OFF:
            return False
        return False
    if _setup_record_requests_debug():
        return True
    return operator_debug_default()


def record_requests_debug(record_path: Path) -> bool:
    """True when an operator already set debug on this setup record.

    essay.setup keeps that flag and does not repeat it in the reply.
    """
    if not record_path.is_file():
        return False
    try:
        import json

        data = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get(DEBUG_RECORD_KEY) is True


def _setup_record_requests_debug() -> bool:

    saved = essay_paths.load_saved_setup()
    return isinstance(saved, dict) and saved.get(DEBUG_RECORD_KEY) is True


def scrub(text: str, secrets: list[str] | None = None) -> str:
    """Drop keys, emails, and tokens. The rest of the line stays."""
    cleaned = text
    for secret in sorted({item for item in (secrets or []) if len(item) >= 8}, key=len, reverse=True):
        cleaned = cleaned.replace(secret, "[redacted]")
    cleaned = _BEARER.sub("[redacted]", cleaned)
    cleaned = _TOKEN.sub("[redacted]", cleaned)
    cleaned = _EMAIL.sub("[redacted]", cleaned)
    return cleaned


def _secret_values(arguments: dict[str, Any]) -> list[str]:
    found: list[str] = []

    def walk(key: object, value: object) -> None:
        if isinstance(value, dict):
            for child_key, child in value.items():
                walk(child_key, child)
            return
        if isinstance(value, list):
            for child in value:
                walk(key, child)
            return
        if isinstance(key, str) and key.casefold() in _SECRET_NAMES and isinstance(value, str):
            text = value.strip()
            if len(text) >= 8:
                found.append(text)

    for key, value in arguments.items():
        walk(key, value)
    for name in _ENV_SECRETS:
        raw = os.environ.get(name, "").strip()
        if len(raw) >= 8:
            found.append(raw)
    return found


def _clip(text: str, limit: int = 240) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def _body(result: Any) -> dict[str, Any] | None:
    if isinstance(result, dict):
        return result
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict):
                return item
    return None


def _present(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _install_root() -> Path:
    """Package install root (repo root in dev, site root when installed)."""
    return Path(__file__).resolve().parents[2]


def _land_sha_from_file() -> str:
    """Pinned land SHA written at ship time. Empty when the file is missing."""
    pkg = Path(__file__).resolve().parent
    candidates = (
        _install_root() / _LAND_SHA_FILE,
        pkg / _LAND_SHA_FILE,
        pkg.parent / _LAND_SHA_FILE,
    )
    for path in candidates:
        if not path.is_file():
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        line = raw.strip().splitlines()[0].strip() if raw.strip() else ""
        if line and line.casefold() != "unknown":
            return line
    return ""


def _land_sha_from_git() -> str:
    root = _install_root()
    try:
        raw = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return raw.decode("utf-8", errors="replace").strip()


def land_sha() -> str:
    """Land SHA for operator logs. `.land-sha` wins over git when present."""
    global _LAND_SHA
    if _LAND_SHA:
        return _LAND_SHA
    pinned = _land_sha_from_file()
    if pinned:
        _LAND_SHA = pinned
        return _LAND_SHA
    found = _land_sha_from_git()
    _LAND_SHA = found or "unknown"
    return _LAND_SHA


def _land_sha() -> str:
    return land_sha()


def _known_land() -> str | None:
    """Land SHA when install, package pin, or git provides one."""
    found = land_sha()
    if isinstance(found, str) and found.strip() and found.casefold() != "unknown":
        return found.strip()
    return None


def _sequence_trail_header_line(essay_id: str) -> str:
    when = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    land = land_sha()
    return f"{when} essay-writer.land land={land} essay_id={essay_id.strip()} trail=open"


def _prepare_sequence_debug_log(path: Path, essay_id: str | None) -> None:
    if essay_id is None or path.is_file():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_sequence_trail_header_line(essay_id) + "\n", encoding="utf-8")


def _tool_count() -> int:
    from essay_writer.doors import DOORS

    return len(DOORS)


def _text_or_none(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "none"


def _posted_digest(body: dict[str, Any] | None) -> str:
    if not isinstance(body, dict):
        return "none"
    card = body.get("card")
    if not isinstance(card, dict):
        return "none"
    for key in ("digest", "cardDigest"):
        found = _text_or_none(card.get(key))
        if found != "none":
            return found
    return "none"


def _file_stamp(path: Path, display: str) -> str:
    if not path.is_file():
        return f"{display} missing"
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        mtime = path.stat().st_mtime_ns
    except OSError:
        return f"{display} missing"
    return f"{display} mtime {mtime} sha {digest}"


_PRODUCT_TOOLS = frozenset(
    {
        "essay.stage",
        "essay.sequence.new",
        "essay.pack.validate",
        "essay.pack.render_word",
        "essay.review",
        "mid-office",
    }
)


def _kv_token(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    text = str(value).strip()
    if not text:
        return ""
    if any(ch.isspace() for ch in text) or "=" in text:
        return '"' + text.replace('"', "'") + '"'
    return text


def _cover_audit_fields(essay_id: str, cover: list[str] | None) -> dict[str, int]:
    if not isinstance(cover, list):
        return {
            "cover_n": 0,
            "cover_sequence_id": 0,
            "cover_title_line": 0,
            "cover_counted_words": 0,
        }
    from essay_writer.programme import PROGRAMME

    programme = {str(value).casefold() for value in PROGRAMME.values()}
    has_sequence = 1 if essay_id in cover else 0
    has_title = 0
    has_counted = 0
    for line in cover:
        text = line.strip()
        if not text:
            continue
        if text.startswith("Counted words:"):
            has_counted = 1
        if text == essay_id:
            has_sequence = 1
        if text.casefold() not in programme and not text.startswith("Counted words:"):
            if text not in {"Conclusion: noted", "Conclusion: open — not a settled finding"}:
                if not text.startswith("Registration number:") and ":" not in text[-3:]:
                    has_title = 1
    return {
        "cover_n": len(cover),
        "cover_sequence_id": has_sequence,
        "cover_title_line": has_title,
        "cover_counted_words": has_counted,
    }


def _write_product_kv_lines(event: str, essay_id: str, facts: dict[str, object]) -> None:
    """One fact per line for LLM grep. Never raises."""
    if not debug_enabled():
        return
    if not isinstance(essay_id, str) or not essay_id.strip():
        return
    if not facts:
        return
    try:
        when = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        found = _valid_log_essay_id(essay_id.strip())
        path = debug_log_path(found)
        path.parent.mkdir(parents=True, exist_ok=True)
        base = (
            f"t={when} event={event} essay_id={_kv_token(essay_id.strip())}"
        )
        with path.open("a", encoding="utf-8") as handle:
            for key, value in facts.items():
                if value is None:
                    continue
                token = _kv_token(value)
                if not token and value != 0:
                    continue
                handle.write(scrub(f"{base} {key}={token}", []) + "\n")
    except Exception:
        return


def _product_tool_extras(
    tool: str, arguments: dict[str, Any], body: dict[str, Any] | None
) -> list[str]:
    if tool not in _PRODUCT_TOOLS:
        return []
    extras: list[str] = []
    essay_id = arguments.get("essay_id")
    if not isinstance(essay_id, str) or not essay_id.strip():
        if isinstance(body, dict) and isinstance(body.get("essay_id"), str):
            essay_id = body["essay_id"]
    essay_id = essay_id.strip() if isinstance(essay_id, str) else ""
    stage = arguments.get("stage")
    if not isinstance(stage, str) and isinstance(body, dict):
        stage = body.get("stage")
    if isinstance(stage, str) and stage.strip():
        extras.append(f"Stage {stage.strip()}.")
    if tool == "essay.sequence.new" and isinstance(arguments.get("parent"), str):
        extras.append(f"Parent {arguments['parent'].strip()}.")
    if isinstance(body, dict):
        saved = body.get("saved_pack_state")
        if isinstance(saved, str) and saved.strip():
            extras.append(f"saved_pack {saved.strip()}.")
        if body.get("chain_armed") is True:
            extras.append("Chain armed.")
        pack_path = body.get("pack_path")
        if isinstance(pack_path, str) and pack_path.strip():
            extras.append(f"Pack path {pack_path.strip()}.")
        references = body.get("references")
        if isinstance(references, list):
            extras.append(f"refs_n={len(references)}")
        sources = body.get("sources")
        if isinstance(sources, list):
            extras.append(f"sources_n={len(sources)}")
        output = body.get("output_path")
        if isinstance(output, str) and output.strip():
            extras.append(_file_stamp(Path(output.strip()), output.strip()))
        if body.get("ok") is False:
            refused = body.get("refused")
            reason = body.get("reason")
            if isinstance(refused, str) and refused.strip():
                extras.append(f"Refused {refused.strip()}.")
            if isinstance(reason, str) and reason.strip():
                extras.append(f"Reason {_clip(reason.strip(), 160)}.")
    return extras


def pack_log_title(pack: dict[str, Any]) -> str:
    """Cover-facing title for operator logs. Draft is not logged as the title."""

    text = _cover_stored_title(pack.get("assessment")) or _cover_stored_title(
        pack.get("title")
    )
    return text or "empty"


def pack_log_assessment(pack: dict[str, Any]) -> str:

    text = _real_title(pack.get("assessment"))
    return text or "empty"


def log_word_step(
    step: str,
    essay_id: str,
    *,
    stage: str | None = None,
    pack_path: str | None = None,
    saved_pack: str | None = None,
    title: str | None = None,
    assessment: str | None = None,
    conclusion: str | None = None,
    cover: list[str] | None = None,
    sources_count: int | None = None,
    refs_count: int | None = None,
    refs_from: str | None = None,
    output_path: Path | str | None = None,
    refused: str | None = None,
    reason: str | None = None,
) -> None:
    """Word rebuild facts for Grok Bot and Cursor. One key=value per debug.log line."""
    if not isinstance(essay_id, str) or not essay_id.strip():
        return
    event = f"essay.product.{step}"
    facts: dict[str, object] = {}
    if stage:
        facts["stage"] = stage
    if pack_path:
        facts["pack_path"] = pack_path
    if saved_pack:
        facts["saved_pack"] = saved_pack
    if title is not None:
        facts["title"] = title or "empty"
    if assessment is not None:
        facts["assessment"] = assessment or "empty"
    if conclusion is not None:
        facts["conclusion"] = conclusion or "empty"
    if cover is not None:
        facts.update(_cover_audit_fields(essay_id.strip(), cover))
    if sources_count is not None:
        facts["sources_n"] = sources_count
    if refs_count is not None:
        facts["refs_n"] = refs_count
    if refs_from:
        facts["refs_from"] = refs_from
    if output_path is not None:
        path = Path(output_path)
        if path.is_file():
            try:
                facts["sha"] = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                pass
    if refused:
        facts["refuse"] = refused
    if reason:
        facts["reason"] = _clip(reason, 160)
    _write_product_kv_lines(event, essay_id.strip(), facts)


def note_product_trace(event: str, essay_id: str, **fields: Any) -> None:
    """Operator-only trace for Word and stage paths. Never raises into the door."""
    log_word_step(event, essay_id, **fields)


def _emit_door_product_facts(
    tool: str, arguments: dict[str, Any], body: dict[str, Any] | None
) -> None:
    """Key=value lines for product doors. One fact per line."""
    if tool not in _PRODUCT_TOOLS:
        return
    essay_id = arguments.get("essay_id")
    if not isinstance(essay_id, str) or not essay_id.strip():
        if isinstance(body, dict) and isinstance(body.get("essay_id"), str):
            essay_id = body["essay_id"]
    if not isinstance(essay_id, str) or not essay_id.strip():
        return
    phase = arguments.get("confirmPhase")
    if not isinstance(phase, str):
        phase = None
    stage = arguments.get("stage")
    if not isinstance(stage, str) and isinstance(body, dict):
        stage = body.get("stage")
    facts: dict[str, object] = {"tool": tool}
    if phase in {"draft", "confirm"}:
        facts["phase"] = phase
    if isinstance(stage, str) and stage.strip():
        facts["stage"] = stage.strip()
    if tool == "essay.sequence.new" and isinstance(arguments.get("parent"), str):
        facts["parent"] = arguments["parent"].strip()
    if not isinstance(body, dict):
        _write_product_kv_lines(f"essay.door.{tool}", essay_id.strip(), facts)
        return
    if isinstance(body.get("saved_pack_state"), str):
        facts["saved_pack"] = body["saved_pack_state"]
    if isinstance(body.get("pack_path"), str):
        facts["pack_path"] = body["pack_path"]
    if body.get("chain_armed") is True:
        facts["chain_armed"] = 1
    cover = body.get("cover")
    if isinstance(cover, list):
        facts.update(_cover_audit_fields(essay_id.strip(), cover))
    if isinstance(body.get("references"), list):
        facts["refs_n"] = len(body["references"])
    if isinstance(body.get("sources"), list):
        facts["sources_n"] = len(body["sources"])
    if body.get("ok") is False and isinstance(body.get("refused"), str):
        facts["refuse"] = body["refused"]
    if body.get("ok") is False and isinstance(body.get("reason"), str):
        facts["reason"] = _clip(body["reason"], 160)
    if body.get("stored") is True:
        facts["stored"] = 1
    if body.get("advanced") is True:
        facts["advanced"] = 1
    _write_product_kv_lines(f"essay.door.{tool}", essay_id.strip(), facts)


def _stage10_stamp(arguments: dict[str, Any], body: dict[str, Any] | None) -> str:
    essay_id = arguments.get("essay_id")
    if not isinstance(essay_id, str) or not essay_id.strip():
        found = body.get("essay_id") if isinstance(body, dict) else None
        essay_id = found if isinstance(found, str) else ""
    essay_id = essay_id.strip()
    if not essay_id:
        return "Sequence output missing. Documents unmounted."
    from essay_writer.late_chain import documents_root, final_place

    module = module_code(essay_id)
    number = sequence_number(essay_id)
    if number is None:
        display = f"Essay-writer/{module}/output/{essay_id}.docx"
    else:
        display = f"Essay-writer/{module}/sequences/{number}/output/{essay_id}.docx"
    sequence = _file_stamp(work_dir(essay_id) / "output" / f"{essay_id}.docx", display)
    from essay_writer.first_run import sequence_mac_deliverables_dir

    seq_mac = sequence_mac_deliverables_dir(essay_id)
    root = documents_root()
    if seq_mac is not None:
        documents = _file_stamp(seq_mac / f"{module}-final.docx", final_place(essay_id))
    elif root is None:
        documents = "unmounted"
    else:
        documents = _file_stamp(root / f"{module}-10" / f"{module}-final.docx", final_place(essay_id))
    return f"Sequence output {sequence}. Documents {documents}."


def _confirm_spine(tool: str, body: dict[str, Any] | None) -> list[str]:
    """Card digest beside the card that would be posted, plus the atomic confirm line."""
    tool_digest = _text_or_none(body.get("cardDigest") if isinstance(body, dict) else None)
    posted = _posted_digest(body)
    card_field = isinstance(body, dict) and isinstance(body.get("card"), dict)
    lines = [
        f"Card digest {tool_digest}.",
        "Card present." if card_field else "Card absent.",
        f"Posted {posted}.",
    ]
    if tool == "essay.stage":
        stored = "yes" if isinstance(body, dict) and body.get("stored") is True else "no"
        advanced = "yes" if isinstance(body, dict) and body.get("advanced") is True else "no"
        lines.append(f"Confirm store {stored} advance {advanced} next-card {tool_digest}.")
    return lines


def _start_launch_fields(stage: str) -> dict[str, Any]:
    """Stage settings for a start row. Prompt text stays off the log."""
    from essay_writer.stage_llm import stage_settings

    try:
        item = stage_settings(stage)
    except KeyError:
        return {}
    return {
        "stage": item["stage"],
        "model": item["model"],
        "reasoning": item["reasoning"],
        "fast": item["fast"],
        "context_window": item["context_window"],
    }


_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _short_cli_line(text: str, limit: int = 160) -> str:
    """One short CLI outcome line. The tail is kept when the text is long."""
    cleaned = _ANSI.sub("", text)
    cleaned = "".join(ch if ch.isprintable() else " " for ch in cleaned)
    cleaned = " ".join(cleaned.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[-limit:]


def note_mid_office(
    event: str,
    essay_id: str,
    shell: str,
    *,
    reason: str = "",
    exit_code: int | None = None,
    stage: str | None = None,
    stderr_line: str = "",
) -> None:
    """One start, done, or exit line. Unknown events and shells are not written."""
    if event not in {"start", "done", "exit"} or shell not in {"Cursor", "Build"}:
        return
    if not isinstance(essay_id, str) or not essay_id.strip():
        return
    payload: dict[str, Any] = {"ok": True, "wrote": False, "mid_office": event, "mid_shell": shell}
    if event == "start" and isinstance(stage, str) and stage.strip():
        payload.update(_start_launch_fields(stage.strip()))
    if isinstance(reason, str) and reason.strip():
        payload["mid_exit_reason"] = reason.strip()
    if exit_code is not None and not isinstance(exit_code, bool):
        payload["mid_exit_code"] = int(exit_code)
    if isinstance(stderr_line, str) and stderr_line.strip():
        short = _short_cli_line(stderr_line)
        if short:
            payload["mid_stderr"] = short
    note_call(
        "mid-office",
        {"essay_id": essay_id.strip(), "confirmPhase": event},
        result=payload,
    )


def _format(tool: str, arguments: dict[str, Any], result: Any, error: BaseException | None) -> str:
    phase = arguments.get("confirmPhase")
    phase_text = phase if phase in {"draft", "confirm"} else "read"
    target = ""
    for key in ("essay_id", "module", "sequence_id"):
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            target = value.strip()
            break
    body = _body(result)
    if error is not None:
        outcome = f"Failed ({type(error).__name__}). {_clip(str(error))}"
    elif body is None:
        outcome = "Finished."
    elif body.get("ok") is False:
        code = body.get("refused") if isinstance(body.get("refused"), str) else "refused"
        reason_raw = body.get("reason")
        reason = reason_raw if isinstance(reason_raw, str) else ""
        outcome = f"Refused ({code}). {_clip(reason)} Nothing written."
    elif body.get("wrote") is True:
        outcome = "Ready. Wrote."
    elif body.get("wrote") is False:
        outcome = "Ready. Nothing written."
    else:
        outcome = "Ready."

    extras: list[str] = []
    where = body.get("where") if body and isinstance(body.get("where"), str) else None
    if where is None and isinstance(arguments.get("where"), str) and arguments["where"].strip():
        where = arguments["where"].strip()
    if isinstance(where, str) and where.strip():
        extras.append(f"Where {where.strip()}.")
    if body and body.get("deleted") is True:
        extras.append("Removed the workspace.")
    if body and body.get("deleted_local") is True:
        extras.append("Removed the named copies.")
    if body and isinstance(body.get("sequences"), list):
        extras.append(f"Sequences {len(body['sequences'])}.")
    if body and isinstance(body.get("local"), list):
        extras.append(f"Local files {len(body['local'])}.")
    consensus = body.get("consensus") if body else None
    reported_key = isinstance(consensus, dict) and "key_present" in consensus
    if isinstance(consensus, dict):
        if consensus.get("enabled") is True:
            extras.append("Consensus on.")
        elif consensus.get("enabled") is False:
            extras.append("Consensus off.")
        if consensus.get("key_present") is True:
            extras.append("Consensus key present.")
        elif consensus.get("key_present") is False:
            extras.append("Consensus key absent.")
    if "consensus_api_key" in arguments and not reported_key:
        extras.append(
            "Consensus key present." if _present(arguments.get("consensus_api_key")) else "Consensus key absent."
        )
    if "unpaywall_email" in arguments:
        extras.append(
            "Unpaywall email present." if _present(arguments.get("unpaywall_email")) else "Unpaywall email absent."
        )
    query = arguments.get("query")
    if isinstance(query, str) and query.strip():
        extras.append(f"Query {_clip(query.strip(), 80)}.")
    if body and isinstance(body.get("digest"), str) and body["digest"]:
        extras.append(f"Digest {body['digest']}.")
    if tool in {"essay.sequence.new", "essay.stage"} and phase_text == "confirm":
        extras.extend(_confirm_spine(tool, body))
    if tool == "essay.health":
        extras.append(f"Land {_land_sha()} pid {os.getpid()} tools {_tool_count()}.")
    stage = arguments.get("stage")
    if (
        tool == "essay.stage"
        and phase_text == "confirm"
        and isinstance(stage, str)
        and stage == "10"
    ):
        extras.append(_stage10_stamp(arguments, body))
    if (
        body
        and body.get("mid_office") in {"start", "done", "exit"}
        and body.get("mid_shell") in {"Cursor", "Build"}
    ):
        extras.append(f"Mid-office {body['mid_office']} {body['mid_shell']}.")
        exit_reason = body.get("mid_exit_reason")
        if isinstance(exit_reason, str) and exit_reason.strip():
            extras.append(f"Exit {_clip(exit_reason.strip())}.")
        if "mid_exit_code" in body:
            extras.append(f"Code {body['mid_exit_code']}.")
        cli_line = body.get("mid_stderr")
        if isinstance(cli_line, str) and cli_line.strip():
            extras.append(f"Stderr {_clip(cli_line.strip(), 160)}.")
    extras.extend(_product_tool_extras(tool, arguments, body))
    when = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    head = f"{when} {tool} {phase_text}"
    if target:
        head = f"{head} for {target}"
    return f"{head}. {outcome} {' '.join(extras)}".rstrip()


def note_call(
    tool: str,
    arguments: dict[str, Any] | None = None,
    result: Any = None,
    error: BaseException | None = None,
) -> None:
    """Append one door line and the structured events when the log is on.

    Never raises into the door. essay.debug.wipe writes nothing, so a wipe
    does not recreate either file.
    """
    if tool == DEBUG_WIPE_TOOL:
        return
    if not debug_enabled():
        return
    args = arguments if isinstance(arguments, dict) else {}
    try:
        line = scrub(_format(tool, args, result, error), _secret_values(args))
        line = " ".join(line.split())
        if line:
            essay_id = call_essay_id(args, result)
            path = debug_log_path(essay_id)
            _prepare_sequence_debug_log(path, essay_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
    except Exception:
        pass
    try:
        from essay_writer.ml_events import note_events

        note_events(tool, args, result=result, error=error)
    except Exception:
        return
    try:
        _emit_door_product_facts(tool, args, _body(result))
    except Exception:
        return


def _bound(handler: Callable[..., object], args: tuple[object, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    try:
        bound = inspect.signature(handler).bind_partial(*args, **kwargs)
    except TypeError:
        return dict(kwargs)
    return dict(bound.arguments)


def traced(tool: str, handler: Callable[..., object]) -> Callable[..., object]:
    """Call a mounted door and write one line. The original signature stays."""

    @functools.wraps(handler)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        arguments = _bound(handler, args, kwargs)
        try:
            result = handler(*args, **kwargs)
        except Exception as exc:
            note_call(tool, arguments, error=exc)
            raise
        note_call(tool, arguments, result=result)
        return result

    return wrapper
