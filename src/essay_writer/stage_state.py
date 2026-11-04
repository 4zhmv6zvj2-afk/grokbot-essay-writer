"""State and reply layer for the stage tracking note.

This module owns the pointer and its commit journal, the stage lock, the
tracking-note renderer, and the reply bodies a stage save returns when it is
held or refused. The orchestrator in essay_writer.stage_track keeps the public
entry points and re-exports every name here. This module does not import
essay_writer.stage_track at module import time; the two call-time imports in
_confirm_blocked and _draft_next_card close that loop.
"""

from __future__ import annotations

import contextvars
import fcntl
import json
import os
import threading
from contextlib import contextmanager
from typing import Any, TypedDict, cast

from essay_writer.confirm import (
    CONFIRM,
    latest_draft,
    load_draft_by_digest,
    refuse,
)
from essay_writer.known_paths import refuse_repo_write
from essay_writer.paths import relative, work_dir
from essay_writer.stage_llm import (
    POINTER_FILE,
    STAGE_ORDER,
    brief_genre,
    next_stage,
    stage_settings,
    stage_title,
    tracking_file,
)

TOOL = "essay.stage"
_MINTING: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "essay_stage_minting",
    default=False,
)
_INHERITED_KEEP: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "essay_stage_inherited_keep",
    default=False,
)


def _atomic(path, text: str) -> None:

    refuse_repo_write(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    temporary.write_text(text, encoding="utf-8")
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


# One file. The note body and the pointer that names it land together.
STAGE_COMMIT = "tracking/.stage.commit"
_STAGE_NOTE_RELS = frozenset(tracking_file(stage) for stage in STAGE_ORDER)
_LOCKS = threading.local()


def _pointer_path(essay_id: str):
    return work_dir(essay_id) / POINTER_FILE


def _commit_path(essay_id: str):
    return work_dir(essay_id) / STAGE_COMMIT


def _pointer_text(pointer: Pointer) -> str:
    return json.dumps(pointer, indent=2, ensure_ascii=False) + "\n"


def _note_rel(note) -> str:
    rel = f"tracking/{note.name}"
    if rel not in _STAGE_NOTE_RELS:
        raise ValueError(rel)
    return rel


def _apply_commit(root, record: dict[str, object]) -> None:
    """Publish one journal record onto a sequence folder. The journal is removed last."""
    note_rel = record.get("note")
    note_text = record.get("note_text")
    if note_rel is not None or note_text is not None:
        if not isinstance(note_rel, str) or note_rel not in _STAGE_NOTE_RELS or not isinstance(note_text, str):
            raise ValueError("stage commit note is not a tracking note")
        _atomic(root / note_rel, note_text)
    pointer = record.get("pointer")
    if not isinstance(pointer, dict):
        raise ValueError("stage commit is missing the pointer")
    _atomic(root / POINTER_FILE, _pointer_text(cast(Pointer, pointer)))
    journal = root / STAGE_COMMIT
    if journal.is_file():
        journal.unlink()


def _read_commit(root) -> dict[str, object] | None:
    journal = root / STAGE_COMMIT
    if not journal.is_file():
        return None
    try:
        record = json.loads(journal.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(record, dict) or not isinstance(record.get("pointer"), dict):
        return None
    return record


def _replay_commit(root) -> None:
    record = _read_commit(root)
    if record is not None:
        _apply_commit(root, record)


def _note_path(essay_id: str, stage: str):
    name = tracking_file(stage)
    if name is None:
        raise KeyError(stage)
    return work_dir(essay_id) / name


class Pointer(TypedDict, total=False):
    current: str
    saved: list[str]
    files: dict[str, object]
    closed: bool
    revisit_open: str | None
    revisit_after_lock: bool
    chain_armed: bool
    room_grant: str | None
    room_lock: bool
    waiting_stage: str | None
    waiting_digest: str | None
    revision: int


class StageResult(TypedDict, total=False):
    ok: bool
    essay_id: str
    stage: str
    confirmPhase: str | None
    noop: bool
    wrote: bool
    stored: bool
    advanced: bool
    closed: bool
    submitted: bool
    refused: str
    reason: str
    digest: str
    current: str
    next: str


def blank_pointer() -> dict[str, object]:
    """A new sequence is open on stage 1. Nothing is saved yet."""
    return {
        "current": "1",
        "saved": [],
        "files": {},
        "closed": False,
        "revisit_open": None,
        "revisit_after_lock": False,
        "chain_armed": False,
        "room_grant": None,
        "room_lock": False,
        "waiting_stage": None,
        "waiting_digest": None,
        "revision": 0,
    }


def _clear_copied_writing(folder) -> None:
    """Drop inherited stage notes and drafts. The child writes its own."""
    for rel in _STAGE_NOTE_RELS:
        note = folder / rel
        if note.is_file() or note.is_symlink():
            note.unlink()
    drafts = folder / ".drafts"
    if drafts.is_dir():
        import shutil

        shutil.rmtree(drafts)


def init_cloned_sequence_pointer(folder) -> None:
    """Pointer init after a parent tree is copied onto a new sequence.

    Open and closed parents use the same shape. The child starts open on
    stage 1 with nothing saved. The parent's writing pointer is not kept,
    and the copied stage notes and drafts are removed so stages 1–3 run
    again from the first card. A journal copied with the tree is finished
    first, then replaced, so the child is not a torn pair.
    """
    _replay_commit(folder)
    path = folder / POINTER_FILE
    if path.is_file():
        _atomic(path, _pointer_text(cast(Pointer, blank_pointer())))
    _clear_copied_writing(folder)


def rebind_cloned_confirms(folder, essay_id: str) -> None:
    """Point copied drafts at this sequence.

    The id rewrite changes the payload, so the file hash changes with it.
    The draft file and a waiting digest still named the parent's hash, and
    that card could not be loaded on the child. The only card that hash
    still opens is the parent's. This writes the child's hash, or clears a
    waiting digest that does not belong to this sequence.
    """
    from essay_writer.canon import digest as payload_digest

    root = folder / ".drafts"
    stage_map: dict[str, tuple[str, str | None]] = {}
    if root.is_dir():
        for path in list(root.rglob("*.json")):
            if not path.is_file() or path.name.endswith(".tmp"):
                continue
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(record, dict):
                path.unlink()
                continue
            payload = record.get("payload")
            if not isinstance(payload, dict):
                path.unlink()
                continue
            owner = payload.get("essay_id")
            if isinstance(owner, str) and owner != essay_id:
                path.unlink()
                continue
            new_digest = payload_digest(payload)
            record["digest"] = new_digest
            record["essay_id"] = essay_id
            dest = path.with_name(f"{new_digest}.json")
            dest.write_text(
                json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            if dest != path and path.is_file():
                path.unlink()
            if path.parent.name == TOOL:
                stage = payload.get("stage")
                stage_map[path.stem] = (new_digest, stage if isinstance(stage, str) else None)
    pointer_path = folder / POINTER_FILE
    if not pointer_path.is_file():
        return
    try:
        data = json.loads(pointer_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(data, dict) or data.get("closed") is True:
        return
    waiting = data.get("waiting_digest")
    if not isinstance(waiting, str) or not waiting:
        return
    bound = stage_map.get(waiting)
    stage = data.get("waiting_stage")
    if bound is not None and bound[1] == stage:
        data["waiting_digest"] = bound[0]
    else:
        data["waiting_stage"] = None
        data["waiting_digest"] = None
    _atomic(pointer_path, _pointer_text(cast(Pointer, data)))


def _own_door_card(opened: dict[str, object] | None, essay_id: str, stage: str) -> dict[str, object] | None:
    """The door card when it names this sequence and this stage."""
    if not isinstance(opened, dict) or opened.get("ok") is False:
        return None
    card = opened.get("card")
    if not isinstance(card, dict) or card.get("kind") != "confirm":
        return None
    if card.get("essay_id") != essay_id or card.get("stage") != stage:
        return None
    digest = opened.get("cardDigest") or card.get("digest")
    if not isinstance(digest, str) or len(digest) != 64:
        return None
    if card.get("digest") not in (None, digest):
        return None
    return opened


def door_card_reply(essay_id: str) -> dict[str, object] | None:
    """Confirm card for this sequence's open stage.

    A fresh stage 1, with nothing saved, gets that stage's door card.
    Roll-forward starts the child on stage 1 and returns that card.
    A card from another sequence is not returned.
    """
    from essay_writer.spine import stage_uses_confirm_card

    pointer = load_pointer(essay_id)
    if pointer.get("closed") is True:
        return None
    current = pointer.get("current")
    if not isinstance(current, str) or not stage_uses_confirm_card(current):
        return None
    saved = pointer.get("saved") or []
    if current in saved:
        return None
    replay = _replay_confirm_card(essay_id, current, brief_genre(essay_id), pointer, None)
    own = _own_door_card(replay, essay_id, current)
    if own is not None:
        return own
    if current == "1" and not saved:
        return _own_door_card(_draft_next_card(essay_id, "1"), essay_id, "1")
    return None


def _read_pointer_data(essay_id: str) -> dict[str, object] | None:
    path = _pointer_path(essay_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def load_pointer(essay_id: str) -> dict[str, Any]:
    if not _pointer_path(essay_id).is_file() and not _commit_path(essay_id).is_file():
        return blank_pointer()
    with _pointer_lock(essay_id):
        data = _read_pointer_data(essay_id)
        if data is None:
            return blank_pointer()
        return _normalize_pointer(data)


def _normalize_pointer(data: dict[str, Any]) -> dict[str, Any]:
    current = data.get("current")
    if current not in STAGE_ORDER:
        current = "1"
    saved = [item for item in data.get("saved") or [] if item in STAGE_ORDER]
    files_raw = data.get("files")
    files: dict[str, object] = files_raw if isinstance(files_raw, dict) else {}
    kept = {key: value for key, value in files.items() if key in STAGE_ORDER and isinstance(value, str)}
    reopen = data.get("revisit_open")
    if reopen not in {"2", "3"}:
        reopen = None
    grant = data.get("room_grant")
    if grant not in STAGE_ORDER:
        grant = None
    waiting_stage, waiting_digest = _waiting_pair(data)
    return {
        "current": current,
        "saved": saved,
        "files": kept,
        "closed": data.get("closed") is True,
        "revisit_open": reopen,
        "revisit_after_lock": data.get("revisit_after_lock") is True,
        "chain_armed": data.get("chain_armed") is True,
        "room_grant": grant,
        "room_lock": data.get("room_lock") is True,
        "waiting_stage": waiting_stage,
        "waiting_digest": waiting_digest,
        "revision": _revision(data),
    }


def _room_state(pointer: dict[str, Any]) -> dict[str, object]:
    """The room press still on the pointer. A card tap leaves both empty."""
    grant = pointer.get("room_grant")
    if grant not in STAGE_ORDER:
        grant = None
    return {"room_grant": grant, "room_lock": pointer.get("room_lock") is True}


def _room_after_card_save(pointer: dict[str, Any], stage: str) -> dict[str, object]:
    """A room press saves only the stage it named. The next stage needs its own press."""
    state = _room_state(pointer)
    if state["room_grant"] == stage:
        return {"room_grant": None, "room_lock": True}
    return {"room_grant": None, "room_lock": False}


def _saved_after_confirm(pointer: dict[str, Any], stage: str) -> list[str]:
    """One confirm stores this stage only. The next stage is not appended."""
    saved = list(pointer["saved"])
    if stage not in saved:
        saved.append(stage)
    return saved


def _room_blocks(pointer: dict[str, Any], stage: str) -> bool:
    """True when a room press for another stage, or a used press, is not this stage's Confirm."""
    state = _room_state(pointer)
    if state["room_lock"] and state["room_grant"] != stage:
        return True
    return state["room_grant"] is not None and state["room_grant"] != stage


def _waiting_pair(pointer: dict[str, Any]) -> tuple[str | None, str | None]:
    stage = pointer.get("waiting_stage")
    digest = pointer.get("waiting_digest")
    if stage not in STAGE_ORDER or not isinstance(digest, str) or len(digest) != 64:
        return None, None
    return stage, digest


def _waiting_digest(pointer: dict[str, Any], stage: str) -> str | None:
    """Digest of the draft that wrote the current note for this stage."""
    waiting_stage, digest = _waiting_pair(pointer)
    if waiting_stage != stage:
        return None
    return digest


def _note_look(essay_id: str, stage: str) -> str | None:
    """Look last written into this stage's tracking note."""
    try:
        path = _note_path(essay_id, stage)
    except KeyError:
        return None
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    for heading in ("## Final look\n\n", "## Working look\n\n"):
        if heading in text:
            body = text.rsplit(heading, 1)[1]
            body = body.removesuffix("\n")
            return body
    return None


def _revision(pointer: dict[str, Any]) -> int:
    value = pointer.get("revision")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


def _held_locks() -> set[str]:
    held = getattr(_LOCKS, "held", None)
    if held is None:
        held = set()
        _LOCKS.held = held
    return held


@contextmanager
def _pointer_lock(essay_id: str):
    """One exclusive lock for the note and pointer on this sequence.

    The same thread may re-enter. A journal left by a crashed commit is
    finished before the body runs, so readers do not see a torn pair.
    """
    held = _held_locks()
    if essay_id in held:
        yield
        return
    folder = work_dir(essay_id) / "tracking"
    folder.mkdir(parents=True, exist_ok=True)
    handle = (folder / ".stage.lock").open("a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        held.add(essay_id)
        try:
            _replay_commit(work_dir(essay_id))
            yield
        finally:
            held.discard(essay_id)
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def stage_lock(essay_id: str):
    """Exclusive lock for this sequence's note and pointer. Replays a torn commit first."""
    return _pointer_lock(essay_id)


def _rolls_backward(fresh: dict[str, Any], proposed: dict[str, Any]) -> bool:
    """True when proposed drops a saved stage or moves current to an earlier stage."""
    fresh_saved = [item for item in fresh.get("saved") or [] if item in STAGE_ORDER]
    proposed_saved = [item for item in proposed.get("saved") or [] if item in STAGE_ORDER]
    if any(item not in proposed_saved for item in fresh_saved):
        return True
    if fresh.get("closed") is True and proposed.get("closed") is not True:
        return True
    fresh_at = fresh.get("current")
    proposed_at = proposed.get("current")
    if fresh_at in STAGE_ORDER and proposed_at in STAGE_ORDER:
        return STAGE_ORDER.index(proposed_at) < STAGE_ORDER.index(fresh_at)
    return False


def _commit_pointer(
    essay_id: str,
    base: dict[str, Any],
    proposed: dict[str, Any],
    *,
    note=None,
    note_text: str | None = None,
) -> dict[str, object] | None:
    """Commit the note and pointer only while base is still the pointer on disk.

    The revision loaded with base must still be the revision on disk. A newer
    writer has already moved the sequence, so this write is skipped. Proposed
    current and saved are not allowed to move backward from what is on disk.
    The note and the pointer are written into one journal file first. A crash
    between the live files is finished from that journal on the next lock.
    """
    with _pointer_lock(essay_id):
        fresh = load_pointer(essay_id)
        if _revision(fresh) != _revision(base):
            return None
        if _rolls_backward(fresh, proposed):
            return None
        stored = dict(proposed)
        stored["revision"] = _revision(fresh) + 1
        record: dict[str, object] = {"pointer": stored}
        if note is not None and note_text is not None:
            record["note"] = _note_rel(note)
            record["note_text"] = note_text
        _atomic(_commit_path(essay_id), _pointer_text(cast(Pointer, record)))
        _apply_commit(work_dir(essay_id), record)
        return stored


def _pointer_lost(essay_id: str, stage: str, genre: str | None) -> dict[str, object]:
    """The pointer moved after this call read it. The newer pointer stays."""
    fresh = load_pointer(essay_id)
    blocked = _stage_refusal(cast(Pointer, fresh), stage, genre)
    if blocked is not None:
        return _confirm_blocked(essay_id, fresh, stage, genre, blocked)
    return refuse(
        "pointer",
        f"This step was saved in another chat. The current stage is {fresh['current']}.",
        current=fresh["current"],
        stage=stage,
        waiting_confirm=True,
        stored=False,
        advanced=False,
        wrote=False,
    )


def _confirm_blocked(
    essay_id: str,
    pointer: dict[str, Any],
    stage: str,
    genre: str | None,
    blocked: dict[str, object],
) -> dict[str, object]:
    """An already-saved stage does not replay its card. The draft card is for current."""
    from essay_writer.specialists.grok_bot import missing_confirm_next
    from essay_writer.spine import stage_uses_confirm_card
    from essay_writer.stage_track import essay_stage

    current = pointer["current"]
    blocked["waiting_confirm"] = False
    blocked["stored"] = False
    blocked["advanced"] = False
    blocked["repost"] = False
    blocked.pop("card", None)
    blocked.pop("cardAction", None)
    blocked.pop("cardDigest", None)
    saved = pointer.get("saved") or []
    if pointer.get("closed") is True or current in saved:
        blocked["next"] = str(
            blocked.get("reason")
            or "The last stage is already saved. This tool does not submit."
        )
        return blocked
    opened = None
    if stage_uses_confirm_card(current) and current != stage:
        opened = _replay_confirm_card(essay_id, current, genre, pointer, None)
        if opened is None:
            opened = essay_stage(essay_id, current, "draft", card_only=True)
    opened_reply = opened if isinstance(opened, dict) else None
    card = opened_reply.get("card") if isinstance(opened_reply, dict) else None
    digest = opened_reply.get("cardDigest") if isinstance(opened_reply, dict) else None
    if (
        isinstance(opened_reply, dict)
        and isinstance(card, dict)
        and card.get("essay_id") == essay_id
        and card.get("stage") == current
        and card.get("stage") != stage
        and opened_reply.get("cardAction") == "confirm"
        and isinstance(digest, str)
        and len(digest) == 64
    ):
        blocked["card"] = card
        if opened_reply.get("cardAction"):
            blocked["cardAction"] = opened_reply["cardAction"]
        if opened_reply.get("cardDigest"):
            blocked["cardDigest"] = opened_reply["cardDigest"]
        nxt = opened_reply.get("next")
        blocked["next"] = nxt if isinstance(nxt, str) and nxt.strip() else missing_confirm_next(
            current, stage_title(current, genre)
        )
    else:
        blocked["next"] = missing_confirm_next(current, stage_title(current, genre))
    return blocked


def _opening_look(essay_id: str) -> str:
    """A next-stage draft the assignment check can hold. Daily use stays empty."""
    from essay_writer.specialists.grok_bot import (
        attach_basics_pass,
        cached_approved_look,
    )

    cached = cached_approved_look(essay_id)
    if cached:
        return cached
    lines = attach_basics_pass(essay_id)
    if not lines:
        return ""
    return "\n".join(lines)


def _next_card_look(essay_id: str, stage: str) -> str:
    """Opening note the next Confirm card can save. The brief's own names stay in it."""
    from essay_writer.brief_contract import opening_card_lines

    lines: list[str] = []
    opening = _opening_look(essay_id)
    if opening:
        lines.extend(line for line in opening.splitlines() if line)
    text = "\n".join(lines)
    for extra in opening_card_lines(essay_id, stage):
        if extra.casefold() not in text.casefold():
            lines.append(extra)
            text = "\n".join(lines)
    return "\n".join(lines)


def _draft_next_card(essay_id: str, following: str) -> dict[str, object]:
    """One card-only draft of the next stage. It does not move the pointer.

    Student-answer rules (part names, Entry N, house words) stay off this mint.
    They run when the student later writes that stage. The flag is not a door
    argument.
    """
    from essay_writer.stage_track import essay_stage

    token = _MINTING.set(True)
    try:
        return essay_stage(
            essay_id,
            following,
            "draft",
            _next_card_look(essay_id, following),
            card_only=True,
        )
    finally:
        _MINTING.reset(token)


def _next_card_fields(opened: dict[str, object], essay_id: str, following: str) -> dict[str, object] | None:
    """card, cardAction, and cardDigest for this sequence's next stage, or nothing."""
    card = opened.get("card")
    if not isinstance(card, dict):
        return None
    if card.get("essay_id") != essay_id or card.get("stage") != following:
        return None
    if card.get("kind") != "confirm":
        return None
    action = opened.get("cardAction") or card.get("cardAction")
    digest = opened.get("cardDigest") or card.get("cardDigest") or card.get("digest")
    if action != "confirm" or not isinstance(digest, str) or len(digest) != 64:
        return None
    if card.get("digest") not in (None, digest):
        return None
    return {"card": card, "cardAction": action, "cardDigest": digest}


def _pending_inherited(essay_id: str, stage: str | None) -> dict[str, object] | None:
    """Parent save still waiting on a copied stage 2 or 3."""
    if not stage:
        return None
    from essay_writer.fo_chat_locks import inherited_lock_pending

    return inherited_lock_pending(essay_id, stage)


def _name_inherited_lock(
    body: dict[str, object],
    essay_id: str,
    stage: str,
    row: dict[str, object],
) -> dict[str, object]:
    """Name the parent save. This reply does not carry a Confirm card."""
    from essay_writer.fo_chat_locks import prior_saved_lock_ask

    ask = prior_saved_lock_ask(essay_id, stage, row)
    body.pop("card", None)
    body.pop("cardAction", None)
    body.pop("cardDigest", None)
    body.pop("explicit_end", None)
    body["next"] = ask["next"]
    body["prior_saved_lock"] = ask["prior_saved_lock"]
    body["inherited_lock_preview"] = ask["inherited_lock_preview"]
    body["lock_choices"] = ask["lock_choices"]
    body["waiting_confirm"] = False
    return body


def _expects_next_card(following: str | None) -> bool:
    """True when this advance must carry the next stage's Confirm card."""
    from essay_writer.spine import stage_uses_confirm_card

    return bool(following) and stage_uses_confirm_card(following or "")


def _mint_stage_allowed(pointer: dict[str, Any], stage: str) -> bool:
    """The next card may be minted while the pointer is still on the stage being confirmed."""
    if pointer.get("closed") is True or stage in (pointer.get("saved") or []):
        return False
    current = pointer.get("current")
    if current not in STAGE_ORDER:
        return False
    return next_stage(current) == stage


def _hold_confirm(
    essay_id: str,
    stage: str,
    genre: str | None,
    pointer: dict[str, Any],
    card_digest: str | None,
    opened: dict[str, Any] | None,
    following: str,
) -> dict[str, object]:
    """The next card was not minted. The pointer and the waiting card stay."""
    reason = "The next Confirm card was not returned. This step was not saved."
    code = "card"
    if isinstance(opened, dict):
        if isinstance(opened.get("reason"), str) and opened["reason"].strip():
            reason = f"{opened['reason'].strip()} This step was not saved."
        if isinstance(opened.get("refused"), str) and opened["refused"].strip():
            code = opened["refused"].strip()
    held = _reoffer_confirm(
        essay_id,
        stage,
        genre,
        pointer,
        card_digest,
        code=code,
        reason=reason,
    )
    held["next_card_stage"] = following
    held["advanced"] = False
    held["stored"] = False
    return held


def _attach_minted_card(
    body: dict[str, object],
    opened: dict[str, object],
    fields: dict[str, object],
) -> dict[str, object]:
    """Put the already-minted next card on a confirm that has been stored."""
    body["repost"] = False
    body["card"] = fields["card"]
    body["cardAction"] = fields["cardAction"]
    body["cardDigest"] = fields["cardDigest"]
    chain = body.get("next_run") or body.get("blocked") or body.get("final_word")
    nxt = opened.get("next")
    if not chain and isinstance(nxt, str) and nxt.strip():
        body["next"] = nxt
    if "status" not in body:
        status = opened.get("status")
        if isinstance(status, list) and any(isinstance(line, str) and line for line in status):
            body["status"] = [line for line in status if isinstance(line, str) and line]
    questions = opened.get("questions")
    if isinstance(questions, list) and questions:
        body["questions"] = questions
    return body


def _mark_explicit_end(body: dict[str, object]) -> dict[str, object]:
    """Stage 5 and the last stage advance with no Confirm card. That end is named."""
    body["repost"] = False
    body.pop("card", None)
    body.pop("cardAction", None)
    body.pop("cardDigest", None)
    body["explicit_end"] = True
    return body


def _render_stage10_before_close(
    body: dict[str, object],
    essay_id: str,
    stage: str,
    genre: str | None,
    pointer: dict[str, Any],
    card_digest: str | None,
) -> dict[str, object] | None:
    """Write the graded sequence file before the pointer can close.

    A missing registration number or an empty footer keeps the Confirm card
    and leaves the sequence closed flag false. The tracking note is not
    recorded as final.
    """
    from essay_writer.late_chain import write_stage10

    rendered = write_stage10(essay_id)
    written = rendered.pop("sequence_written", False) is True and rendered.get("ok") is True
    if written:
        body["final_word"] = rendered
        delivery = rendered.get("delivery")
        if isinstance(delivery, dict):
            body["delivery"] = delivery
        return None
    reason_raw = rendered.get("reason")
    reason = reason_raw if isinstance(reason_raw, str) else ""
    if not reason.strip():
        reason = "The final Word file was not written. This step was not saved."
    code_raw = rendered.get("refused")
    code = code_raw if isinstance(code_raw, str) else ""
    if not code.strip():
        code = "stage"
    held = _reoffer_confirm(
        essay_id,
        stage,
        genre,
        pointer,
        card_digest,
        code=code.strip(),
        reason=reason.strip(),
    )
    held["closed"] = False
    held["ok"] = False
    return held


def _with_plan_encourage(
    body: dict[str, object],
    essay_id: str,
    stage: str,
    plan_text: str | None,
) -> dict[str, object]:
    """One plan question after Stage 3 is stored. Silence still leaves the save in place."""
    if stage != "3" or body.get("stored") is not True or not isinstance(plan_text, str):
        return body
    from essay_writer.encourage import attach_plan_encourage

    return attach_plan_encourage(body, essay_id, plan_text)


def _cache_approved_look(essay_id: str, stage: str, look: str) -> None:
    if stage == "5":
        return
    from essay_writer.specialists.grok_bot import remember_approved_look

    remember_approved_look(essay_id, look)


def _snapshot_stage_save(essay_id: str, stage: str, look: str | None, body: dict[str, object]) -> None:
    """Auto-snapshot after a stage save that stored. A refusal writes no snapshot."""
    if body.get("stored") is not True:
        return
    from essay_writer.pack_backup import snapshot_after_stage_save

    snapshot_after_stage_save(essay_id, stage, look if isinstance(look, str) else "")


def _commit_with_next_card(
    body: dict[str, object],
    essay_id: str,
    stage: str,
    genre: str | None,
    pointer: dict[str, Any],
    updated: dict[str, object],
    note,
    note_text: str,
    following: str | None,
    card_digest: str | None,
    plan_text: str | None = None,
    *,
    approved_look: str | None = None,
) -> dict[str, object]:
    """One write advances the pointer and stores the next waiting card.

    A stage that expects a card and cannot mint one does not write. Stage 5
    and the last stage write the advance with no card, and say so.
    """
    if isinstance(approved_look, str) and approved_look.strip():
        _cache_approved_look(essay_id, stage, approved_look)
    if stage == "10":
        held = _render_stage10_before_close(body, essay_id, stage, genre, pointer, card_digest)
        if held is not None:
            return held
    opened: dict[str, object] | None = None
    fields: dict[str, object] | None = None
    pending_next = _pending_inherited(essay_id, following)
    # A copied stage 2 or 3 names the parent save. Confirm waits for revise or re-lock.
    expects_card = _expects_next_card(following) and pending_next is None
    if expects_card:
        opened = _draft_next_card(essay_id, following or "")
        if isinstance(opened, dict):
            fields = _next_card_fields(opened, essay_id, following or "")
        if fields is None or opened is None:
            return _hold_confirm(
                essay_id,
                stage,
                genre,
                pointer,
                card_digest,
                opened if isinstance(opened, dict) else None,
                following or "",
            )
        updated["waiting_stage"] = following
        updated["waiting_digest"] = fields["cardDigest"]
    else:
        updated["waiting_stage"] = None
        updated["waiting_digest"] = None
    stored = _commit_pointer(essay_id, pointer, updated, note=note, note_text=note_text)
    if stored is None:
        return _pointer_lost(essay_id, stage, genre)
    updated = stored
    body["wrote"] = True
    body["stored"] = True
    body["advanced"] = following is not None
    body["closed"] = following is None
    body["digest"] = card_digest
    body["tracking_path"] = relative(note)
    body["current"] = updated["current"]
    from essay_writer.specialists.grok_bot import saved_next

    if following:
        body["next"] = saved_next(following, stage_title(following, genre))
    else:
        body["next"] = "Keep a copy. This tool does not submit."
    from essay_writer.late_chain import finish_stage_reply

    finished = finish_stage_reply(
        body,
        essay_id,
        stage,
        armed=updated.get("chain_armed") is True,
    )
    if finished.get("delivery_speech") == "4b" and isinstance(finished.get("next"), str):
        from essay_writer.specialists.grok_bot import critical_reviews_delivery_next

        finished["next"] = critical_reviews_delivery_next(finished["next"])
        finished.pop("delivery_speech", None)
    if fields is not None and opened is not None:
        finished = _attach_minted_card(finished, opened, fields)
    elif pending_next is not None and following:
        finished = _name_inherited_lock(finished, essay_id, following, pending_next)
    else:
        finished = _mark_explicit_end(finished)
    finished = _with_plan_encourage(finished, essay_id, stage, plan_text)
    _snapshot_stage_save(
        essay_id,
        stage,
        approved_look if isinstance(approved_look, str) else "",
        finished,
    )
    return finished


def render_tracking(
    stage: str,
    *,
    status: str,
    look: str,
    genre: str | None = None,
    essay_id: str | None = None,
) -> str:
    """Markdown from that stage's guidance, plus the working or final look."""
    item = stage_settings(stage, genre)
    title = stage_title(stage, genre)
    body = look if look else item["prompt_overlay"]
    heading = "Final look" if status == "final" else "Working look"
    sequence_line = f"Sequence id: {essay_id}\n\n" if essay_id else ""
    return (
        f"# Stage {stage} — {title}\n\n"
        f"{sequence_line}"
        f"Status: {status}\n\n"
        f"{item['rules']}\n\n"
        f"## {heading}\n\n"
        f"{body}\n"
    )


def _payload(essay_id: str, stage: str, look: str) -> dict[str, object]:
    return {"essay_id": essay_id, "stage": stage, "look": look}


_CARD_FIELDS = ("master", "namedFolder", "answers", "edited", "webCheck", "heldFile")


def _replay_confirm_card(
    essay_id: str,
    stage: str,
    genre: str | None,
    pointer: dict[str, Any],
    card_digest: str | None,
) -> dict[str, object] | None:
    """The waiting Confirm card. Typed Confirm, yes, or ok shows it again."""
    record = _card_record(essay_id, stage, card_digest)
    if record is None:
        record = _card_record(essay_id, stage, _waiting_digest(pointer, stage))
    if record is None:
        record = latest_draft(essay_id, TOOL, stage=stage)
    if record is None:
        return None
    digest = record.get("digest")
    if not isinstance(digest, str) or not digest:
        return None
    from essay_writer.specialists.grok_bot import card_next, confirm_reply_fields
    from essay_writer.spine import stage_confirm_card

    revisit = _revisit_window(pointer) and stage in {"2", "3"}
    line = _confirm_line(stage, genre, revisit=revisit)
    title = stage_title(stage, genre)
    card = stage_confirm_card(
        essay_id,
        stage,
        digest,
        line,
        stage_title=title,
    )
    return {
        "card": card,
        "digest": digest,
        **confirm_reply_fields(digest),
        "next": card_next(stage, title),
        "confirm_line": line,
        "stored": False,
        "advanced": False,
        "wrote": False,
    }


def _card_records_no_change(record: dict[str, object] | None) -> bool:
    """True when this waiting card already recorded a no-change answer."""
    if not isinstance(record, dict):
        return False
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return False
    from essay_writer.stage7 import answers_mean_no_change

    for key in ("answers", "look"):
        value = payload.get(key)
        if isinstance(value, str) and answers_mean_no_change(value):
            return True
    return False


def _stage7_skip_reply(
    essay_id: str,
    stage: str,
    genre: str | None,
    pointer: dict[str, Any],
    confirm_phase: str,
) -> dict[str, object]:
    """A skip does not save. The same reply asks the questions again."""
    from essay_writer.specialists.grok_bot import stage7_lead
    from essay_writer.stage7 import load_stage7, note_questions, questions_for

    record = load_stage7(essay_id)
    if not record.get("asked"):
        note_questions(essay_id)
        record = load_stage7(essay_id)
    questions = list(record.get("questions") or questions_for(essay_id))
    title = stage_title(stage, genre)
    reason = "Skipping the questions does not save this step. Answer them in this chat."
    lead = stage7_lead(questions, title)
    return refuse(
        "stage",
        reason,
        next=f"{reason} {lead}",
        questions=questions,
        stored=False,
        wrote=False,
        advanced=False,
        waiting_confirm=True,
        current=pointer["current"],
        stage=stage,
        confirmPhase=confirm_phase,
    )


def _reoffer_confirm(
    essay_id: str,
    stage: str,
    genre: str | None,
    pointer: dict[str, Any],
    card_digest: str | None,
    *,
    reason: str,
    code: str = "confirm-card",
) -> dict[str, object]:
    """A confirm that does not save still leaves the Confirm card, or a next ask."""
    from essay_writer.specialists.grok_bot import missing_confirm_next

    replay = _replay_confirm_card(essay_id, stage, genre, pointer, card_digest)
    extra: dict[str, object] = {
        "stage": stage,
        "confirmPhase": CONFIRM,
        "current": pointer["current"],
        "waiting_confirm": True,
        "stored": False,
        "advanced": False,
        "wrote": False,
    }
    if replay:
        extra.update(replay)
    else:
        extra["next"] = missing_confirm_next(stage, stage_title(stage, genre))
    return refuse(code, reason, **extra)


def _card_record(essay_id: str, stage: str, card_digest: str | None):
    """Draft named by the Confirm card, when it is this stage's draft."""
    if not isinstance(card_digest, str) or not card_digest.strip():
        return None
    record = load_draft_by_digest(essay_id, TOOL, card_digest.strip())
    if record is None:
        return None
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return None
    if payload.get("essay_id") != essay_id or payload.get("stage") != stage:
        return None
    return record


def _hydrate_card(
    text: str,
    look: str | None,
    record: dict[str, Any] | None,
    fields: dict[str, object],
) -> tuple[str, dict[str, Any]]:
    """Fill omitted Confirm fields from the card draft. A different look stays a new payload."""
    if record is None:
        return text, fields
    payload = record["payload"]
    omitted = look is None or (isinstance(look, str) and not look.strip())
    saved_look = payload.get("look")
    if omitted and isinstance(saved_look, str):
        text = saved_look.strip()
    filled = dict(fields)
    for key in _CARD_FIELDS:
        if filled.get(key) is None and key in payload:
            filled[key] = payload[key]
    return text, filled


def _grant_room(essay_id: str, pointer: dict[str, Any], stage: str) -> dict[str, object] | None:
    """Record this stage's press without rewriting current or saved from a stale read."""
    proposed = dict(pointer)
    proposed["room_grant"] = stage
    proposed["room_lock"] = False
    return _commit_pointer(essay_id, pointer, proposed)


def _superseded_card(
    essay_id: str,
    stage: str,
    pointer: dict[str, Any],
    card_digest: str | None,
) -> bool:
    """True when this card is an older draft of the same stage than the one waiting."""
    record = _card_record(essay_id, stage, card_digest)
    if record is None:
        return False
    card = record.get("digest")
    waiting = _waiting_digest(pointer, stage)
    if waiting is not None:
        return card != waiting
    payload = record.get("payload")
    look = payload.get("look") if isinstance(payload, dict) else None
    note_look = _note_look(essay_id, stage)
    if isinstance(note_look, str) and isinstance(look, str) and look != note_look:
        return True
    latest = latest_draft(essay_id, TOOL, stage=stage)
    if isinstance(latest, dict) and latest.get("digest") != card:
        return True
    return False


def _older_card(
    essay_id: str,
    stage: str,
    genre: str | None,
    pointer: dict[str, Any],
) -> dict[str, object]:
    return _reoffer_confirm(
        essay_id,
        stage,
        genre,
        pointer,
        None,
        code="confirm",
        reason=(
            "That card is an older draft of this step. "
            "Show the latest draft again before it can be saved."
        ),
    )


def _stale_confirm_body(
    essay_id: str,
    stage: str,
    pointer: dict[str, Any],
    digest: object,
    look_text: str,
) -> bool:
    """True unless this confirm is the waiting draft and that draft's look."""
    waiting = _waiting_digest(pointer, stage)
    if waiting is not None:
        if digest != waiting:
            return True
        record = load_draft_by_digest(essay_id, TOOL, waiting)
        payload = record.get("payload") if isinstance(record, dict) else None
        if not isinstance(payload, dict):
            return True
        return payload.get("look") != look_text
    note_look = _note_look(essay_id, stage)
    if isinstance(note_look, str) and note_look != look_text:
        return True
    latest = latest_draft(essay_id, TOOL, stage=stage)
    if not isinstance(latest, dict) or latest.get("digest") != digest:
        return True
    payload = latest.get("payload")
    if not isinstance(payload, dict):
        return True
    return payload.get("look") != look_text


def _revisit_window(pointer: dict[str, Any]) -> bool:
    """After 4b is saved and before stage 5 is saved, the plan may be opened again."""
    return (
        pointer.get("closed") is not True
        and pointer.get("current") == "5"
        and "4b" in pointer.get("saved", [])
        and "5" not in pointer.get("saved", [])
    )


def _stage_refusal(pointer: Pointer, stage: str, genre: str | None) -> dict[str, object] | None:
    current = pointer["current"]
    if pointer.get("closed"):
        return refuse("stage", "The last stage is already saved. This tool does not submit.")
    window = _revisit_window(cast(dict[str, Any], pointer))
    if window and stage in {"2", "3"}:
        if stage == "3" and pointer.get("revisit_open") == "2":
            if genre == "report":
                reason = "Save purpose and scope first. Then save the plan before the first draft."
            elif genre == "essay":
                reason = "Save the thesis first. Then save the plan before the first draft."
            elif genre == "diary":
                reason = "Save the entries first. Then save the plan before the first draft."
            else:
                reason = "Save the earlier lock first. Then save the plan before the first draft."
            return refuse("stage", reason)
        return None
    if stage == "5" and window and pointer.get("revisit_open"):
        return refuse(
            "stage",
            "Save the plan note first. The first draft waits until that save.",
        )
    if stage == "5" and window and pointer.get("revisit_after_lock"):
        return refuse(
            "stage",
            "Save the plan again before the first draft. The earlier lock changed.",
        )
    if stage in pointer["saved"]:
        return refuse(
            "stage",
            f"Stage {stage} is already saved. The current stage is {current}.",
        )
    if stage != current:
        return refuse(
            "stage",
            f"The current stage is {current}. Finish that step in this chat before stage {stage}.",
        )
    return None


def _stage5_held(
    pointer: dict[str, Any],
    gate: dict[str, Any],
    blockers: list[dict[str, str]],
) -> dict[str, object]:
    """A failed north-star or a notes-shaped draft does not store and does not advance."""
    from essay_writer.late_chain import stage5_chat_line

    if blockers:
        code = blockers[0].get("code") or "argument"
        reason = blockers[0].get("reason") or "Stage 5 is the report or essay argument."
    else:
        code = "north-star"
        reason = gate.get("reason") or "The first draft does not pass the assignment check yet."
    line = stage5_chat_line(reason, "The first draft is not ready yet.")
    return refuse(
        code,
        reason,
        advanced=False,
        current=pointer["current"],
        north_star=gate,
        blockers=blockers,
        quiet=True,
        step="5",
        checklist_in_chat=False,
        chat=line,
        next=line,
        confirm_line=line,
    )


def _confirm_line(stage: str, genre: str | None, *, revisit: bool = False) -> str:
    from essay_writer.spine import save_line

    return save_line(stage, genre, revisit=revisit)


def in_first_draft(essay_id: str) -> bool:
    """True after 4b is saved and before stage 5 is saved."""
    pointer = load_pointer(essay_id)
    return pointer.get("current") == "5" and "5" not in pointer.get("saved", [])
