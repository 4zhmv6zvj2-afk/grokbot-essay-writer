"""Tracking note for each writing stage.

The note lives at Essay-writer/<module>/sequences/<n>/tracking/<stage>.md.
It is that stage's guidance. Draft writes the working note and does not
advance. A card pick saves the final look in the same file, then
tracking/stage.json moves to the next stage. Stage 5 stores on the
draft and starts stage 6 when the north-star gate passes and the look
is the report or essay argument. A failed gate does not store. Stage 10
does not submit.

After stage 4b is saved and before stage 5 is saved, stages 2 and 3
may be saved again. Stage 2 is only for a broken lock. A plan change
stays on stage 3. The first draft waits until that save. A broken
lock is saved on stage 2, then the plan is saved again on stage 3.

Cursor and Grok Build both read the path and the rules from
essay_writer.stage_llm.stage_settings. This module is the only writer.
The note and the pointer fields that name it are one commit under the
stage lock. A confirm that expects a next card stores that card's waiting
digest in the same write as the advance. If that card cannot be minted,
the write does not happen and the waiting card stays. Stage 5 and the
last stage name an advance with no card. A newer current or saved list
is left in place.
"""

from __future__ import annotations

import contextvars
import fcntl
import json
import os
import threading
from contextlib import contextmanager
from typing import Any

from essay_writer.confirm import (
    CONFIRM,
    DRAFT,
    confirm_ready,
    latest_draft,
    load_draft_by_digest,
    phase_refusal,
    refuse,
    save_draft,
)
from essay_writer.known_paths import guard_write_door, refuse_repo_write
from essay_writer.paths import relative, sequence_write_error, work_dir
from essay_writer.stage_llm import (
    POINTER_FILE,
    RULES_SOURCE,
    STAGE_ORDER,
    brief_genre,
    next_stage,
    stage_settings,
    stage_title,
    tracking_file,
)
from essay_writer.student_voice import student_surface_hits

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


def _pointer_text(pointer: dict[str, object]) -> str:
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
    _atomic(root / POINTER_FILE, _pointer_text(pointer))
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
        _atomic(path, _pointer_text(blank_pointer()))
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
    _atomic(pointer_path, _pointer_text(data))


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


def _room_state(pointer: dict[str, object]) -> dict[str, object]:
    """The room press still on the pointer. A card tap leaves both empty."""
    grant = pointer.get("room_grant")
    if grant not in STAGE_ORDER:
        grant = None
    return {"room_grant": grant, "room_lock": pointer.get("room_lock") is True}


def _room_after_card_save(pointer: dict[str, object], stage: str) -> dict[str, object]:
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


def _room_blocks(pointer: dict[str, object], stage: str) -> bool:
    """True when a room press for another stage, or a used press, is not this stage's Confirm."""
    state = _room_state(pointer)
    if state["room_lock"] and state["room_grant"] != stage:
        return True
    return state["room_grant"] is not None and state["room_grant"] != stage


def _waiting_pair(pointer: dict[str, object]) -> tuple[str | None, str | None]:
    stage = pointer.get("waiting_stage")
    digest = pointer.get("waiting_digest")
    if stage not in STAGE_ORDER or not isinstance(digest, str) or len(digest) != 64:
        return None, None
    return stage, digest


def _waiting_digest(pointer: dict[str, object], stage: str) -> str | None:
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


def _revision(pointer: dict[str, object]) -> int:
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
        _atomic(_commit_path(essay_id), _pointer_text(record))
        _apply_commit(work_dir(essay_id), record)
        return stored


def _pointer_lost(essay_id: str, stage: str, genre: str | None) -> dict[str, object]:
    """The pointer moved after this call read it. The newer pointer stays."""
    fresh = load_pointer(essay_id)
    blocked = _stage_refusal(fresh, stage, genre)
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
    pointer: dict[str, object],
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
    pointer: dict[str, object],
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
    pointer: dict[str, object],
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
    pointer: dict[str, object],
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
    pointer: dict[str, object],
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
    pointer: dict[str, object],
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


def _grant_room(essay_id: str, pointer: dict[str, object], stage: str) -> dict[str, object] | None:
    """Record this stage's press without rewriting current or saved from a stale read."""
    proposed = dict(pointer)
    proposed["room_grant"] = stage
    proposed["room_lock"] = False
    return _commit_pointer(essay_id, pointer, proposed)


def _superseded_card(
    essay_id: str,
    stage: str,
    pointer: dict[str, object],
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
    pointer: dict[str, object],
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
    pointer: dict[str, object],
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


def _stage_refusal(pointer: dict[str, Any], stage: str, genre: str | None) -> dict[str, object] | None:
    current = pointer["current"]
    if pointer.get("closed"):
        return refuse("stage", "The last stage is already saved. This tool does not submit.")
    window = _revisit_window(pointer)
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
    pointer: dict[str, object],
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


def _late_armed(pointer: dict[str, object], stage: str, essay_id: str) -> bool:
    from essay_writer.stage7 import stage7_edited

    armed = pointer.get("chain_armed") is True
    if stage == "7" and stage7_edited(essay_id):
        armed = True
    return armed


def _open_stage6(
    body: dict[str, object],
    essay_id: str,
    *,
    master: str | None,
    named_folder: str | None,
) -> dict[str, object]:
    """Stage 6 fields for the reply. This does not write stage 6's note."""
    from essay_writer.late_chain import stage6_fields

    fields = stage6_fields(essay_id, master=master, named_folder=named_folder)
    body["started"] = {
        "stage": "6",
        "stage_title": stage_title("6", brief_genre(essay_id)),
        "place": fields["place"],
        "master_ask": fields["master_ask"],
        "choices": fields["choices"],
        "expected_draft": fields["expected_draft"],
        "chain_started": False,
    }
    body.pop("card", None)
    return body


def _attach_outline_report(
    body: dict[str, object], essay_id: str, stage: str
) -> None:
    """Name the student outline the draft follows. Stages 3 to 6 only."""
    if stage not in {"3", "4a", "4b", "5", "6"}:
        return
    from essay_writer.outline_primary import outline_speech, read_outline

    outline = read_outline(essay_id)
    if outline is None:
        return
    body["student_outline"] = {
        "headings": list(outline.get("headings") or []),
        "files": list(outline.get("files") or []),
    }
    line = outline_speech(essay_id)
    if line:
        body["student_outline_line"] = line


def _attach_short_report(body: dict[str, object], report: dict[str, object] | None) -> None:
    """Say the cite length the student asked for. An untouched body stays quiet."""
    if not isinstance(report, dict):
        return
    limit = report.get("limit")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        body.pop("cite_short", None)
        return
    raw_cut = report.get("cut")
    cut = raw_cut if isinstance(raw_cut, list) else []
    if report.get("applied") is not True and not cut and report.get("asked") is not True:
        body.pop("cite_short", None)
        return
    body["cite_short"] = {"limit": limit, "cut": len(cut)}
    from essay_writer.cite_fit import in_line
    from essay_writer.short_cites import short_line

    body["cite_short_line"] = short_line(limit)
    in_line(body, "cite_short_line")


def _attach_cite_report(body: dict[str, object], report: dict[str, object] | None) -> None:
    """Ask and held cites from the shared writer gate. Empty stays off the reply."""
    if not isinstance(report, dict):
        return
    held = report.get("held")
    if isinstance(held, list) and held:
        body["cite_held"] = held
    else:
        body.pop("cite_held", None)
    ask = report.get("ask")
    if isinstance(ask, str) and ask.strip():
        body["cite_ask"] = ask
    else:
        body.pop("cite_ask", None)
    gap = report.get("gap")
    if isinstance(gap, str) and gap.strip():
        body["cite_gap"] = gap
    else:
        body.pop("cite_gap", None)


def _store_stage(
    body: dict[str, object],
    essay_id: str,
    stage: str,
    text: str,
    genre: str | None,
    pointer: dict[str, Any],
    note,
    *,
    digest: str,
    master: str | None,
    named_folder: str | None,
) -> dict[str, object]:
    """Store one stage that has no card between it and the next."""
    note_text = render_tracking(stage, status="final", look=text, genre=genre, essay_id=essay_id)
    rel = relative(note)
    saved = _saved_after_confirm(pointer, stage)
    files = dict(pointer["files"])
    files[stage] = rel
    following = next_stage(stage)
    updated = {
        "current": following if following else stage,
        "saved": saved,
        "files": files,
        "closed": following is None,
        "revisit_open": None,
        "revisit_after_lock": False,
        "chain_armed": _late_armed(pointer, stage, essay_id),
        "waiting_stage": None,
        "waiting_digest": None,
        **_room_state(pointer),
    }
    stored = _commit_pointer(essay_id, pointer, updated, note=note, note_text=note_text)
    if stored is None:
        return _pointer_lost(essay_id, stage, genre)
    updated = stored
    body["wrote"] = True
    body["stored"] = True
    body["advanced"] = following is not None
    body["closed"] = following is None
    body["digest"] = digest
    body["tracking_path"] = rel
    body["current"] = updated["current"]
    body.pop("card", None)
    from essay_writer.specialists.grok_bot import saved_next

    if following:
        body["next"] = saved_next(following, stage_title(following, genre))
    else:
        body["next"] = "Keep a copy. This tool does not submit."
    from essay_writer.late_chain import finish_stage_reply, quiet_stage5

    finished = finish_stage_reply(
        body,
        essay_id,
        stage,
        armed=updated.get("chain_armed") is True,
    )
    if stage == "5":
        finished = quiet_stage5(finished, essay_id)
    finished = _mark_explicit_end(finished)
    _snapshot_stage_save(essay_id, stage, text, finished)
    if following == "6":
        return _open_stage6(finished, essay_id, master=master, named_folder=named_folder)
    return finished


_MID_RUN_STAGES = frozenset({"4a", "4b", "5", "6", "7", "8", "9", "10"})


def _attach_mid_run(body: dict[str, Any], essay_id: str, stage: str) -> None:
    """Arm a mid session only when Cursor CLI or Grok Build actually starts.

    Stage 4b research is skipped only when every kept paper already has a
    critical note. Cursor and Grok Build share this decision.
    """
    if stage not in _MID_RUN_STAGES:
        return
    from essay_writer.cursor_office import start_4a_research, start_stage_mid
    from essay_writer.roll_forward import four_b_action

    if stage == "4b":
        action = four_b_action(essay_id)
        if action == "skip":
            body["roll_forward_4b"] = "skip"
            return
        if action == "research":
            body["roll_forward_4b"] = "research"
    if stage == "4a":
        started = start_4a_research(essay_id, launch=body.get("mid_office_launch"))
    else:
        started = start_stage_mid(essay_id, stage, launch=body.get("mid_office_launch"))
    if stage == "4a":
        host = body.get("mid_office_launch")
        if isinstance(host, dict):
            host["research"] = {
                "runner": started.get("runner", ""),
                "command": started.get("command", []),
                "started": started.get("started", False),
                "reason": started.get("reason", ""),
                "heartbeat_seconds": started.get("heartbeat_seconds"),
            }
    if started.get("status"):
        body["status"] = started["status"]
    if started.get("started"):
        body["mid_started"] = True


def _miss_record(body: dict[str, object]) -> dict[str, Any]:
    item: dict[str, object] = {"code": body.get("refused"), "reason": body.get("reason")}
    words = body.get("words")
    if isinstance(words, list) and words:
        item["words"] = list(words)
    return item


def _join_stage_misses(found: list[dict[str, Any]]) -> dict[str, Any]:
    """One refuse that names every current miss. A single miss keeps its own reply."""
    misses = [_miss_record(body) for body in found]
    reasons = [
        str(item["reason"])
        for item in misses
        if isinstance(item.get("reason"), str) and item["reason"]
    ]
    words: list[str] = []
    for item in misses:
        for word in item.get("words") or []:
            if word not in words:
                words.append(word)
    extra: dict[str, Any] = {"misses": misses, "advanced": False}
    if words:
        extra["words"] = words
    return refuse("misses", " ".join(reasons), **extra)


def _collect_stage_misses(
    essay_id: str,
    stage: str,
    confirmPhase: str | None,
    text: str,
    pointer: dict[str, Any],
    *,
    minting: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Every current save block. One code returns that reply unchanged."""
    found: list[dict[str, Any]] = []

    def add(body: dict[str, Any] | None) -> None:
        if not isinstance(body, dict):
            return
        code = body.get("refused")
        if not isinstance(code, str) or any(item.get("refused") == code for item in found):
            return
        found.append(body)

    if not minting and student_surface_hits(text):
        add(
            refuse(
                "house-jargon",
                "That note uses a label that stays off the stage file. Use plain words.",
                words=student_surface_hits(text),
            )
        )
    if not minting:
        from essay_writer.brief_contract import stage_contract_refusal

        blocked_contract = stage_contract_refusal(essay_id, stage, text)
        if blocked_contract:
            blocked_contract["stage"] = stage
            blocked_contract["confirmPhase"] = confirmPhase
            add(blocked_contract)
    from essay_writer.specialists.grok_bot import basics_pass_block, delivery_file_only
    from essay_writer.spine import gate_save, north_star

    if stage != "5" and delivery_file_only(text):
        blocked_pass = basics_pass_block(essay_id, text)
        if blocked_pass:
            blocked_pass["stage"] = stage
            blocked_pass["confirmPhase"] = confirmPhase
            add(blocked_pass)
    stage5_gate = None
    if stage == "5":
        from essay_writer.draft_from_review import stage5_draft_blockers

        stage5_gate = north_star(essay_id, text)
        stage5_blockers = stage5_draft_blockers(essay_id, text)
        if stage5_gate.get("passed") is not True or stage5_blockers:
            add(_stage5_held(pointer, stage5_gate, stage5_blockers))
    else:
        add(gate_save(essay_id, text))
    if stage != "5":
        blocked_pass = basics_pass_block(essay_id, text)
        if blocked_pass:
            blocked_pass["stage"] = stage
            blocked_pass["confirmPhase"] = confirmPhase
            add(blocked_pass)
    if not found:
        return None, stage5_gate
    if len(found) == 1:
        return found[0], stage5_gate
    return _join_stage_misses(found), stage5_gate


def _inherited_lock_keep(
    essay_id: str,
    stage: str,
    genre: str | None,
    pointer: dict[str, Any],
    row: dict[str, Any],
) -> dict[str, Any]:
    """Keep continues the parent save without showing Confirm again."""
    from essay_writer.fo_chat_locks import _mark_lock_resolved
    from essay_writer.specialists.grok_bot import CARD_CONFIRM

    text = str(row.get("look") or "").strip()
    if not text:
        return refuse("lock-choice", "The inherited lock is empty. Revise instead.")
    if pointer.get("waiting_stage") == stage:
        cleared = dict(pointer)
        cleared["waiting_stage"] = None
        cleared["waiting_digest"] = None
        refreshed = _commit_pointer(essay_id, pointer, cleared, note=None, note_text=None)
        if refreshed is not None:
            pointer = refreshed
    blocked_save, _stage5_gate = _collect_stage_misses(
        essay_id,
        stage,
        CONFIRM,
        text,
        pointer,
        minting=False,
    )
    if blocked_save is not None:
        return blocked_save
    payload = _payload(essay_id, stage, text)
    fingerprint = {"stage": stage, "inherited_keep": True}
    digest = save_draft(essay_id, TOOL, payload, fingerprint)
    ready = confirm_ready(essay_id, TOOL, payload, fingerprint)
    if ready.get("ok") is False:
        return ready
    _mark_lock_resolved(essay_id, stage)
    token = _INHERITED_KEEP.set(True)
    try:
        saved = essay_stage(
            essay_id,
            stage,
            CONFIRM,
            text,
            cardAction=CARD_CONFIRM,
            cardDigest=digest if isinstance(digest, str) else ready.get("digest"),
        )
    finally:
        _INHERITED_KEEP.reset(token)
    if isinstance(saved, dict):
        saved["inherited_keep"] = True
        saved["prior_saved_lock"] = {
            "stage": row.get("stage"),
            "title": row.get("title"),
            "essay_id": row.get("essay_id"),
        }
        if saved.get("stored") is True:
            saved.pop("card", None)
            saved.pop("cardAction", None)
            saved.pop("cardDigest", None)
            saved["waiting_confirm"] = False
    return saved


def essay_stage(
    essay_id: str,
    stage: str,
    confirmPhase: str | None = None,
    look: str | None = None,
    *,
    master: str | None = None,
    namedFolder: str | None = None,
    answers: str | None = None,
    edited: str | None = None,
    webCheck: dict[str, Any] | None = None,
    heldFile: str | None = None,
    cardAction: str | None = None,
    cardDigest: str | None = None,
    card_only: bool = False,
    encourageChoice: str | None = None,
    paperChoice: dict[str, Any] | None = None,
    lockChoice: str | None = None,
) -> dict[str, Any]:
    """A card saves the final look. Stage 5 starts stage 6."""
    minting = _MINTING.get()
    id_error = sequence_write_error(essay_id)
    if id_error:
        return refuse("essay-id", id_error)
    if encourageChoice is not None:
        from essay_writer.encourage import answer_encourage

        return answer_encourage(essay_id, encourageChoice)
    if paperChoice is not None:
        from essay_writer.roll_forward import choose_paper

        return choose_paper(essay_id, paperChoice)
    from essay_writer.fo_chat_locks import (
        inherited_lock_pending,
        lock_choice_refusal,
        prior_saved_lock_ask,
    )

    refused_choice = lock_choice_refusal(lockChoice)
    if refused_choice is not None:
        return refused_choice
    phase = phase_refusal(confirmPhase)
    if phase:
        return phase

    blocked = guard_write_door(work_dir(essay_id))
    if blocked:
        return blocked
    if stage not in STAGE_ORDER:
        return refuse(
            "stage",
            "stage must be 1, 2, 3, 4a, 4b, 5, 6, 7, 8, 9, or 10.",
        )
    if look is None:
        text = ""
    elif isinstance(look, str):
        text = look.strip()
    else:
        return refuse("stage", "look must be plain text.")
    pointer = load_pointer(essay_id)
    genre = brief_genre(essay_id)
    pending_lock = inherited_lock_pending(essay_id, stage)
    blocked = _stage_refusal(pointer, stage, genre)
    if blocked and not (minting and _mint_stage_allowed(pointer, stage)):
        if confirmPhase == CONFIRM:
            return _confirm_blocked(essay_id, pointer, stage, genre, blocked)
        return blocked
    if lockChoice == "keep" and pending_lock is not None:
        return _inherited_lock_keep(essay_id, stage, genre, pointer, pending_lock)
    if lockChoice in {"revise", "relock"} and pending_lock is not None:
        from essay_writer.fo_chat_locks import _mark_lock_resolved

        inherited = str(pending_lock.get("look") or "").strip()
        if inherited:
            if not text.strip():
                text = inherited
            elif inherited.casefold() not in text.casefold():
                text = f"{inherited}\n{text}".strip()
        # The card minted before this choice does not carry the parent look.
        # Revise and re-lock open Confirm. They do not save that older card.
        if confirmPhase == CONFIRM and inherited:
            record = _card_record(essay_id, stage, cardDigest)
            payload = record.get("payload") if isinstance(record, dict) else None
            card_look = payload.get("look") if isinstance(payload, dict) else None
            if not isinstance(card_look, str) or inherited.casefold() not in card_look.casefold():
                confirmPhase = DRAFT
                cardAction = None
                cardDigest = None
                look = text
        _mark_lock_resolved(essay_id, stage)
    elif (
        pending_lock is not None
        and confirmPhase in {DRAFT, CONFIRM}
        and not minting
        and lockChoice is None
        and not card_only
        and not _INHERITED_KEEP.get()
    ):
        return prior_saved_lock_ask(essay_id, stage, pending_lock)
    from essay_writer.spine import accept_stage_card, advances_without_confirm

    auto_next = advances_without_confirm(stage)
    if confirmPhase == CONFIRM and auto_next:
        return refuse(
            "confirm-card",
            "This step moves on when the draft is stored. There is no save-card between this step and the next.",
            advanced=False,
            current=pointer["current"],
            next=(
                "This step moves on when the draft is stored. "
                "There is no Confirm card between this step and the next."
            ),
            waiting_confirm=False,
        )
    if (
        confirmPhase == CONFIRM
        and not auto_next
        and not minting
        and _waiting_digest(pointer, stage) is None
        and latest_draft(essay_id, TOOL, stage=stage) is None
    ):
        return {
            "ok": True,
            "essay_id": essay_id,
            "stage": stage,
            "confirmPhase": confirmPhase,
            "noop": True,
            "wrote": False,
            "stored": False,
            "advanced": False,
            "current": pointer["current"],
            "closed": False,
            "submitted": False,
        }
    if confirmPhase == CONFIRM:
        from essay_writer.specialists.grok_bot import (
            CARD_CONFIRM,
            press_confirm_stage,
            typed_save_word,
        )
        from essay_writer.stage7 import answers_mean_no_change, answers_mean_skip

        named = press_confirm_stage(cardAction)
        if named is None:
            named = press_confirm_stage(look)
        press_target = None
        if named is not None:
            press_target = stage if named == "" else named
        card_record = _card_record(essay_id, stage, cardDigest)
        card_matches = cardAction == CARD_CONFIRM and card_record is not None
        probe = look if isinstance(look, str) else ""
        answer_text = answers if isinstance(answers, str) else ""
        if stage == "7" and (answers_mean_skip(probe) or answers_mean_skip(answer_text)):
            return _stage7_skip_reply(essay_id, stage, genre, pointer, confirmPhase)
        # "All fine" is the answer. A waiting card copied into that same call does not save.
        stage7_no_change = stage == "7" and (
            answers_mean_no_change(probe) or answers_mean_no_change(answer_text)
        )
        no_card_no_change = (not card_matches) and (
            answers_mean_no_change(probe) or answers_mean_no_change(answer_text)
        )
        if stage7_no_change or no_card_no_change:
            # "All fine" opens the Confirm card. It does not save on this call.
            confirmPhase = DRAFT
            if answers is None and answers_mean_no_change(probe):
                answers = probe
            waiting = latest_draft(essay_id, TOOL, stage=stage)
            saved_look = None
            if isinstance(waiting, dict):
                payload = waiting.get("payload")
                if isinstance(payload, dict) and isinstance(payload.get("look"), str):
                    saved_look = payload["look"]
            if isinstance(saved_look, str) and saved_look.strip() and not answers_mean_no_change(saved_look):
                text = saved_look.strip()
                look = text
        else:
            if not _INHERITED_KEEP.get() and _superseded_card(
                essay_id, stage, pointer, cardDigest
            ):
                return _older_card(essay_id, stage, genre, pointer)
            if press_target is not None and press_target != stage:
                return _reoffer_confirm(
                    essay_id,
                    stage,
                    genre,
                    pointer,
                    cardDigest,
                    reason=(
                        f"That press is for Stage {press_target} only. "
                        f"It does not save Stage {stage}. "
                        f"Open the Confirm card for Stage {stage}."
                    ),
                )
            granted_here = False
            if press_target == stage and card_matches:
                # One press plus the waiting card saves this stage only.
                stored_room = _grant_room(essay_id, pointer, stage)
                if stored_room is None:
                    return _pointer_lost(essay_id, stage, genre)
                pointer = stored_room
                look = None
                text = ""
                granted_here = True
            elif press_target == stage:
                stored_room = _grant_room(essay_id, pointer, stage)
                if stored_room is None:
                    return _pointer_lost(essay_id, stage, genre)
                pointer = stored_room
                return _reoffer_confirm(
                    essay_id,
                    stage,
                    genre,
                    pointer,
                    cardDigest,
                    reason="A typed reply does not save this step. Open the Confirm card in this reply.",
                )
            if not card_matches or (_room_blocks(pointer, stage) and not granted_here):
                if not card_matches:
                    picked_card = accept_stage_card(cardAction)
                    if picked_card:
                        return _reoffer_confirm(
                            essay_id,
                            stage,
                            genre,
                            pointer,
                            cardDigest,
                            reason=str(
                                picked_card.get("reason")
                                or "A typed reply does not save this step. Open the Confirm card in this reply."
                            ),
                        )
                if _room_blocks(pointer, stage):
                    return _reoffer_confirm(
                        essay_id,
                        stage,
                        genre,
                        pointer,
                        cardDigest,
                        reason=(
                            f"Stage {stage} needs its own Confirm card. "
                            "The earlier card does not save this stage."
                        ),
                    )
            if typed_save_word(look):
                look = None
                text = ""
            omitted_look = look is None or (isinstance(look, str) and not look.strip())
            if card_record is None and omitted_look:
                return _reoffer_confirm(
                    essay_id,
                    stage,
                    genre,
                    pointer,
                    cardDigest,
                    reason="That card does not match this draft. Show the draft card again.",
                )
        if confirmPhase == CONFIRM:
            if card_matches:
                answers = None
                edited = None
                webCheck = None
                look = None
                text = ""
            text, filled = _hydrate_card(
                text,
                look,
                card_record,
                {
                    "master": master,
                    "namedFolder": namedFolder,
                    "answers": answers,
                    "edited": edited,
                    "webCheck": webCheck,
                    "heldFile": heldFile,
                },
            )
            master = filled["master"]
            namedFolder = filled["namedFolder"]
            answers = filled["answers"]
            edited = filled["edited"]
            webCheck = filled["webCheck"]
            heldFile = filled["heldFile"]
    if stage == "7" and confirmPhase == DRAFT:
        from essay_writer.stage7 import answers_mean_skip as _skip_probe

        if _skip_probe(text) or _skip_probe(answers if isinstance(answers, str) else None):
            return _stage7_skip_reply(essay_id, stage, genre, pointer, confirmPhase)
    from essay_writer.specialists.grok_bot import maybe_seed_basics_on_draft

    text, basics_seeded = maybe_seed_basics_on_draft(
        essay_id,
        stage,
        confirmPhase,
        text,
        minting=minting,
    )
    from essay_writer.cite_open import cite_look
    from essay_writer.short_cites import apply_short_cite_request
    from essay_writer.specialists.writer import BODY_CITE_STAGES, land_body_cites

    text = cite_look(essay_id, text)
    # A student ask for one or two sentences per cited point is read before the
    # gate, so a shortened stretch still has to pass claim-fit on the way out.
    short_report = apply_short_cite_request(
        essay_id,
        text,
        answers=answers if isinstance(answers, str) else None,
        edited=edited if isinstance(edited, str) else None,
        rewrite=stage in BODY_CITE_STAGES,
    )
    text = short_report["text"]
    if isinstance(edited, str):
        edited = short_report["edited"]
    cite_report = None
    if stage in BODY_CITE_STAGES:
        cite_report = land_body_cites(
            essay_id,
            stage,
            text,
            answers=answers if isinstance(answers, str) else None,
            edited=edited if isinstance(edited, str) else None,
        )
        text = cite_report["text"]
        if isinstance(edited, str):
            edited = cite_report["edited"]
        from essay_writer.outline_primary import SHORT_CITE_LIMIT, weave_short_cites

        # The student's outline is the structure, so each woven cite stays
        # short here too: no mini review is built around a gathered paper.
        text, woven = weave_short_cites(essay_id, text, SHORT_CITE_LIMIT)
        if woven:
            short_report = {
                **short_report,
                "limit": SHORT_CITE_LIMIT,
                "applied": True,
                "cut": list(short_report.get("cut") or []) + woven,
            }
    # A waiting-card mint is not the student's answer. Part names, Entry N,
    # and house words are checked when the student later writes that stage.
    blocked_save, stage5_gate = _collect_stage_misses(
        essay_id,
        stage,
        confirmPhase,
        text,
        pointer,
        minting=minting,
    )
    if blocked_save is not None:
        if basics_seeded:
            blocked_save["basics_seeded"] = True
        return blocked_save
    if basics_seeded:
        look = text
    revisit = _revisit_window(pointer) and stage in {"2", "3"}
    if revisit and not text:
        return refuse(
            "stage",
            "Write what changed, or that the plan still holds, and which gathered source shows it.",
        )
    item = stage_settings(stage, genre)
    payload = _payload(essay_id, stage, text)
    for key, value in (
        ("master", master),
        ("namedFolder", namedFolder),
        ("answers", answers),
        ("edited", edited),
        ("webCheck", webCheck),
        ("heldFile", heldFile),
    ):
        if value is not None:
            payload[key] = value
    fingerprint = (
        {"stage": stage, "inherited_keep": True}
        if _INHERITED_KEEP.get()
        else {"stage": stage}
    )
    note = _note_path(essay_id, stage)
    body: dict[str, Any] = {
        "ok": True,
        "essay_id": essay_id,
        "stage": stage,
        "stage_title": stage_title(stage, genre),
        "confirmPhase": confirmPhase,
        "rules": item["rules"],
        "source": RULES_SOURCE,
        "tracking_file": item["tracking_file"],
        "pointer_file": item["pointer_file"],
        "next_stage": item["next_stage"],
        "next_stage_title": item["next_stage_title"],
        "current": pointer["current"],
        "stored": False,
        "advanced": False,
        "closed": False,
        "submitted": False,
        "revisit": revisit,
    }
    if basics_seeded:
        body["basics_seeded"] = True
    _attach_outline_report(body, essay_id, stage)
    _attach_short_report(body, short_report)
    _attach_cite_report(body, cite_report)
    if stage in {"5", "6", "7", "8"}:
        from essay_writer.encourage import student_facts

        body["student_detail"] = student_facts(essay_id)
    if stage5_gate is not None:
        body["north_star"] = stage5_gate
        body["checklist_in_chat"] = False
    if stage != "5":
        from essay_writer.specialists.grok_bot import attach_basics_pass

        shown = attach_basics_pass(essay_id)
        if shown:
            body["basics_pass"] = shown
    if stage in {"1", "3"}:
        from essay_writer.brief_contract import assignment_silence_gaps

        gaps = assignment_silence_gaps(essay_id)
        if gaps:
            body["assignment_gaps"] = gaps
    from essay_writer.cursor_office import stage_host_launch

    body["mid_office_launch"] = stage_host_launch(stage)
    if stage in {"1", "4a"} or heldFile is not None:
        from essay_writer.databases import database_view, remember_databases

        remember_databases(essay_id, heldFile)
        body["databases"] = database_view(essay_id)
    from essay_writer.spine import stage_confirm_card

    if stage == "6":
        from essay_writer.late_chain import stage6_fields
        body.update(stage6_fields(essay_id, master=master, named_folder=namedFolder))
        block_master = body.pop("block_confirm", False)
        if confirmPhase == CONFIRM and block_master:
            return refuse(
                "master",
                f"Which Word file is the master copy? The place is {body['place']}. Do not guess.",
                place=body["place"],
                choices=body["choices"],
                master_ask=True,
                chain_started=False,
            )
    if stage == "7" and confirmPhase == DRAFT and card_only:
        from essay_writer.stage7 import note_questions

        body.update(note_questions(essay_id))
    elif stage == "7" and confirmPhase == DRAFT:
        from essay_writer.stage7 import (
            answers_mean_no_change,
            answers_mean_skip,
            load_stage7,
            note_edits,
            note_questions,
        )

        if answers_mean_skip(text) or answers_mean_skip(answers if isinstance(answers, str) else None):
            return _stage7_skip_reply(essay_id, stage, genre, pointer, confirmPhase)
        # A later draft whose whole note is "no changes" is the answer.
        # The door keeps the text already saved and does not invent sentences.
        if (
            answers is None
            and edited is None
            and webCheck is None
            and load_stage7(essay_id).get("asked") is True
            and answers_mean_no_change(text)
        ):
            answers = text
        if answers is not None or edited is not None or webCheck is not None:
            edited_note = note_edits(essay_id, answers=answers, edited=edited, web_check=webCheck)
            if edited_note.get("ok") is False:
                return refuse(
                    "stage",
                    str(edited_note.get("reason") or "Ask, then edit from the answers."),
                    next=edited_note.get("next"),
                    stage=stage,
                    current=pointer["current"],
                )
            answers = edited_note.get("answers", answers)
            edited = edited_note.get("edited", edited)
            webCheck = edited_note.get("webCheck", webCheck)
            if stage in BODY_CITE_STAGES:
                short_report = apply_short_cite_request(
                    essay_id,
                    text,
                    answers=answers if isinstance(answers, str) else None,
                    edited=edited if isinstance(edited, str) else None,
                )
                text = short_report["text"]
                if isinstance(edited, str):
                    edited = short_report["edited"]
                cite_report = land_body_cites(
                    essay_id,
                    stage,
                    text,
                    answers=answers if isinstance(answers, str) else None,
                    edited=edited if isinstance(edited, str) else None,
                )
                text = cite_report["text"]
                if isinstance(edited, str):
                    edited = cite_report["edited"]
            payload["look"] = text
            for key, value in (
                ("answers", answers),
                ("edited", edited),
                ("webCheck", webCheck),
            ):
                if value is not None:
                    payload[key] = value
            body.update(edited_note)
            if isinstance(edited, str):
                body["edited"] = edited
            _attach_short_report(body, short_report)
            _attach_cite_report(body, cite_report)
        else:
            body.update(note_questions(essay_id))
    if stage == "10" and confirmPhase == CONFIRM and pointer.get("chain_armed") is True:
        from essay_writer.spine import final_review

        eqr_blocked, verdict = final_review(essay_id)
        if eqr_blocked:
            return refuse(
                "eqr",
                eqr_blocked,
                eqr=verdict,
                blocked=True,
                chain_started=False,
            )
    real_bib = True
    if stage == "4b":
        from essay_writer.spine import stage_reconcile

        real_bib, check = stage_reconcile(essay_id)
        body["download_check"] = check
    if confirmPhase == DRAFT:
        from essay_writer.canon import digest as payload_digest

        waiting_same = None if minting or auto_next else _waiting_digest(pointer, stage)
        if (
            waiting_same is not None
            and waiting_same == payload_digest(payload)
            and _note_path(essay_id, stage).is_file()
        ):
            replay = _replay_confirm_card(essay_id, stage, genre, pointer, waiting_same)
            if replay is not None:
                body["digest"] = waiting_same
                body.update(replay)
                body["wrote"] = False
                body.pop("mid_office_launch", None)
                body.pop("status", None)
                body.pop("mid_started", None)
                from essay_writer.late_chain import finish_stage_reply

                return finish_stage_reply(
                    body,
                    essay_id,
                    stage,
                    armed=pointer.get("chain_armed") is True,
                )
        body["digest"] = save_draft(essay_id, TOOL, payload, fingerprint)
        if not auto_next and not minting:
            note_text = render_tracking(stage, status="draft", look=text, genre=genre, essay_id=essay_id)
            proposed = dict(pointer)
            proposed["waiting_stage"] = stage
            proposed["waiting_digest"] = body["digest"]
            if revisit:
                proposed["revisit_open"] = stage
                if stage == "2":
                    proposed["revisit_after_lock"] = True
            stored = _commit_pointer(
                essay_id,
                pointer,
                proposed,
                note=note,
                note_text=note_text,
            )
            if stored is None:
                return _pointer_lost(essay_id, stage, genre)
            pointer = stored
        body["wrote"] = not minting
        if not minting:
            body["tracking_path"] = relative(note)
        if stage == "4b" and not real_bib:
            line = (
                "Stage 4a has no bibliography yet. "
                "Stay on the annotated list. Do not go on to the next stage."
            )
        else:
            line = _confirm_line(stage, genre, revisit=revisit)
            if stage == "4b":
                line += " Option C: Download leftovers first."
        body["confirm_line"] = line
        if not card_only:
            _attach_mid_run(body, essay_id, stage)
            from essay_writer.roll_forward import attach_stage_roll

            attach_stage_roll(body, essay_id, stage)
        if auto_next:
            return _store_stage(
                body,
                essay_id,
                stage,
                text,
                genre,
                pointer,
                note,
                digest=body["digest"],
                master=master,
                named_folder=namedFolder,
            )
        from essay_writer.specialists.grok_bot import (
            card_next,
            confirm_reply_fields,
            stage7_lead,
        )
        from essay_writer.stage7 import stage7_edited
        from essay_writer.student_progress import (
            mid_run_wait_next,
            upload_reconcile_next,
        )

        upload_next = upload_reconcile_next(body.get("download_check"))
        if upload_next:
            body["next"] = upload_next
        elif body.get("mid_started") is True:
            body["next"] = mid_run_wait_next(stage, body["stage_title"])
        elif stage == "7" and not stage7_edited(essay_id):
            body["next"] = stage7_lead(list(body.get("questions") or []), body["stage_title"])
        else:
            body["next"] = card_next(stage, body["stage_title"])
        body["card"] = stage_confirm_card(
            essay_id,
            stage,
            body["digest"],
            line,
            stage_title=body["stage_title"],
        )
        body.update(confirm_reply_fields(body["digest"]))
        from essay_writer.late_chain import finish_stage_reply

        return finish_stage_reply(
            body,
            essay_id,
            stage,
            armed=pointer.get("chain_armed") is True,
        )
    ready = confirm_ready(essay_id, TOOL, payload, fingerprint)
    if ready.get("ok") is False:
        return _reoffer_confirm(
            essay_id,
            stage,
            genre,
            pointer,
            cardDigest,
            code="confirm",
            reason=str(ready.get("reason") or "Show this step in the chat again before it can be saved."),
        )
    if cardDigest != ready.get("digest"):
        return _reoffer_confirm(
            essay_id,
            stage,
            genre,
            pointer,
            None,
            reason="That card does not match this draft. Show the draft card again.",
        )
    if not _INHERITED_KEEP.get() and _stale_confirm_body(
        essay_id, stage, pointer, ready.get("digest"), text
    ):
        return _older_card(essay_id, stage, genre, pointer)
    if stage == "4a":
        from essay_writer.roll_forward import pending_choice_reason

        pending = pending_choice_reason(essay_id)
        if pending:
            return _reoffer_confirm(
                essay_id,
                stage,
                genre,
                pointer,
                cardDigest,
                code="papers",
                reason=pending,
            )
        from essay_writer.spine import stage_bibliography

        delivery = stage_bibliography(essay_id)
        if delivery is None:
            return _reoffer_confirm(
                essay_id,
                stage,
                genre,
                pointer,
                cardDigest,
                code="stage",
                reason=(
                    "Stage 4a stays here until a gathered source is on the list. "
                    "Nothing was saved and the stage did not advance."
                ),
            )
        if isinstance(delivery, dict) and delivery.get("ok") is False:
            return _reoffer_confirm(
                essay_id,
                stage,
                genre,
                pointer,
                cardDigest,
                code=str(delivery.get("refused") or "annotation-prose"),
                reason=str(delivery.get("reason") or "The annotation needs full sentences."),
            )
        body["delivery"] = delivery
    if stage == "4b" and not real_bib:
        return _reoffer_confirm(
            essay_id,
            stage,
            genre,
            pointer,
            cardDigest,
            code="stage",
            reason=(
                "Stage 4b stays here until stage 4a has a bibliography. "
                "Nothing was saved and the stage did not advance."
            ),
        )
    if stage == "4b":
        from essay_writer.spine import stage_critical_reviews

        delivery = stage_critical_reviews(essay_id)
        if delivery is None:
            return _reoffer_confirm(
                essay_id,
                stage,
                genre,
                pointer,
                cardDigest,
                code="stage",
                reason=(
                    "Stage 4b stays here until stage 4a has a bibliography. "
                    "Nothing was saved and the stage did not advance."
                ),
            )
        body["delivery"] = delivery
        body["delivery_speech"] = "4b"
    note_text = render_tracking(stage, status="final", look=text, genre=genre, essay_id=essay_id)
    rel = relative(note)
    saved = _saved_after_confirm(pointer, stage)
    room = _room_after_card_save(pointer, stage)
    files = dict(pointer["files"])
    files[stage] = rel
    following = next_stage(stage)
    if revisit:
        updated = {
            "current": "5",
            "saved": saved,
            "files": files,
            "closed": False,
            "revisit_open": None,
            "revisit_after_lock": stage == "2",
            "chain_armed": pointer.get("chain_armed") is True,
            "waiting_stage": None,
            "waiting_digest": None,
            **room,
        }
        stored = _commit_pointer(essay_id, pointer, updated, note=note, note_text=note_text)
        if stored is None:
            return _pointer_lost(essay_id, stage, genre)
        updated = stored
        _cache_approved_look(essay_id, stage, text)
        body["wrote"] = True
        body["stored"] = True
        body["advanced"] = False
        body["closed"] = False
        body["revisit"] = True
        body["digest"] = ready["digest"]
        body["tracking_path"] = rel
        body["current"] = "5"
        from essay_writer.specialists.grok_bot import revisit_plan_next, saved_next

        if stage == "2":
            body["next_stage"] = "3"
            body["next_stage_title"] = stage_title("3", genre)
            body["next"] = revisit_plan_next(stage_title("3", genre))
        else:
            body["next_stage"] = "5"
            body["next_stage_title"] = stage_title("5", genre)
            body["next"] = saved_next("5", stage_title("5", genre))
        finished = _mark_explicit_end(_with_plan_encourage(body, essay_id, stage, text))
        _snapshot_stage_save(essay_id, stage, text, finished)
        return finished
    updated = {
        "current": following if following else stage,
        "saved": saved,
        "files": files,
        "closed": following is None,
        "revisit_open": None,
        "revisit_after_lock": False,
        "chain_armed": _late_armed(pointer, stage, essay_id),
        **room,
    }
    if stage == "1":
        from essay_writer.first_run import ensure_sequence_mac_folder

        body["sequence_mac_folder"] = ensure_sequence_mac_folder(essay_id)
    return _commit_with_next_card(
        body,
        essay_id,
        stage,
        genre,
        pointer,
        updated,
        note,
        note_text,
        following,
        ready.get("digest") if isinstance(ready.get("digest"), str) else None,
        text if stage == "3" else None,
        approved_look=text,
    )
