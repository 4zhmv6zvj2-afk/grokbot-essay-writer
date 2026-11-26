"""Pointer, commit journal, and stage lock.

This file owns the pointer, the commit journal, and the stage lock.
"""

from __future__ import annotations

import json
import sys
import threading
from collections.abc import Mapping
from contextlib import contextmanager
from typing import Any, Literal, Never, TypedDict

# The stage lock is POSIX-only. Importing the package on Windows must succeed;
# only taking the lock refuses, and the refusal names the platform.
try:
    import fcntl
except ImportError:  # pragma: no cover - exercised by the no-fcntl subprocess test
    fcntl = None  # type: ignore[assignment]

from essay_writer.durable import replace_text
from essay_writer.incident import note
from essay_writer.known_paths import refuse_repo_write
from essay_writer.paths import work_dir
from essay_writer.stage_llm import POINTER_FILE, STAGE_ORDER, tracking_file

TOOL = "essay.stage"


def _atomic(path, text: str) -> None:
    refuse_repo_write(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    replace_text(path, text)


# One file. The note body and the pointer that names it land together.
STAGE_COMMIT = "tracking/.stage.commit"
_STAGE_NOTE_RELS = frozenset(tracking_file(stage) for stage in STAGE_ORDER)
_LOCKS = threading.local()
_CRASH_RECOVERED: set[str] = set()
_CRASH_RECOVERED_LOCK = threading.Lock()
_COMMIT_FILE_NAME = STAGE_COMMIT.rpartition("/")[2]
_COMMIT_TEMP_PREFIXES = (f".{_COMMIT_FILE_NAME}.", f"{_COMMIT_FILE_NAME}.")


def _pointer_path(essay_id: str):
    return work_dir(essay_id) / POINTER_FILE


def _commit_path(essay_id: str):
    return work_dir(essay_id) / STAGE_COMMIT


def _pointer_text(body: dict[str, object]) -> str:
    # A journal record is a mapping, not a Pointer. The on-disk JSON is unchanged.
    return json.dumps(body, indent=2, ensure_ascii=False) + "\n"


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
        if (
            not isinstance(note_rel, str)
            or note_rel not in _STAGE_NOTE_RELS
            or not isinstance(note_text, str)
        ):
            raise ValueError("stage commit note is not a tracking note")
        _atomic(root / note_rel, note_text)
    pointer = record.get("pointer")
    if not isinstance(pointer, dict):
        raise ValueError("stage commit is missing the pointer")
    _atomic(root / POINTER_FILE, _pointer_text(pointer))
    journal = root / STAGE_COMMIT
    if journal.is_file():
        journal.unlink()


DAMAGED_COMMIT = "The last confirm record was damaged and was not applied."


class DamagedStageCommit(Exception):
    """A stage journal exists and cannot be applied."""

    def __init__(self) -> None:
        super().__init__(DAMAGED_COMMIT)


def _commit_record_ok(record: object) -> bool:
    """True when the journal can be applied without wiping the pointer."""
    if not isinstance(record, dict):
        return False
    pointer = record.get("pointer")
    if not isinstance(pointer, dict) or pointer.get("current") not in STAGE_ORDER:
        return False
    saved = pointer.get("saved", [])
    # An unknown saved entry is kept. A value that is not a list still cannot be applied.
    if not isinstance(saved, list):
        return False
    note_rel = record.get("note")
    note_text = record.get("note_text")
    if note_rel is None and note_text is None:
        return True
    return isinstance(note_rel, str) and note_rel in _STAGE_NOTE_RELS and isinstance(note_text, str)


def _journal_damaged(root) -> bool:
    """True when the journal is present but is not a commit record.

    A missing file is not damage. Damage is not applied.
    """
    journal = root / STAGE_COMMIT
    if not journal.is_file():
        return False
    try:
        record = json.loads(journal.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return True
    return not _commit_record_ok(record)


def _raise_if_journal_damaged(root) -> None:
    """Stop when the journal exists and is not a commit record.

    A missing file is not damage. The damaged file stays where it is and is
    not applied.
    """
    if _journal_damaged(root):
        raise DamagedStageCommit()


def _read_commit(root) -> dict[str, object] | None:
    journal = root / STAGE_COMMIT
    if not journal.is_file() or _journal_damaged(root):
        return None
    record = json.loads(journal.read_text(encoding="utf-8"))
    if not _commit_record_ok(record):
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


class _RoomFields(TypedDict):
    room_grant: str | None
    room_lock: bool


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


def blank_pointer() -> Pointer:
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
    first, then replaced, so the child is not a torn pair. A damaged journal
    stops the copy. It is not applied and it is not set aside.
    """
    _raise_if_journal_damaged(folder)
    _replay_commit(folder)
    path = folder / POINTER_FILE
    if path.is_file():
        _atomic(path, _pointer_text(dict(blank_pointer())))
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
            replace_text(
                dest,
                json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                mkdir=True,
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


def _read_pointer_data(essay_id: str) -> dict[str, object] | None:
    path = _pointer_path(essay_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError):
        _note_pointer("pointer-damaged", disposition="fallback", severity="warn")
        return None
    if not isinstance(data, dict):
        _note_pointer("pointer-damaged", disposition="fallback", severity="warn")
        return None
    return data


def _is_commit_temp(name: str) -> bool:
    return name.endswith(".tmp") and name.startswith(_COMMIT_TEMP_PREFIXES)


def _has_commit_temp(root) -> bool:
    tracking = root / "tracking"
    if not tracking.is_dir():
        return False
    return any(entry.is_file() and _is_commit_temp(entry.name) for entry in tracking.iterdir())


def _stage_commit_shape(root) -> Literal["absent", "orphan", "published", "both"]:
    journal = (root / STAGE_COMMIT).is_file()
    temp = _has_commit_temp(root)
    if journal and temp:
        return "both"
    if journal:
        return "published"
    if temp:
        return "orphan"
    return "absent"


def _stage_lock_path(essay_id: str):
    return work_dir(essay_id) / "tracking" / ".stage.lock"


def _note_crash_recovered(sequence: str) -> None:
    with _CRASH_RECOVERED_LOCK:
        if sequence in _CRASH_RECOVERED:
            return
        _CRASH_RECOVERED.add(sequence)
    note(
        "crash-recovered",
        severity="warn",
        disposition="fallback",
        tool="stage",
        step="commit",
        sequence=sequence,
    )


def _settle_stage_commit(essay_id: str) -> None:
    root = work_dir(essay_id)
    shape = _stage_commit_shape(root)
    if shape == "both":
        _raise_if_journal_damaged(root)
        _note_crash_recovered(essay_id)
    elif shape == "orphan":
        _note_crash_recovered(essay_id)
    elif shape != "absent" and shape != "published":
        unexpected: Never = shape
        raise AssertionError(unexpected)
    _raise_if_journal_damaged(root)
    _replay_commit(root)


def load_pointer(essay_id: str) -> Pointer:
    if not _pointer_path(essay_id).is_file() and not _commit_path(essay_id).is_file():
        root = work_dir(essay_id)
        lock = _stage_lock_path(essay_id)
        if not lock.is_file():
            orphan = _stage_commit_shape(root) == "orphan"
            if orphan and not lock.is_file():
                _note_crash_recovered(essay_id)
                return blank_pointer()
            if not lock.is_file():
                return blank_pointer()
    with _pointer_lock(essay_id):
        data = _read_pointer_data(essay_id)
        if data is None:
            return blank_pointer()
        return _normalize_pointer(data)


def _note_pointer(code: str, *, disposition: str, severity: str = "info") -> None:
    note(code, severity=severity, disposition=disposition, tool="stage", step="pointer")


def _keep_unnamed(
    pointer: Pointer, source: Mapping[str, Any], *, named: Mapping[str, Any] | None = None
) -> None:
    """Copy fields the named pointer keys do not cover. A later save still writes them."""
    if named is None:
        extra = {key: value for key, value in source.items() if key not in pointer}
    else:
        extra = {
            key: value for key, value in source.items() if key not in named and key not in pointer
        }
    if extra:
        dict.update(pointer, extra)


def _waiting_input(data: dict[str, Any]) -> Pointer:
    """The waiting fields from a raw pointer file, before the pointer is normalized."""
    view: Pointer = {}
    stage = data.get("waiting_stage")
    digest = data.get("waiting_digest")
    if isinstance(stage, str):
        view["waiting_stage"] = stage
    if isinstance(digest, str):
        view["waiting_digest"] = digest
    return view


def _normalize_pointer(data: dict[str, Any]) -> Pointer:
    """Load a pointer without writing it.

    A missing known field is filled in memory. An unknown field, including an
    unknown saved entry or file entry, is kept. A current value that is not a
    stage becomes stage 1 in memory. A saved or files value that is not a list
    or an object is left out of the loaded pointer. Each of those is recorded.
    The file on disk is unchanged until a later save.
    """
    known = blank_pointer()
    if any(key not in data for key in known):
        _note_pointer("pointer-field-filled", disposition="fallback")
    saved_raw = data.get("saved")
    files_raw = data.get("files")
    unknown = any(key not in known for key in data)
    if isinstance(saved_raw, list) and any(
        not isinstance(item, str) or item not in STAGE_ORDER for item in saved_raw
    ):
        unknown = True
    if isinstance(files_raw, dict) and any(
        key not in STAGE_ORDER or not isinstance(value, str) for key, value in files_raw.items()
    ):
        unknown = True
    if unknown:
        _note_pointer("pointer-unknown-field", disposition="fallback")
    current = data.get("current")
    if "current" in data and current not in STAGE_ORDER:
        _note_pointer("pointer-unknown-current", disposition="fallback")
        current = "1"
    elif current not in STAGE_ORDER:
        current = "1"
    if isinstance(saved_raw, list):
        saved = list(saved_raw)
    else:
        saved = []
    if isinstance(files_raw, dict):
        files = dict(files_raw)
    else:
        files = {}
    reopen = data.get("revisit_open")
    if reopen not in {"2", "3"}:
        reopen = None
    grant = data.get("room_grant")
    if grant not in STAGE_ORDER:
        grant = None
    waiting_stage, waiting_digest = _waiting_pair(_waiting_input(data))
    result: Pointer = {
        "current": current,
        "saved": saved,
        "files": files,
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
    dropped = ("saved" in data and not isinstance(saved_raw, list)) or (
        "files" in data and not isinstance(files_raw, dict)
    )
    for key, value in result.items():
        if key == "current" or key not in data:
            continue
        if data[key] != value:
            dropped = True
    if dropped:
        _note_pointer("pointer-field-dropped", disposition="fallback")
    _keep_unnamed(result, data)
    return result


def _room_state(pointer: Pointer) -> _RoomFields:
    """The room press still on the pointer. A card tap leaves both empty."""
    grant = pointer.get("room_grant")
    if grant not in STAGE_ORDER:
        grant = None
    return {"room_grant": grant, "room_lock": pointer.get("room_lock") is True}


def _room_after_card_save(pointer: Pointer, stage: str) -> _RoomFields:
    """A room press saves only the stage it named. The next stage needs its own press."""
    state = _room_state(pointer)
    if state["room_grant"] == stage:
        return {"room_grant": None, "room_lock": True}
    return {"room_grant": None, "room_lock": False}


def _saved_after_confirm(pointer: Pointer, stage: str) -> list[str]:
    """One confirm stores this stage only. The next stage is not appended."""
    saved = list(pointer["saved"])
    if stage not in saved:
        saved.append(stage)
    return saved


def _room_blocks(pointer: Pointer, stage: str) -> bool:
    """True when a room press for another stage, or a used press, is not this stage's Confirm."""
    state = _room_state(pointer)
    if state["room_lock"] and state["room_grant"] != stage:
        return True
    return state["room_grant"] is not None and state["room_grant"] != stage


def _waiting_pair(pointer: Pointer) -> tuple[str | None, str | None]:
    stage = pointer.get("waiting_stage")
    digest = pointer.get("waiting_digest")
    if stage not in STAGE_ORDER or not isinstance(digest, str) or len(digest) != 64:
        return None, None
    return stage, digest


def _waiting_digest(pointer: Pointer, stage: str) -> str | None:
    """Digest of the draft that wrote the current note for this stage."""
    waiting_stage, digest = _waiting_pair(pointer)
    if waiting_stage != stage:
        return None
    return digest


def _revision(pointer: Mapping[str, Any]) -> int:
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


def require_fcntl() -> Any:
    """The POSIX ``fcntl`` module, or a clear unsupported-platform refusal.

    This module imports on every platform. Only a caller that actually takes a
    lock needs fcntl, and only then is the platform named.
    """
    if fcntl is None:
        raise RuntimeError(
            "Cross-process file locking needs POSIX fcntl, which this platform "
            f"({sys.platform}) does not provide. Run the essay writer on macOS or Linux; "
            "Windows is not supported."
        )
    return fcntl


@contextmanager
def _pointer_lock(essay_id: str):
    """One exclusive lock for the note and pointer on this sequence."""
    held = _held_locks()
    if essay_id in held:
        _raise_if_journal_damaged(work_dir(essay_id))
        yield
        return
    module = require_fcntl()
    folder = work_dir(essay_id) / "tracking"
    folder.mkdir(parents=True, exist_ok=True)
    handle = (folder / ".stage.lock").open("a+")
    try:
        module.flock(handle.fileno(), module.LOCK_EX)
        held.add(essay_id)
        try:
            _settle_stage_commit(essay_id)
            yield
        finally:
            held.discard(essay_id)
    finally:
        module.flock(handle.fileno(), module.LOCK_UN)
        handle.close()


def stage_lock(essay_id: str):
    """Exclusive lock for this sequence's note and pointer."""
    return _pointer_lock(essay_id)


def _rolls_backward(fresh: Pointer, proposed: Pointer) -> bool:
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
    base: Pointer,
    proposed: Pointer,
    *,
    note=None,
    note_text: str | None = None,
) -> Pointer | None:
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
        stored: Pointer = {**proposed}
        known = blank_pointer()
        _keep_unnamed(stored, base, named=known)
        stored["revision"] = _revision(fresh) + 1
        record: dict[str, object] = {"pointer": stored}
        if note is not None and note_text is not None:
            record["note"] = _note_rel(note)
            record["note_text"] = note_text
        _atomic(_commit_path(essay_id), _pointer_text(record))
        _apply_commit(work_dir(essay_id), record)
        return stored


def _payload(essay_id: str, stage: str, look: str) -> dict[str, object]:
    return {"essay_id": essay_id, "stage": stage, "look": look}


def _grant_room(essay_id: str, pointer: Pointer, stage: str) -> Pointer | None:
    """Record this stage's press without rewriting current or saved from a stale read."""
    proposed: Pointer = {**pointer}
    proposed["room_grant"] = stage
    proposed["room_lock"] = False
    return _commit_pointer(essay_id, pointer, proposed)


def _revisit_window(pointer: Pointer) -> bool:
    """After 4b is saved and before stage 5 is saved, the plan may be opened again."""
    return (
        pointer.get("closed") is not True
        and pointer.get("current") == "5"
        and "4b" in pointer.get("saved", [])
        and "5" not in pointer.get("saved", [])
    )


def in_first_draft(essay_id: str) -> bool:
    """True after 4b is saved and before stage 5 is saved."""
    pointer = load_pointer(essay_id)
    return pointer.get("current") == "5" and "5" not in pointer.get("saved", [])
