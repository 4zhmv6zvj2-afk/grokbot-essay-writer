"""Draft-then-confirm ledger.

A write is stored only when confirmPhase is confirm and a draft of the same
arguments is already on disk. A changed payload is a different digest and
cannot reuse the old draft.

The fingerprint is the student arguments and the hashes of local files.
A live look-up body is not a fingerprint field. A drift in gathered-file
hashes refuses confirm even when the arguments are unchanged. The card that
was shown may be stored beside the fingerprint. Confirm reuses that card.
It is not compared as a fingerprint.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from essay_writer.canon import digest, dump
from essay_writer.known_paths import refuse_repo_write
from essay_writer.paths import work_dir
from essay_writer.student_voice import speak

DRAFT = "draft"
CONFIRM = "confirm"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def refuse(code: str, reason: str, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "ok": False,
        "refused": code,
        "reason": reason,
        "wrote": False,
        "stored": False,
    }
    body.update(extra)
    return speak(body)


def phase_refusal(phase: object) -> dict[str, Any] | None:
    if phase == DRAFT or phase == CONFIRM:
        return None
    if phase is None:
        return refuse(
            "confirm",
            "Show this step in the chat first. Then it can be saved. Do not save it silently.",
        )
    return refuse("confirm", "That step was not shown in a form this chat can save.")


def _draft_path(essay_id: str, tool: str, payload_digest: str, root: Path | None = None):
    home = root if root is not None else work_dir(essay_id)
    return home / ".drafts" / tool / f"{payload_digest}.json"


def save_draft(
    essay_id: str,
    tool: str,
    payload: dict[str, Any],
    fingerprint: dict[str, Any],
    *,
    root: Path | None = None,
    shown: dict[str, Any] | None = None,
) -> str:
    """Store one draft.

    fingerprint is student arguments and local file hashes. shown is the card
    the student saw, including look-up rows. shown is not part of the fingerprint.
    """
    payload_digest = digest(payload)
    record = {
        "tool": tool,
        "essay_id": essay_id,
        "digest": payload_digest,
        "payload": payload,
        "fingerprint": fingerprint,
        "created_at": now(),
    }
    if shown is not None:
        record["shown"] = shown
    path = _draft_path(essay_id, tool, payload_digest, root)

    refuse_repo_write(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return payload_digest


def _read_draft_record(path: Path, payload_digest: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(record, dict):
        return None
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return None
    if digest(payload) != payload_digest or record.get("digest") != payload_digest:
        return None
    return record


def load_draft(
    essay_id: str,
    tool: str,
    payload: dict[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Any] | None:
    payload_digest = digest(payload)
    path = _draft_path(essay_id, tool, payload_digest, root)
    return _read_draft_record(path, payload_digest)


def latest_draft(
    essay_id: str,
    tool: str,
    *,
    root: Path | None = None,
    stage: str | None = None,
) -> dict[str, Any] | None:
    """Newest draft for this tool. Stage saves pass stage so another step is not reused."""
    home = root if root is not None else work_dir(essay_id)
    folder = home / ".drafts" / tool
    if not folder.is_dir():
        return None
    best: dict[str, Any] | None = None
    best_key: tuple[str, float] | None = None
    for path in folder.glob("*.json"):
        if not path.is_file() or path.name.endswith(".tmp"):
            continue
        record = _read_draft_record(path, path.stem)
        if record is None:
            continue
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        if payload.get("essay_id") not in (None, essay_id):
            continue
        if stage is not None and payload.get("stage") != stage:
            continue
        created = str(record.get("created_at") or "")
        try:
            modified = path.stat().st_mtime
        except OSError:
            modified = 0.0
        # created_at is whole seconds. The newer file is the waiting card.
        key = (created, modified)
        if best_key is None or key >= best_key:
            best = record
            best_key = key
    return best


def load_draft_by_digest(
    essay_id: str,
    tool: str,
    payload_digest: str,
    *,
    root: Path | None = None,
) -> dict[str, Any] | None:
    """The draft a Confirm card names. The digest is the file name, not a rebuilt payload."""
    if not isinstance(payload_digest, str) or re.fullmatch(r"[0-9a-f]{64}", payload_digest) is None:
        return None
    path = _draft_path(essay_id, tool, payload_digest, root)
    return _read_draft_record(path, payload_digest)


def confirm_ready(
    essay_id: str,
    tool: str,
    payload: dict[str, Any],
    fingerprint: dict[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Return the draft record, or a refusal dict (ok false).

    A matching draft still refuses when fingerprint differs. That comparison
    is the gathered-file hashes and the student arguments. It is not a live
    look-up body.
    """
    record = load_draft(essay_id, tool, payload, root=root)
    if record is None:
        return refuse(
            "confirm",
            "No matching draft is waiting. Show this step in the chat again before it can be saved. "
            "If the draft, the topic, or the source list changed, show it again.",
            digest=digest(payload),
        )
    if dump(record.get("fingerprint")) != dump(fingerprint):
        return refuse(
            "confirm",
            "The saved files changed after that step was shown. Show this step again in this chat.",
            digest=digest(payload),
        )
    return record
