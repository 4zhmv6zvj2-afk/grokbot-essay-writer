"""Per-essay Confirm state. One file, one essay id, no cross-read."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps
from typing import Any, cast

from essay_writer.known_paths import refuse_repo_write
from essay_writer.paths import module_code, sequence_number, work_dir, write_last_saved
from essay_writer.records import write_json

STATE_DAMAGED = "The state file is damaged."


class DamagedState(Exception):
    """state.json exists and is not a JSON object."""

    def __init__(self) -> None:
        super().__init__(STATE_DAMAGED)


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
    """Load one sequence's state.

    A missing file starts empty. A file that exists and is not a JSON object
    is damage: the sequence is not treated as empty.
    """
    path = state_path(essay_id)
    data: dict[str, Any] | None = None
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DamagedState() from exc
        if not isinstance(loaded, dict):
            raise DamagedState()
        data = loaded
    base = empty_state(essay_id)
    if data is not None:
        for key in base:
            if key in data:
                base[key] = data[key]
        for key, value in data.items():
            if key not in base:
                base[key] = value
    base["essay_id"] = essay_id
    return base


def state_file_refusal() -> dict[str, Any]:
    """Refusal when state.json exists and cannot be read as an object."""
    from essay_writer.confirm import refuse

    return refuse("state", STATE_DAMAGED, wrote=False, stored=False)


def record_damage_refusal(essay_id: str) -> dict[str, Any] | None:
    """Refusal when the state file or the stage confirm record is damaged.

    A missing file is not damage. A damaged confirm record is not applied.
    When both are damaged, the refusal names both.
    """
    reasons: list[str] = []
    try:
        load_state(essay_id)
    except DamagedState:
        reasons.append(STATE_DAMAGED)
    from essay_writer.stage_state import DAMAGED_COMMIT, DamagedStageCommit, load_pointer

    try:
        load_pointer(essay_id)
    except DamagedStageCommit:
        reasons.append(DAMAGED_COMMIT)
    if not reasons:
        return None
    from essay_writer.confirm import refuse

    if reasons == [DAMAGED_COMMIT]:
        code = "stage"
    else:
        code = "state"
    return refuse(code, " ".join(reasons), wrote=False, stored=False)


def refusal_for_damage(exc: BaseException) -> dict[str, Any] | None:
    """Refusal for a damaged state file or confirm record. Other errors stay."""
    if isinstance(exc, DamagedState):
        return state_file_refusal()
    from essay_writer.stage_state import DAMAGED_COMMIT, DamagedStageCommit

    if isinstance(exc, DamagedStageCommit):
        from essay_writer.confirm import refuse

        reason = str(exc).strip() or DAMAGED_COMMIT
        return refuse("stage", reason, wrote=False, stored=False)
    return None


def guard_damaged_records[F: Callable[..., Any]](fn: F) -> F:
    """Turn a damaged state file or confirm record into a refusal."""

    @wraps(fn)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            refused = refusal_for_damage(exc)
            if refused is None:
                raise
            return refused

    return cast(F, wrapped)


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
