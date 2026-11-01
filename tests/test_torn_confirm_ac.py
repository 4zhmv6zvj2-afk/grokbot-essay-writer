"""Torn confirm. Stable ids: AC1, AC2, AC3, AC4.

A crash between the note replace and the pointer replace must not let Confirm
save the older look. The note and the pointer fields that name it commit
together. An open-parent clone must not publish that torn pair. A closed
parent clone must not leave stages 1–10 as final notes.
"""

import json
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest
from helpers import ESSAY, open_sequence

from essay_writer import stage_track
from essay_writer.canon import digest
from essay_writer.confirm import load_draft_by_digest
from essay_writer.paths import sequence_dir, work_dir
from essay_writer.projects import (
    clone_sequence,
    essay_sequence_new,
    save_sequence_state,
    sequence_id,
)
from essay_writer.stage_track import STAGE_COMMIT, TOOL, essay_stage, load_pointer
from essay_writer.writing_basics import STAGE_ORDER

LOOK = "Look A stays."
NEWER = "Look B replaces."
LOCK = "Purpose and scope now name one chain because Smith 2020 shows it."


def _note(seq: str, stage: str) -> str:
    return (work_dir(seq) / "tracking" / f"{stage}.md").read_text(encoding="utf-8")


def _raw_pointer(seq: str) -> dict:
    return json.loads((work_dir(seq) / "tracking" / "stage.json").read_text(encoding="utf-8"))


def _journal(seq: str) -> dict:
    return json.loads((work_dir(seq) / STAGE_COMMIT).read_text(encoding="utf-8"))


def _rebound_waiting(seq: str, pointer: dict, look: str) -> None:
    """The child's waiting digest opens the copied look for this sequence."""
    waiting = pointer["waiting_digest"]
    record = load_draft_by_digest(seq, TOOL, waiting)
    assert record is not None
    payload = record["payload"]
    assert payload["essay_id"] == seq
    assert payload["look"] == look
    assert digest(payload) == waiting


def _confirm(seq: str, stage: str, digest: str) -> dict:
    return essay_stage(
        seq,
        stage,
        "confirm",
        None,
        cardAction="confirm",
        cardDigest=digest,
    )


@contextmanager
def _torn_pointer(monkeypatch):
    """Let the note replace finish, then raise before the pointer replace."""
    real = stage_track._atomic

    def tearing(path, text):
        if Path(path).name == "stage.json":
            raise RuntimeError("torn before pointer")
        real(path, text)

    monkeypatch.setattr(stage_track, "_atomic", tearing)
    try:
        yield
    finally:
        monkeypatch.setattr(stage_track, "_atomic", real)


def test_ac1_torn_confirm_keeps_the_newer_look(workspace, monkeypatch):
    """AC1: Confirm of the stale digest does not advance or overwrite the newer note."""
    seq = open_sequence()
    first = essay_stage(seq, "1", "draft", LOOK)
    assert first["ok"] is True, first
    with _torn_pointer(monkeypatch):
        with pytest.raises(RuntimeError, match="torn before pointer"):
            essay_stage(seq, "1", "draft", NEWER)
    raw = _raw_pointer(seq)
    note = _note(seq, "1")
    journal = _journal(seq)
    new_digest = journal["pointer"]["waiting_digest"]
    assert raw["waiting_digest"] == first["digest"]
    assert new_digest != first["digest"]
    assert NEWER in note
    assert LOOK not in note
    assert "Status: draft" in note
    assert NEWER in journal["note_text"]
    stale = _confirm(seq, "1", first["digest"])
    assert stale["ok"] is False, stale
    assert stale["refused"] == "confirm"
    assert stale["stored"] is False
    assert stale["advanced"] is False
    assert stale.get("cardDigest") == new_digest
    assert "older draft" in stale["reason"]
    healed = load_pointer(seq)
    assert healed["current"] == "1"
    assert healed["saved"] == []
    assert healed["waiting_digest"] == new_digest
    kept = _note(seq, "1")
    assert "Status: final" not in kept
    assert NEWER in kept
    assert LOOK not in kept
    fresh = _confirm(seq, "1", new_digest)
    assert fresh["ok"] is True, fresh
    assert fresh["stored"] is True
    assert fresh["current"] == "2"
    final = _note(seq, "1")
    assert "Status: final" in final
    assert NEWER in final
    assert LOOK not in final
    assert load_pointer(seq)["saved"] == ["1"]
    assert load_pointer(seq)["current"] == "2"


def test_ac2_note_and_pointer_fields_commit_together(workspace, monkeypatch):
    """AC2: waiting_digest, saved/current, and revisit_open commit with the note."""
    seq = open_sequence()
    first = essay_stage(seq, "1", "draft", LOOK)
    assert first["ok"] is True, first
    with _torn_pointer(monkeypatch):
        with pytest.raises(RuntimeError, match="torn before pointer"):
            essay_stage(seq, "1", "draft", NEWER)
    journal = _journal(seq)
    assert journal["note"] == "tracking/1.md"
    assert NEWER in journal["note_text"]
    assert journal["pointer"]["waiting_stage"] == "1"
    assert journal["pointer"]["waiting_digest"] != first["digest"]
    assert journal["pointer"]["current"] == "1"
    assert _raw_pointer(seq)["waiting_digest"] == first["digest"]
    recovered = load_pointer(seq)
    assert recovered["waiting_digest"] == journal["pointer"]["waiting_digest"]
    assert recovered["current"] == "1"
    assert recovered["saved"] == []
    assert recovered["revisit_open"] is None
    assert NEWER in _note(seq, "1")
    assert not (work_dir(seq) / STAGE_COMMIT).is_file()

    digest = recovered["waiting_digest"]
    with _torn_pointer(monkeypatch):
        with pytest.raises(RuntimeError, match="torn before pointer"):
            _confirm(seq, "1", digest)
    confirm_journal = _journal(seq)
    assert "Status: final" in confirm_journal["note_text"]
    assert NEWER in confirm_journal["note_text"]
    assert confirm_journal["pointer"]["current"] == "2"
    assert confirm_journal["pointer"]["saved"] == ["1"]
    assert confirm_journal["pointer"]["waiting_stage"] == "2"
    next_digest = confirm_journal["pointer"]["waiting_digest"]
    assert isinstance(next_digest, str) and len(next_digest) == 64
    assert next_digest != digest
    assert _raw_pointer(seq)["current"] == "1"
    assert _raw_pointer(seq)["saved"] == []
    assert "Status: final" in _note(seq, "1")
    finished = load_pointer(seq)
    assert finished["current"] == "2"
    assert finished["saved"] == ["1"]
    assert finished["waiting_stage"] == "2"
    assert finished["waiting_digest"] == next_digest
    assert "Status: final" in _note(seq, "1")
    assert NEWER in _note(seq, "1")

    revisit = open_sequence()
    planted = {
        "current": "5",
        "saved": ["1", "2", "3", "4a", "4b"],
        "files": {},
        "closed": False,
        "revisit_open": None,
        "revisit_after_lock": False,
        "chain_armed": False,
        "room_grant": None,
        "room_lock": False,
        "waiting_stage": None,
        "waiting_digest": None,
        "revision": 9,
    }
    pointer_path = work_dir(revisit) / "tracking" / "stage.json"
    pointer_path.parent.mkdir(parents=True, exist_ok=True)
    pointer_path.write_text(json.dumps(planted, indent=2) + "\n", encoding="utf-8")
    with _torn_pointer(monkeypatch):
        with pytest.raises(RuntimeError, match="torn before pointer"):
            essay_stage(revisit, "2", "draft", LOCK)
    reopen = _journal(revisit)
    assert LOCK in reopen["note_text"]
    assert "Status: draft" in reopen["note_text"]
    assert reopen["pointer"]["revisit_open"] == "2"
    assert reopen["pointer"]["current"] == "5"
    assert "2" in reopen["pointer"]["saved"]
    assert reopen["pointer"]["waiting_stage"] == "2"
    assert _raw_pointer(revisit)["revisit_open"] is None
    assert _raw_pointer(revisit)["current"] == "5"
    assert LOCK in _note(revisit, "2")
    held = essay_stage(revisit, "5", "draft", "The first draft can start.")
    assert held["ok"] is False, held
    assert held.get("stored") is not True
    assert "Save the plan note first" in held["reason"]
    after = load_pointer(revisit)
    assert after["current"] == "5"
    assert after["revisit_open"] == "2"
    assert "5" not in after["saved"]
    assert "2" in after["saved"]
    assert after["waiting_stage"] == "2"
    assert LOCK in _note(revisit, "2")
    assert "Status: draft" in _note(revisit, "2")


def test_ac3_open_clone_cannot_publish_a_torn_pair(workspace, monkeypatch):
    """AC3: a clone during the note/pointer window publishes one generation."""
    seq = open_sequence()
    first = essay_stage(seq, "1", "draft", LOOK)
    assert first["ok"] is True, first
    with _torn_pointer(monkeypatch):
        with pytest.raises(RuntimeError, match="torn before pointer"):
            essay_stage(seq, "1", "draft", NEWER)
    assert _raw_pointer(seq)["waiting_digest"] == first["digest"]
    assert NEWER in _note(seq, "1")
    new_digest = _journal(seq)["pointer"]["waiting_digest"]
    clone_sequence(ESSAY, 1, 2, reason="roll-forward")
    parent = _raw_pointer(seq)
    child = _raw_pointer(f"{ESSAY}-2")
    assert parent["waiting_digest"] == new_digest
    assert child["current"] == "1"
    assert child["saved"] == []
    assert child.get("waiting_digest") in (None,)
    assert not (work_dir(f"{ESSAY}-2") / "tracking" / "1.md").exists()
    assert NEWER in _note(seq, "1")
    assert not (work_dir(seq) / STAGE_COMMIT).is_file()
    assert not (work_dir(f"{ESSAY}-2") / STAGE_COMMIT).is_file()

    live = open_sequence()
    assert live == f"{ESSAY}-3"
    older = essay_stage(live, "1", "draft", LOOK)
    assert older["ok"] is True, older
    entered = threading.Event()
    release = threading.Event()
    entered_lock = threading.Event()
    acquired_lock = threading.Event()
    real_atomic = stage_track._atomic
    real_lock = stage_track.stage_lock

    def pausing(path, text):
        real_atomic(path, text)
        if Path(path).name == "1.md" and NEWER in text:
            entered.set()
            assert release.wait(10), "clone test did not release the writer"

    @contextmanager
    def watching(essay_id):
        entered_lock.set()
        with real_lock(essay_id):
            acquired_lock.set()
            yield

    monkeypatch.setattr(stage_track, "_atomic", pausing)
    monkeypatch.setattr(stage_track, "stage_lock", watching)
    box: dict = {}

    def writer():
        try:
            box["result"] = essay_stage(live, "1", "draft", NEWER)
        except Exception as exc:
            box["error"] = exc

    def cloner():
        try:
            clone_sequence(ESSAY, 3, 4, reason="roll-forward")
            box["clone"] = "ok"
        except Exception as exc:
            box["clone_error"] = exc

    worker = threading.Thread(target=writer)
    copier = threading.Thread(target=cloner)
    worker.start()
    assert entered.wait(10), "the draft never paused between the note and the pointer"
    assert _raw_pointer(live)["waiting_digest"] == older["digest"]
    assert NEWER in _note(live, "1")
    copier.start()
    assert entered_lock.wait(10), "clone did not take the stage lock"
    assert not acquired_lock.wait(0.2)
    target = sequence_dir(ESSAY, 4)
    assert not target.exists()
    assert not target.with_name(".4.partial").exists()
    release.set()
    worker.join(10)
    copier.join(10)
    assert not worker.is_alive()
    assert not copier.is_alive()
    assert "error" not in box, box.get("error")
    assert box.get("clone_error") is None, box.get("clone_error")
    result = box["result"]
    assert result["ok"] is True, result
    published = _raw_pointer(f"{ESSAY}-4")
    assert _raw_pointer(live)["waiting_digest"] == result["digest"]
    assert published["current"] == "1"
    assert published["saved"] == []
    assert published.get("waiting_digest") in (None,)
    assert not (work_dir(f"{ESSAY}-4") / "tracking" / "1.md").exists()
    assert NEWER in _note(live, "1")


def test_ac4_closed_parent_notes_are_not_finals(workspace):
    """AC4: a closed parent clone does not present stages 1–10 as final notes."""
    number = 2
    parent = sequence_id(ESSAY, number)
    save_sequence_state(
        ESSAY,
        number,
        {
            "essay_id": parent,
            "sequence": number,
            "sequence_id": parent,
            "research": {"summary": {"topic": "ports"}, "full": None},
            "validations": {},
            "word": {},
            "revisions": [],
            "shelf": {},
        },
    )
    saved = list(STAGE_ORDER)
    pointer = {
        "current": "10",
        "saved": saved,
        "files": {stage: f"tracking/{stage}.md" for stage in saved},
        "closed": True,
        "revisit_open": None,
        "revisit_after_lock": False,
        "chain_armed": True,
        "revision": 20,
    }
    folder = sequence_dir(ESSAY, number) / "tracking"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "stage.json").write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")
    for stage in STAGE_ORDER:
        (folder / f"{stage}.md").write_text(
            f"# Stage {stage}\n\nStatus: final\n\n## Final look\n\nSaved {stage}.\n",
            encoding="utf-8",
        )
    draft = essay_sequence_new(ESSAY, "draft", parent)
    assert draft["ok"] is True, draft
    opened = essay_sequence_new(ESSAY, "confirm", parent)
    assert opened["ok"] is True, opened
    child = opened["sequence_id"]
    assert child == sequence_id(ESSAY, 3)
    fresh = load_pointer(child)
    assert fresh["current"] == "1"
    assert fresh["saved"] == []
    assert fresh["closed"] is False
    finals = []
    for stage in STAGE_ORDER:
        path = work_dir(child) / "tracking" / f"{stage}.md"
        if path.is_file() and "Status: final" in path.read_text(encoding="utf-8"):
            finals.append(stage)
        assert not path.is_file()
    assert finals == []
    for stage in STAGE_ORDER:
        parent_note = folder / f"{stage}.md"
        assert "Status: final" in parent_note.read_text(encoding="utf-8")
    assert load_pointer(parent)["closed"] is True
    assert load_pointer(parent)["saved"] == saved
    started = essay_stage(child, "1", "draft", LOOK)
    assert started["ok"] is True, started
    assert started["current"] == "1"
    assert "already saved" not in str(started.get("reason", ""))
    assert "Status: draft" in _note(child, "1")
    assert "Status: final" not in _note(child, "1")
