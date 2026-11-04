"""Local essay shelf. Get and put are both two-step."""

from __future__ import annotations

import json
import os
import re

from essay_writer.canon import file_sha256
from essay_writer.confirm import (
    CONFIRM,
    DRAFT,
    confirm_ready,
    now,
    phase_refusal,
    refuse,
    save_draft,
)
from essay_writer.known_paths import guard_write_door
from essay_writer.paths import (
    module_code,
    relative,
    sequence_number,
    sequence_write_error,
    work_dir,
)
from essay_writer.state import load_state, save_state
from essay_writer.student_voice import say
from essay_writer.validate import inspect_pack, pack_identity

PUT = "essay.shelf.put"
GET = "essay.shelf.get"
PACK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")


def _clean_id(value: object) -> str | None:
    if isinstance(value, str) and PACK_ID.fullmatch(value):
        return value
    return None


def _derive(essay_id: str, pack: dict[str, object], pack_id: str | None) -> str:
    cleaned = _clean_id(pack_id) if pack_id else None
    if cleaned:
        return cleaned
    return "pack-" + pack_identity(essay_id, pack)[:12]


def _shelf_file(essay_id: str, pack_id: str):
    return work_dir(essay_id) / "shelf" / f"{pack_id}.json"


def _shelf_card_path(essay_id: str, pack_id: str) -> str:
    """Path the Bot shows on the shelf draft. It is the sequence shelf, not the module root."""
    number = sequence_number(essay_id)
    module = module_code(essay_id)
    if number is None:
        return ""
    return f"Essay-writer/{module}/sequences/{number}/shelf/{pack_id}.json"


def essay_shelf_put(
    essay_id: str,
    pack: dict[str, object],
    confirmPhase: str | None = None,
    pack_id: str | None = None,
    topic: str | None = None,
) -> dict[str, object]:
    id_error = sequence_write_error(essay_id)
    if id_error:
        return refuse("essay-id", id_error)
    phase = phase_refusal(confirmPhase)
    if phase:
        return phase

    blocked = guard_write_door(work_dir(essay_id))
    if blocked:
        return blocked
    if not isinstance(pack, dict):
        return refuse("pack", "pack must be an object")
    if pack_id is not None and _clean_id(pack_id) is None:
        return refuse("shelf", "pack_id has characters the local shelf will not store")
    if isinstance(topic, str) and topic.strip() and topic.strip() != str(pack.get("title", "")).strip():
        return refuse("shelf", "topic does not match the pack title. Confirm one title, not two.")
    report = inspect_pack(essay_id, pack)
    hard = [item for item in report["blockers"] if item["code"] in {"invent-forbid", "cross-essay"}]
    if hard:
        return refuse(hard[0]["code"], hard[0]["reason"], blockers=report["blockers"])
    identity = pack_identity(essay_id, pack)
    state = load_state(essay_id)
    word = (state.get("word") or {}).get(identity)
    if not isinstance(word, dict):
        return refuse(
            "shelf",
            "Shelf stores a pack only after Word confirm for that same pack.",
        )
    if not report["passed"] or word.get("files") != report["files"]:
        return refuse(
            "confirm",
            "The pack or its gathered files changed after Word. Validate and write Word again before the shelf.",
        )
    local_id = _derive(essay_id, pack, pack_id)
    payload = {"essay_id": essay_id, "pack": pack, "pack_id": local_id}
    if topic is not None:
        payload["topic"] = topic
    fingerprint = {"word": word, "files": report["files"]}
    body: dict[str, object] = {
        "ok": True,
        "essay_id": essay_id,
        "confirmPhase": confirmPhase,
        "wrote": False,
        "stored": False,
        "pack_id": local_id,
        "pack_digest": identity,
        "title": report["title"],
        "path": _shelf_card_path(essay_id, local_id),
        "same_arguments_required": True,
    }
    if confirmPhase == DRAFT:
        body["digest"] = save_draft(essay_id, PUT, payload, fingerprint)
        body["next"] = say(
            "Show this saved-copy draft to the human. Saying yes stores it on this computer."
        )
        return body
    ready = confirm_ready(essay_id, PUT, payload, fingerprint)
    if ready.get("ok") is False:
        ready["confirmPhase"] = CONFIRM
        return ready
    target = _shelf_file(essay_id, local_id)
    record = {
        "essay_id": essay_id,
        "pack_id": local_id,
        "pack_digest": identity,
        "title": report["title"],
        "topic": topic.strip() if isinstance(topic, str) else report["title"],
        "pack": pack,
        "word": word.get("path"),
        "confirmed_at": now(),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    state = load_state(essay_id)
    state["shelf"][local_id] = {
        "pack_id": local_id,
        "pack_digest": identity,
        "path": relative(target),
        "title": report["title"],
        "confirmed_at": record["confirmed_at"],
    }
    save_state(essay_id, state)
    body["stored"] = True
    body["wrote"] = True
    body["digest"] = ready["digest"]
    body["path"] = relative(target)
    return body


def essay_shelf_get(
    essay_id: str,
    pack_id: str,
    confirmPhase: str | None = None,
) -> dict[str, object]:
    id_error = sequence_write_error(essay_id)
    if id_error:
        return refuse("essay-id", id_error)
    phase = phase_refusal(confirmPhase)
    if phase:
        return phase

    blocked = guard_write_door(work_dir(essay_id))
    if blocked:
        return blocked
    cleaned = _clean_id(pack_id)
    if cleaned is None:
        return refuse("shelf", "pack_id is not a local shelf id")
    path = _shelf_file(essay_id, cleaned)
    if not path.is_file():
        return refuse("shelf", "no shelf pack for this essay id")
    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict) or record.get("essay_id") != essay_id:
        return refuse("cross-essay", "that shelf record is not this essay")
    payload = {"essay_id": essay_id, "pack_id": cleaned}
    fingerprint = {"sha256": file_sha256(path)}
    body: dict[str, object] = {
        "ok": True,
        "essay_id": essay_id,
        "confirmPhase": confirmPhase,
        "wrote": False,
        "stored": False,
        "pack_id": cleaned,
        "title": record.get("title"),
        "pack_digest": record.get("pack_digest"),
        "same_arguments_required": True,
    }
    if confirmPhase == DRAFT:
        body["digest"] = save_draft(essay_id, GET, payload, fingerprint)
        body["next"] = say("The draft shows the label only. Saying yes with the same pack_id returns it.")
        return body
    ready = confirm_ready(essay_id, GET, payload, fingerprint)
    if ready.get("ok") is False:
        ready["confirmPhase"] = CONFIRM
        return ready
    body["stored"] = True
    body["pack"] = record.get("pack")
    body["word"] = record.get("word")
    body["digest"] = ready["digest"]
    return body
