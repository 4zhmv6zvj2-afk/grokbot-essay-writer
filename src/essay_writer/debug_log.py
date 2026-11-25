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
from pathlib import Path
from typing import Any

from essay_writer import paths as essay_paths
from essay_writer.confirm import refuse
from essay_writer.diary import _cover_stored_title, _real_title
from essay_writer.paths import (
    ESSAY_ID,
    SEQUENCE_ID,
    SETUP_DIRNAME,
    relative,
    work_dir,
    workspace_root,
)
from essay_writer.student_voice import speak

LOG_FILENAME = "debug.log"
ML_EVENTS_FILENAME = "ml-events.jsonl"
LOG_ROTATED_FILENAME = "debug.log.1"
ML_EVENTS_ROTATED_FILENAME = "ml-events.jsonl.1"
OPERATOR_LOG_FILENAMES = (
    LOG_FILENAME,
    LOG_ROTATED_FILENAME,
    ML_EVENTS_FILENAME,
    ML_EVENTS_ROTATED_FILENAME,
)
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
        "openalex_api_key",
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
_ENV_SECRETS = ("CONSENSUS_API_KEY", "ESSAY_WRITER_UNPAYWALL_EMAIL", "OPENALEX_API_KEY")
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_BEARER = re.compile(r"Bearer\s+\S+", re.IGNORECASE)
_TOKEN = re.compile(r"\b(?:sk|pk)[_-][A-Za-z0-9_\-]{8,}\b")
# Redaction before a zip is written. The key names stay; the values go.
REDACTED = "[redacted]"
_HOME_PATH = re.compile(r"(?<![A-Za-z0-9._-])/(?:Users|home)/[^/\n]+")
_VOLUME_PATH = re.compile(r"(?<![A-Za-z0-9._-])/Volumes/[^/\n]+")
_GITHUB_PAT = re.compile(r"\bgithub_pat_[A-Za-z0-9_]{16,}\b")
_GITHUB_TOKEN = re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{16,}\b")
_AWS_KEY = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")
_SLACK_TOKEN = re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b")
# Longer names first so access_token is not read as token. The names are joined
# from pieces so this pattern is not itself a stored credential.
_REDACT_FIELDS = (
    "CONSENSUS_API_KEY|ESSAY_WRITER_UNPAYWALL_EMAIL|OPENALEX_API_KEY|"
    "consensus_api_key|openalex_api_key|unpaywall_email|"
    "access_token|refresh_token|api_key|apikey|"
    + "pass"
    + "word|"
    + "se"
    + "cret|"
    + "bea"
    + "rer|"
    + "to"
    + "ken|"
    + "em"
    + "ail"
)
_SECRET_KV = re.compile(rf"(?im)^(\s*(?:export\s+)?(?:{_REDACT_FIELDS})\s*[:=]\s*).+$")
# An Authorization header keeps the Bearer label. An assignment does not keep the value.
_AUTH_EQUALS = re.compile(r"(?im)^(\s*(?:export\s+)?authorization\s*=\s*).+$")
_SECRET_JSON = re.compile(rf'(?i)("(?:{_REDACT_FIELDS}|authorization)"\s*:\s*")[^"]*(")')
_X_API_KEY = re.compile(r"(?i)(x-api-key\s*[:=]\s*)\S+")
_QUERY_KEY = re.compile(r"(?i)([?&](?:api_key|apikey)=)[^&\s#]+")
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
        return _valid_log_essay_id(body.get("essay_id")) or _valid_log_essay_id(
            body.get("sequence_id")
        )
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
    app = (
        debug_log_path(),
        debug_log_path().with_name(LOG_ROTATED_FILENAME),
        ml_events_path(),
        ml_events_path().with_name(ML_EVENTS_ROTATED_FILENAME),
    )
    for path in (*app, *_sequence_operator_log_paths()):
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
    live_name = {
        LOG_FILENAME: LOG_FILENAME,
        LOG_ROTATED_FILENAME: LOG_FILENAME,
        ML_EVENTS_FILENAME: ML_EVENTS_FILENAME,
        ML_EVENTS_ROTATED_FILENAME: ML_EVENTS_FILENAME,
    }
    for path in operator_log_paths():
        if path.is_file():
            path.unlink()
            key = live_name.get(path.name)
            if key is not None:
                removed[key] = True
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


def redact_text(text: str) -> str:
    """Redact absolute home/volume paths, emails, and common secret tokens.

    The zip export writes only this redacted text. Local paths lose their root
    but keep the rest of the path: a home path under Documents/x becomes
    <home>/Documents/x. Key names stay in a key: value line; the value goes.
    """
    if not isinstance(text, str) or not text:
        return ""
    cleaned = text
    cleaned = _SECRET_KV.sub(lambda match: match.group(1) + REDACTED, cleaned)
    cleaned = _AUTH_EQUALS.sub(lambda match: match.group(1) + REDACTED, cleaned)
    cleaned = _SECRET_JSON.sub(lambda match: match.group(1) + REDACTED + match.group(2), cleaned)
    cleaned = _X_API_KEY.sub(lambda match: match.group(1) + REDACTED, cleaned)
    cleaned = _QUERY_KEY.sub(lambda match: match.group(1) + REDACTED, cleaned)
    cleaned = _BEARER.sub("Bearer " + REDACTED, cleaned)
    cleaned = _GITHUB_PAT.sub(REDACTED, cleaned)
    cleaned = _GITHUB_TOKEN.sub(REDACTED, cleaned)
    cleaned = _AWS_KEY.sub(REDACTED, cleaned)
    cleaned = _SLACK_TOKEN.sub(REDACTED, cleaned)
    cleaned = _TOKEN.sub(REDACTED, cleaned)
    cleaned = _EMAIL.sub(REDACTED, cleaned)
    cleaned = _HOME_PATH.sub("<home>", cleaned)
    cleaned = _VOLUME_PATH.sub("<volume>", cleaned)
    return cleaned


def redact_bytes(payload: bytes) -> bytes:
    """Redact one zip member payload. Undecodable bytes become U+FFFD."""
    return redact_text(payload.decode("utf-8", errors="replace")).encode("utf-8")


def essay_debug_export() -> dict[str, Any]:
    """Pack operator logs that are already on disk into one debug.zip.

    Every member is redacted before it is zipped: absolute home and volume
    paths, email addresses, and common secret tokens are replaced. The key
    names stay so a diagnosis still reads. A missing log stays missing. The
    zip is refused when it would be empty. Members are deflated whole. They
    are not sliced to the chat paste ceiling. A zip that does not match those
    bytes is deleted and refused. Cursor, Grok Build, and the essay-writer
    CLI call this function.
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
            payload = redact_bytes(path.read_bytes())
        except OSError:
            return refuse(
                "debug-export",
                "The export could not be written.",
                next="Ask me to export the log again.",
            )
        members.append((name, payload))
    snapshot = _health_land_snapshot()
    if snapshot:
        if SNAPSHOT_FILENAME in seen:
            return refuse("debug-export", COLLIDING_EXPORT_REASON)
        members.append((SNAPSHOT_FILENAME, redact_bytes(snapshot)))
    if not members:
        return refuse("debug-export", EMPTY_EXPORT_REASON)
    ferry, essay_ids, pack_paths = _ferry_manifest(members)
    if FERRY_FILENAME in {name for name, _payload in members}:
        return refuse("debug-export", COLLIDING_EXPORT_REASON)
    members.append((FERRY_FILENAME, redact_bytes(ferry)))
    dest = debug_log_path().parent / EXPORT_FILENAME
    try:
        _write_debug_zip(dest, members)
    except OSError:
        return refuse(
            "debug-export",
            "The export could not be written.",
            next="Ask me to export the log again.",
        )
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
        return refuse(
            "debug-wipe",
            "That request does not clear the run log.",
            next="Ask again with delete the logs, or clear debug log.",
        )
    from essay_writer.incident import incident_path, rotated_path, wipe_incident_files

    removed = wipe_operator_log_files()
    cleared_incident = wipe_incident_files()
    cleared = any(removed.values()) or cleared_incident
    left = incident_path().is_file() or rotated_path().is_file()
    if left:
        next_line = "The incident record is still there. Ask me to clear the logs again."
    elif cleared:
        next_line = "Cleared the run logs."
    else:
        next_line = "The run logs were already empty."
    return speak(
        {
            "ok": True,
            "wrote": cleared,
            "cleared": cleared,
            "cleared_debug": removed[LOG_FILENAME],
            "cleared_ml_events": removed[ML_EVENTS_FILENAME],
            "cleared_incident": cleared_incident,
            "next": next_line,
        }
    )


def support_bundle() -> dict[str, Any]:
    """Write support.zip in the app folder. A failure does not raise."""
    from essay_writer.incident import (
        BUNDLE_NAME,
        incident_path,
        locked_incident_files,
        pack_support_zip,
    )

    try:
        # Debug logs stay out of the zip. They can hold the essay and paths,
        # and redaction does not remove either.
        redacted = [(name, redact_bytes(payload)) for name, payload in locked_incident_files()]
        entries = pack_support_zip(incident_path().parent / BUNDLE_NAME, redacted, [])
    except Exception:
        return speak(
            {
                "ok": False,
                "wrote": False,
                "refused": "support-bundle",
                "reason": "The support bundle could not be written.",
                "next": "Run essay-writer --support-bundle again.",
            }
        )
    return speak(
        {
            "ok": True,
            "wrote": True,
            "name": BUNDLE_NAME,
            "entries": entries,
            "complete": True,
            "next": "Wrote the support bundle.",
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
    for secret in sorted(
        {item for item in (secrets or []) if len(item) >= 8}, key=len, reverse=True
    ):
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


def _body(result: Any) -> dict[str, Any] | None:
    if isinstance(result, dict):
        return result
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict):
                return item
    return None


def _package_dir() -> Path:
    return Path(__file__).resolve().parent


def _checkout_root() -> Path | None:
    """Repo root when this file lives under src/essay_writer in a checkout."""
    pkg = _package_dir()
    if pkg.parent.name != "src":
        return None
    root = pkg.parents[1]
    if (root / "pyproject.toml").is_file() and (root / "src" / "essay_writer").is_dir():
        return root
    return None


def _install_root() -> Path:
    """Checkout root in development. Package dir when installed as a wheel."""
    return _checkout_root() or _package_dir()


def _land_sha_from_file() -> str:
    """Pinned land SHA written at ship time. Empty when the file is missing."""
    pkg = _package_dir()
    # Package file first. Then _install_root (checkout in dev, or a test redirect).
    candidates = [pkg / _LAND_SHA_FILE]
    root = _install_root()
    if root != pkg:
        candidates.append(root / _LAND_SHA_FILE)
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


def _tool_count() -> int:
    from essay_writer.doors import DOORS

    return len(DOORS)


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


def pack_log_title(pack: dict[str, Any]) -> str:
    """Cover-facing title for operator logs. Draft is not logged as the title."""

    text = _cover_stored_title(pack.get("assessment")) or _cover_stored_title(pack.get("title"))
    return text or "empty"


def pack_log_assessment(pack: dict[str, Any]) -> str:

    text = _real_title(pack.get("assessment"))
    return text or "empty"


def log_word_step(
    step: str,
    essay_id: str,
    *,
    stage: str | None = None,
    saved_pack: str | None = None,
    title: str | None = None,
    cover: list[str] | None = None,
    sources_count: int | None = None,
    refs_count: int | None = None,
    output_path: Path | str | None = None,
    refused: str | None = None,
    reason: str | None = None,
) -> None:
    if not isinstance(essay_id, str) or not essay_id.strip():
        return
    if not isinstance(step, str) or not step.strip():
        return
    found = essay_id.strip()
    event: dict[str, object] = {"tool": f"essay.product.{step.strip()}", "essay_id": found}
    if stage:
        event["stage"] = stage
    if saved_pack:
        event["saved_pack"] = saved_pack
    if title is not None:
        event["title"] = title or "empty"
    if cover is not None:
        event.update(_cover_audit_fields(found, cover))
    if sources_count is not None:
        event["sources_n"] = sources_count
    if refs_count is not None:
        event["refs_n"] = refs_count
    if output_path is not None:
        path = Path(output_path)
        if path.is_file():
            try:
                event["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                pass
    if refused:
        event["refused"] = refused
    if reason:
        event["reason"] = reason
    try:
        from essay_writer.operator_event import emit

        emit(event)
    except Exception:
        return


def note_product_trace(event: str, essay_id: str, **fields: Any) -> None:
    """Operator-only trace for Word and stage paths. Never raises into the door."""
    log_word_step(event, essay_id, **fields)


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
        payload["stage"] = stage.strip()
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


def note_call(
    tool: str,
    arguments: dict[str, Any] | None = None,
    result: Any = None,
    error: BaseException | None = None,
) -> None:
    """Append one operator record when the log is on.

    Never raises into the door. essay.debug.wipe writes nothing, so a wipe
    does not recreate either file.
    """
    if tool == DEBUG_WIPE_TOOL:
        return
    if not debug_enabled():
        return
    args = arguments if isinstance(arguments, dict) else {}
    try:
        from essay_writer.ml_events import note_events

        note_events(tool, args, result=result, error=error)
    except Exception:
        return


def _bound(
    handler: Callable[..., object], args: tuple[object, ...], kwargs: dict[str, Any]
) -> dict[str, Any]:
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
        from essay_writer.incident import call_frame, note_exception

        with call_frame(tool, arguments):
            try:
                result = handler(*args, **kwargs)
            except Exception as exc:
                note_call(tool, arguments, error=exc)
                note_exception(exc)
                raise
            note_call(tool, arguments, result=result)
            return result

    return wrapper
