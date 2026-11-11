"""Per-essay Confirm state. One file, one essay id, no cross-read."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any

from essay_writer.known_paths import refuse_repo_write
from essay_writer.paths import module_code, sequence_number, work_dir, write_last_saved
from essay_writer.records import read_json, write_json

_STATE_LOCK = "state.json.lock"
_LOCKS = threading.local()


def _held_locks() -> set[str]:
    held = getattr(_LOCKS, "held", None)
    if held is None:
        held = set()
        _LOCKS.held = held
    return held


def _fcntl() -> Any:
    """The guarded POSIX lock module shared with the stage layer."""
    from essay_writer.stage_state import require_fcntl

    return require_fcntl()


@contextmanager
def state_lock(essay_id: str):
    """Exclusive cross-process lock for this sequence's state.json.

    The lock is the sibling ``state.json.lock`` and is shared by every thread
    and process that saves this sequence. ``save_state`` takes it for the
    write. A caller that does ``load_state``, changes the record, then calls
    ``save_state`` must hold this lock across that whole read-modify-write;
    the write alone cannot see an update made after the caller's read. The
    same thread may re-enter.
    """
    held = _held_locks()
    if essay_id in held:
        yield
        return
    module = _fcntl()
    path = state_path(essay_id).with_name(_STATE_LOCK)
    refuse_repo_write(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    try:
        module.flock(handle.fileno(), module.LOCK_EX)
        held.add(essay_id)
        try:
            yield
        finally:
            held.discard(essay_id)
    finally:
        module.flock(handle.fileno(), module.LOCK_UN)
        handle.close()


def empty_state(essay_id: str) -> dict[str, Any]:
    return {
        "essay_id": essay_id,
        "research": {"summary": None, "full": None},
        "validations": {},
        "word": {},
        "revisions": [],
        "shelf": {},
    }


def state_path(essay_id: str):
    return work_dir(essay_id) / "state.json"


def load_state(essay_id: str) -> dict[str, Any]:
    base = empty_state(essay_id)
    data = read_json(state_path(essay_id))
    if data is not None:
        for key in base:
            if key in data:
                base[key] = data[key]
        for key, value in data.items():
            if key not in base:
                base[key] = value
    base["essay_id"] = essay_id
    return base


def save_state(essay_id: str, state: dict[str, Any]) -> None:
    """Write one sequence's state under the cross-process state lock.

    A caller that loads, changes, then saves the same record should hold
    :func:`state_lock` across that whole sequence, not just this call.
    """
    with state_lock(essay_id):
        write_json(state_path(essay_id), state, mkdir=True)
        number = sequence_number(essay_id)
        if number is not None:
            write_last_saved(module_code(essay_id), number)
