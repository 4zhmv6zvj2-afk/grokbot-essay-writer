"""Inherited locks resolve only after a save, and damaged records stop the tool.

An inherited stage 2 or 3 lock stays pending until revise, re-lock, or keep
actually stores. A damaged stage confirm record is not applied and the save
does not continue. A damaged state file is not treated as an empty sequence.
A missing file is not damage. A valid confirm record left by a torn save is
still finished, and a valid state file still loads its stored fields.
"""

import json

import pytest
from helpers import open_sequence, picked
from test_fo_chat_locks import (
    ENTRY_LOCK,
    MODULE,
    _child_from,
    _look,
    _parent_with_stage2_lock,
    _save_stage,
)

from essay_writer.fo_chat_locks import inherited_lock_pending, inherited_locks
from essay_writer.health import essay_health
from essay_writer.paths import essay_dir, work_dir
from essay_writer.revise import essay_revise
from essay_writer.stage_state import STAGE_COMMIT
from essay_writer.stage_track import essay_stage
from essay_writer.state import load_state, save_state

DAMAGED_COMMIT = "last confirm record was damaged"
STATE_DAMAGED = "state file is damaged"


def _pending(seq: str, stage: str) -> dict:
    row = inherited_lock_pending(seq, stage)
    assert row is not None, inherited_locks(seq)
    assert row.get("resolved") is not True
    return row


def _resolved(seq: str, stage: str) -> None:
    assert inherited_lock_pending(seq, stage) is None
    rows = [row for row in inherited_locks(seq) if row["stage"] == stage]
    assert rows
    assert rows[0]["resolved"] is True


def _ask_again(seq: str, stage: str) -> dict:
    asked = essay_stage(seq, stage, "draft")
    assert asked.get("stored") is False
    assert asked.get("prior_saved_lock"), asked
    assert asked["prior_saved_lock"]["stage"] == stage
    return asked


def _child_for(stage: str) -> str:
    parent = _parent_with_stage2_lock()
    if stage == "3":
        _save_stage(parent, "3", _look(parent, ENTRY_LOCK))
    child = _child_from(parent)
    if stage == "3":
        kept = essay_stage(child, "2", "draft", lockChoice="keep")
        assert kept["stored"] is True, kept
        assert inherited_lock_pending(child, "2") is None
        assert inherited_lock_pending(child, "3") is not None
    return child


def _choice_does_not_store(seq: str, stage: str, choice: str) -> dict:
    chosen = essay_stage(seq, stage, "draft", lockChoice=choice)
    assert chosen.get("stored") is not True, chosen
    _pending(seq, stage)
    return chosen


def _refused_follow_up(seq: str, stage: str, choice: str, chosen: dict) -> None:
    refused = essay_stage(
        seq,
        stage,
        "confirm",
        lockChoice=choice,
        cardAction="not_yet",
        cardDigest=chosen.get("digest"),
    )
    assert refused.get("ok") is False, refused
    assert refused.get("stored") is not True
    _pending(seq, stage)
    _ask_again(seq, stage)


def _journal(seq: str):
    return work_dir(seq) / STAGE_COMMIT


def _note(seq: str) -> str:
    return (work_dir(seq) / "tracking" / "1.md").read_text(encoding="utf-8")


def _state(seq: str):
    return work_dir(seq) / "state.json"


@pytest.mark.parametrize("case_id", ["ew-hunt-s3-ac1"])
@pytest.mark.parametrize("stage", ["2", "3"])
def test_ew_hunt_s3_ac1(case_id, stage, workspace):
    """Revise stays pending when the following save is refused or does not store."""
    assert case_id == "ew-hunt-s3-ac1"
    child = _child_for(stage)
    chosen = _choice_does_not_store(child, stage, "revise")
    _refused_follow_up(child, stage, "revise", chosen)


@pytest.mark.parametrize("case_id", ["ew-hunt-s3-ac2"])
@pytest.mark.parametrize("stage", ["2", "3"])
def test_ew_hunt_s3_ac2(case_id, stage, workspace):
    """Re-lock stays pending when the following save is refused or does not store."""
    assert case_id == "ew-hunt-s3-ac2"
    child = _child_for(stage)
    chosen = _choice_does_not_store(child, stage, "relock")
    _refused_follow_up(child, stage, "relock", chosen)


@pytest.mark.parametrize("case_id", ["ew-hunt-s3-ac3"])
@pytest.mark.parametrize("stage", ["2", "3"])
def test_ew_hunt_s3_ac3(case_id, stage, workspace):
    """Keep stays pending when that save is refused or does not store."""
    assert case_id == "ew-hunt-s3-ac3"
    child = _child_for(stage)
    brief = essay_dir(MODULE) / "brief.md"
    original = brief.read_text(encoding="utf-8")
    brief.write_text(
        original.replace(
            "Assignment task: Write four entries.",
            "Assignment task: Write four entries about a different harbour question.",
        ),
        encoding="utf-8",
    )
    refused = essay_stage(child, stage, "draft", lockChoice="keep")
    brief.write_text(original, encoding="utf-8")
    assert refused.get("ok") is False, refused
    assert refused.get("stored") is not True
    _pending(child, stage)
    _ask_again(child, stage)


@pytest.mark.parametrize("case_id", ["ew-hunt-s3-ac4"])
@pytest.mark.parametrize("stage", ["2", "3"])
@pytest.mark.parametrize("choice", ["revise", "relock", "keep"])
def test_ew_hunt_s3_ac4(case_id, stage, choice, workspace):
    """A stored revise, re-lock, or keep resolves that inherited lock."""
    assert case_id == "ew-hunt-s3-ac4"
    child = _child_for(stage)
    if choice == "keep":
        saved = essay_stage(child, stage, "draft", lockChoice="keep")
    else:
        chosen = essay_stage(child, stage, "draft", lockChoice=choice)
        assert chosen.get("stored") is not True, chosen
        saved = essay_stage(child, stage, "confirm", **picked(chosen))
    assert saved.get("ok") is True, saved
    assert saved.get("stored") is True, saved
    _resolved(child, stage)
    again = essay_stage(child, stage, "draft")
    assert again.get("prior_saved_lock") is None
    assert "prior_saved_lock" not in again


@pytest.mark.parametrize("case_id", ["ew-hunt-s3-ac5"])
def test_ew_hunt_s3_ac5(case_id, workspace):
    """A damaged confirm record stops the save and is not applied."""
    assert case_id == "ew-hunt-s3-ac5"
    seq = open_sequence()
    first = essay_stage(seq, "1", "draft", "Look A stays.")
    assert first["ok"] is True, first
    note_before = _note(seq)
    journal = _journal(seq)
    journal.write_bytes(b"{not json")
    saved = essay_stage(seq, "1", "draft", "Look B replaces.")
    assert saved["ok"] is False, saved
    assert saved["stored"] is False
    assert saved.get("wrote") is False
    assert DAMAGED_COMMIT in saved["reason"].casefold()
    assert journal.read_bytes() == b"{not json"
    assert list(journal.parent.glob(".stage.commit.damaged-*")) == []
    assert _note(seq) == note_before
    assert "Look B replaces." not in _note(seq)

    journal.write_text('{"pointer": {}}\n', encoding="utf-8")
    record = essay_stage(seq, "1", "draft", "Look B replaces.")
    assert record["ok"] is False, record
    assert record["stored"] is False
    assert DAMAGED_COMMIT in record["reason"].casefold()
    assert "Look B replaces." not in _note(seq)
    assert journal.read_text(encoding="utf-8") == '{"pointer": {}}\n'

    journal.write_text(
        '{"pointer": {"current": "1"}, "note": "nope", "note_text": "APPLIED BADLY"}\n',
        encoding="utf-8",
    )
    noted = essay_stage(seq, "1", "draft", "Look B replaces.")
    assert noted["ok"] is False, noted
    assert noted["stored"] is False
    assert "APPLIED BADLY" not in _note(seq)
    assert list(journal.parent.glob(".stage.commit.damaged-*")) == []

    _state(seq).write_text("{not json", encoding="utf-8")
    journal.write_bytes(b"{not json")
    stopped = essay_stage(seq, "1", "draft", "Look B replaces.")
    assert isinstance(stopped, dict)
    assert stopped["ok"] is False, stopped
    assert stopped["stored"] is False
    reason = stopped["reason"].casefold()
    assert DAMAGED_COMMIT in reason
    assert STATE_DAMAGED in reason
    assert journal.read_bytes() == b"{not json"
    assert _state(seq).read_text(encoding="utf-8") == "{not json"
    assert "Look B replaces." not in _note(seq)
    assert list(journal.parent.glob(".stage.commit.damaged-*")) == []


@pytest.mark.parametrize("case_id", ["ew-hunt-s3-ac6"])
@pytest.mark.parametrize("body", ["{not json", "[]\n", "null\n", '"text"\n'])
def test_ew_hunt_s3_ac6(case_id, body, workspace):
    """A damaged state file stops the tools that would load it."""
    assert case_id == "ew-hunt-s3-ac6"
    seq = open_sequence()
    essay_stage(seq, "1", "draft", "A sentence before the state file is damaged.")
    path = _state(seq)
    path.write_text(body, encoding="utf-8")
    revised = essay_revise(seq, "Shorten the opening.", "draft")
    assert isinstance(revised, dict)
    assert revised["ok"] is False, revised
    assert revised["stored"] is False
    assert STATE_DAMAGED in revised["reason"].casefold()
    assert "nothing is confirmed yet" not in revised["reason"].casefold()
    assert path.read_text(encoding="utf-8") == body

    staged = essay_stage(seq, "1", "draft", "This save must not treat the sequence as empty.")
    assert isinstance(staged, dict)
    assert staged["ok"] is False, staged
    assert staged["stored"] is False
    assert STATE_DAMAGED in staged["reason"].casefold()
    assert path.read_text(encoding="utf-8") == body


@pytest.mark.parametrize("case_id", ["ew-hunt-s3-ac7"])
def test_ew_hunt_s3_ac7(case_id, workspace):
    """Missing files are not damage. A valid torn record and a valid state still load."""
    assert case_id == "ew-hunt-s3-ac7"
    seq = open_sequence()
    journal = _journal(seq)
    if journal.exists():
        journal.unlink()
    opened = essay_stage(seq, "1", "draft", "A new sequence can still save.")
    assert opened["ok"] is True, opened
    confirmed = essay_stage(seq, "1", "confirm", **picked(opened))
    assert confirmed["ok"] is True, confirmed
    assert confirmed["stored"] is True

    bare = open_sequence()
    _state(bare).unlink()
    if _journal(bare).exists():
        _journal(bare).unlink()
    saved = essay_stage(bare, "1", "draft", "A missing state file still opens.")
    assert saved["ok"] is True, saved
    assert STATE_DAMAGED not in json.dumps(saved).casefold()
    empty = essay_revise(bare, "Shorten the opening.", "draft")
    assert empty["ok"] is False, empty
    assert "nothing is confirmed yet" in empty["reason"].casefold()
    assert STATE_DAMAGED not in empty["reason"].casefold()

    torn = open_sequence()
    draft = essay_stage(torn, "1", "draft", "Original note.")
    assert draft["ok"] is True, draft
    pointer = json.loads((work_dir(torn) / "tracking" / "stage.json").read_text(encoding="utf-8"))
    sentence = "Torn confirm kept this sentence."
    _journal(torn).write_text(
        json.dumps(
            {
                "note": "tracking/1.md",
                "note_text": f"Status: draft\n\n{sentence}\n",
                "pointer": pointer,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    report = essay_health()
    assert report["ok"] is True, report
    assert sentence in _note(torn)
    assert not _journal(torn).exists()

    valid = open_sequence()
    state = load_state(valid)
    state["word"] = {"harbour": {"ok": True}}
    state["registration_number"] = "REG-4481"
    save_state(valid, state)
    loaded = essay_revise(valid, "Shorten the opening.", "draft")
    assert loaded.get("ok") is True, loaded
    assert STATE_DAMAGED not in json.dumps(loaded).casefold()
    assert "nothing is confirmed yet" not in json.dumps(loaded).casefold()
    assert load_state(valid)["registration_number"] == "REG-4481"
    assert load_state(valid)["word"]["harbour"]["ok"] is True
