from __future__ import annotations

import hashlib
import json
import sys
import threading
import time
from pathlib import Path

import pytest
from helpers import open_sequence

from essay_writer.incident import incident_path
from essay_writer.paths import essay_dir, work_dir
from essay_writer.stage_run import essay_stage
from essay_writer.stage_state import DamagedStageCommit, load_pointer, stage_lock

KILLED_BYTES = b"killed-during-stage-commit\n"
ORPHAN_BYTES = b"orphan-commit-temp\n"
BESIDE_BYTES = b"commit-temp-beside-journal\n"
DECOY_BYTES = b"not-a-commit-temp\n"
LOOK = "The task is a short report on the corridor."
DISK_POINTER = {
    "chain_armed": False,
    "closed": False,
    "current": "1",
    "files": {},
    "revision": 0,
    "revisit_after_lock": False,
    "revisit_open": None,
    "room_grant": None,
    "room_lock": False,
    "saved": [],
    "waiting_digest": None,
    "waiting_stage": None,
}
_ROW_KEYS = ("code", "disposition", "message", "sequence", "severity", "stage", "tool")


def _emit(label: str, **items: object) -> None:
    text = label + " " + " ".join(f"{key}={value}" for key, value in items.items())
    print(text, file=sys.__stdout__)


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pointer_bytes(pointer: dict[str, object]) -> bytes:
    return (json.dumps(pointer, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _crash_rows(sequence: str) -> list[dict[str, object]]:
    path = incident_path()
    if not path.is_file():
        return []
    found = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("code") == "crash-recovered" and row.get("sequence") == sequence:
            found.append(row)
    return found


def _assert_one_crash(sequence: str) -> None:
    rows = _crash_rows(sequence)
    assert len(rows) == 1, f"sequence={sequence} crash-recovered rows={len(rows)}"
    row = rows[0]
    assert row["code"] == "crash-recovered"
    assert row["severity"] == "warn"
    assert row["disposition"] == "fallback"
    assert row["tool"] == "stage"
    assert row["stage"] == "commit"
    assert row["sequence"] == sequence
    assert row["message"] == ""
    shown = {key: row[key] for key in _ROW_KEYS}
    _emit("incident", row=json.dumps(shown, sort_keys=True))


def _plant(folder: Path, name: str, data: bytes) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(data)
    return path


def test_an_orphan_commit_temp_records_one_crash_and_leaves_the_files(workspace) -> None:
    killed = open_sequence()
    same_shape = open_sequence()

    killed_root = work_dir(killed)
    killed_tracking = killed_root / "tracking"
    killed_state = killed_root / "state.json"
    killed_pointer = killed_tracking / "stage.json"
    pointer_bytes = _pointer_bytes(DISK_POINTER)
    _plant(killed_tracking, "stage.json", pointer_bytes)
    _plant(killed_tracking, ".stage.lock", b"")
    killed_temp = _plant(killed_tracking, "..stage.commit.killed.tmp", KILLED_BYTES)
    same_tracking = work_dir(same_shape) / "tracking"
    _plant(same_tracking, "stage.json", pointer_bytes)
    _plant(same_tracking, ".stage.lock", b"")

    state_hash = _sha256(killed_state)
    pointer_hash = _sha256(killed_pointer)
    temp_hash = _sha256(killed_temp)
    assert state_hash is not None
    assert pointer_hash is not None
    assert temp_hash is not None
    _emit(
        "orphan-killed-before",
        state=state_hash,
        pointer=pointer_hash,
        temp=temp_hash,
    )
    expected = load_pointer(same_shape)
    loaded = load_pointer(killed)
    assert loaded["current"] == expected["current"]
    assert loaded["saved"] == expected["saved"]
    assert loaded["current"] == "1"
    assert loaded["saved"] == []
    assert _sha256(killed_state) == state_hash
    assert _sha256(killed_pointer) == pointer_hash
    assert killed_pointer.read_bytes() == pointer_bytes
    assert killed_temp.is_file()
    assert killed_temp.read_bytes() == KILLED_BYTES
    assert _sha256(killed_temp) == temp_hash
    proof = f"state={state_hash} pointer={pointer_hash} temp={temp_hash}"
    rows = _crash_rows(killed)
    assert len(rows) == 1, proof
    _assert_one_crash(killed)
    assert _crash_rows(same_shape) == []

    load_pointer(killed)
    assert len(_crash_rows(killed)) == 1, proof

    named = open_sequence("MOD1008AA")
    quiet = open_sequence("MOD1009AA")
    named_root = work_dir(named)
    named_state = named_root / "state.json"
    named_tracking = named_root / "tracking"
    named_pointer = named_tracking / "stage.json"
    named_lock = named_tracking / ".stage.lock"
    named_state.unlink(missing_ok=True)
    named_pointer.unlink(missing_ok=True)
    named_lock.unlink(missing_ok=True)
    named_temp = _plant(named_tracking, ".stage.commit.orphan.tmp", ORPHAN_BYTES)
    assert not named_state.exists()
    assert not named_pointer.exists()
    assert not named_lock.exists()
    named_temp_hash = _sha256(named_temp)
    _emit("orphan-named-before", state=None, pointer=None, temp=named_temp_hash)
    quiet_loaded = load_pointer(quiet)
    named_loaded = load_pointer(named)
    assert named_loaded["current"] == quiet_loaded["current"]
    assert named_loaded["saved"] == quiet_loaded["saved"]
    assert not named_state.exists()
    assert not named_pointer.exists()
    assert not named_lock.exists()
    assert named_temp.is_file()
    assert named_temp.read_bytes() == ORPHAN_BYTES
    assert _sha256(named_temp) == named_temp_hash
    _assert_one_crash(named)
    assert _crash_rows(quiet) == []

    brief = essay_dir(killed) / "brief.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text("Assignment task: Name the corridor.\n", encoding="utf-8")
    draft = essay_stage(killed, "1", "draft", LOOK)
    assert draft["ok"] is True, draft
    saved = essay_stage(
        killed,
        "1",
        "confirm",
        None,
        cardAction="confirm",
        cardDigest=draft["digest"],
    )
    assert saved["ok"] is True, saved
    assert killed_temp.read_bytes() == KILLED_BYTES
    assert len(_crash_rows(killed)) == 1


def test_a_load_with_no_commit_temp_writes_no_crash_recovered(workspace) -> None:
    seq = open_sequence("MOD1011AA")
    tracking = work_dir(seq) / "tracking"
    decoy = _plant(tracking, "..stage.json.abcd1234.tmp", DECOY_BYTES)
    _plant(tracking, ".stage.lock", b"")
    directory = tracking / "..stage.commit.dir.tmp"
    directory.mkdir()
    loaded = load_pointer(seq)
    assert loaded["current"] == "1"
    assert loaded["saved"] == []
    assert _crash_rows(seq) == []
    assert decoy.read_bytes() == DECOY_BYTES
    assert directory.is_dir()


def test_a_held_stage_lock_is_not_a_crash(workspace) -> None:
    seq = open_sequence("MOD1012AA")
    tracking = work_dir(seq) / "tracking"
    temp = tracking / "..stage.commit.live.tmp"
    release = threading.Event()
    started = threading.Event()

    def hold() -> None:
        with stage_lock(seq):
            temp.write_bytes(b"live\n")
            started.set()
            assert release.wait(timeout=5)
            temp.unlink()

    holder = threading.Thread(target=hold)
    holder.start()
    assert started.wait(timeout=5)
    box: dict[str, object] = {}

    def load() -> None:
        box["pointer"] = load_pointer(seq)

    loader = threading.Thread(target=load)
    loader.start()
    blocked = True
    for _ in range(20):
        if "pointer" in box:
            blocked = False
            break
        time.sleep(0.05)
    assert blocked
    release.set()
    holder.join(timeout=5)
    loader.join(timeout=5)
    assert box["pointer"]["current"] == "1"
    assert _crash_rows(seq) == []
    assert not temp.exists()


def test_a_journal_beside_a_commit_temp_replays_and_keeps_the_temp(workspace) -> None:
    seq = open_sequence("MOD1005AA")
    root = work_dir(seq)
    tracking = root / "tracking"
    pointer = _plant(tracking, "stage.json", _pointer_bytes(DISK_POINTER))
    journal_bytes = _pointer_bytes({"pointer": {"current": "3", "saved": ["1"]}})
    journal = _plant(tracking, ".stage.commit", journal_bytes)
    temp = _plant(tracking, "..stage.commit.beside.tmp", BESIDE_BYTES)
    state = root / "state.json"
    state_hash = _sha256(state)
    pointer_hash = _sha256(pointer)
    journal_hash = _sha256(journal)
    temp_hash = _sha256(temp)
    _emit(
        "both-before",
        state=state_hash,
        pointer=pointer_hash,
        journal=journal_hash,
        temp=temp_hash,
    )
    loaded = load_pointer(seq)
    assert loaded["current"] == "3", f"journal={journal_hash} pointer={pointer_hash}"
    assert loaded["saved"] == ["1"]
    assert not journal.exists()
    assert temp.is_file()
    assert temp.read_bytes() == BESIDE_BYTES
    assert _sha256(state) == state_hash
    assert _sha256(temp) == temp_hash
    _assert_one_crash(seq)
    _emit(
        "both-after",
        state=_sha256(state),
        pointer=_sha256(pointer),
        journal=None,
        temp=_sha256(temp),
    )
    load_pointer(seq)
    assert len(_crash_rows(seq)) == 1
    assert temp.read_bytes() == BESIDE_BYTES
    brief = essay_dir(seq) / "brief.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text("Assignment task: Name the corridor.\n", encoding="utf-8")
    draft = essay_stage(seq, "3", "draft", LOOK)
    assert draft["ok"] is True, draft
    saved = essay_stage(
        seq,
        "3",
        "confirm",
        None,
        cardAction="confirm",
        cardDigest=draft["digest"],
    )
    assert saved["ok"] is True, saved
    assert temp.read_bytes() == BESIDE_BYTES
    assert load_pointer(seq)["current"] != "1"
    assert len(_crash_rows(seq)) == 1


def test_a_published_journal_without_a_commit_temp_still_replays(workspace) -> None:
    seq = open_sequence("MOD1006AA")
    tracking = work_dir(seq) / "tracking"
    _plant(tracking, "stage.json", _pointer_bytes(DISK_POINTER))
    journal = _plant(
        tracking,
        ".stage.commit",
        _pointer_bytes({"pointer": {"current": "2", "saved": ["1"]}}),
    )
    decoy = _plant(tracking, "..stage.json.token.tmp", DECOY_BYTES)
    loaded = load_pointer(seq)
    assert loaded["current"] == "2"
    assert loaded["saved"] == ["1"]
    assert not journal.exists()
    assert decoy.read_bytes() == DECOY_BYTES
    assert _crash_rows(seq) == []


def test_a_damaged_journal_beside_a_commit_temp_still_stops(workspace) -> None:
    seq = open_sequence("MOD1007AA")
    tracking = work_dir(seq) / "tracking"
    pointer = _plant(tracking, "stage.json", _pointer_bytes(DISK_POINTER))
    journal = _plant(tracking, ".stage.commit", b"{not json")
    temp = _plant(tracking, "..stage.commit.beside.tmp", BESIDE_BYTES)
    pointer_bytes = pointer.read_bytes()
    with pytest.raises(DamagedStageCommit):
        load_pointer(seq)
    assert journal.read_bytes() == b"{not json"
    assert temp.read_bytes() == BESIDE_BYTES
    assert pointer.read_bytes() == pointer_bytes
    assert _crash_rows(seq) == []
