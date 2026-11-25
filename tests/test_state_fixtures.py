"""Shipped 0.9 sequence snapshots still load.

The state object and the stage pointer object are the same shape from 0.9.14
through 0.9.19. These fixtures are that shape at three positions: stage 1
open, stage 2 open, and stage 6 with a saved first draft. A damaged file and
an unknown field are recorded. The load does not rewrite the file.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from helpers import open_sequence, picked

from essay_writer.incident import incident_path
from essay_writer.paths import work_dir
from essay_writer.stage_llm import STAGE_ORDER
from essay_writer.stage_note import _note_look
from essay_writer.stage_state import blank_pointer, load_pointer
from essay_writer.stage_track import essay_stage
from essay_writer.state import load_state, record_damage_refusal
from essay_writer.word import write_first_draft_word

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "state"
LOOK = "The corridor is the subject of this stage."


def _plant(seq: str, release: str) -> None:
    source = FIXTURES / release
    dest = work_dir(seq)
    shutil.copyfile(source / "state.json", dest / "state.json")
    tracking = dest / "tracking"
    tracking.mkdir(parents=True, exist_ok=True)
    journal = tracking / ".stage.commit"
    if journal.is_file():
        journal.unlink()
    for path in (source / "tracking").iterdir():
        shutil.copyfile(path, tracking / path.name)


def _codes() -> list[str]:
    path = incident_path()
    if not path.is_file():
        return []
    return [json.loads(line)["code"] for line in path.read_text(encoding="utf-8").splitlines()]


def _advance(seq: str, stage: str, look: str) -> dict:
    draft = essay_stage(seq, stage, "draft", look)
    assert draft.get("ok") is True, draft
    saved = essay_stage(seq, stage, "confirm", **picked(draft))
    if saved.get("stored") is True:
        return saved
    pressed = essay_stage(seq, stage, "confirm", look=look)
    saved = essay_stage(
        seq,
        stage,
        "confirm",
        cardAction=pressed.get("cardAction"),
        cardDigest=pressed.get("cardDigest"),
    )
    return saved


def test_shipped_snapshots_load_read_and_advance(workspace) -> None:
    """0.9.14 and 0.9.18 load, the look is the planted sentence, and one stage advances."""
    expectations = {
        "0.9.14": ("1", "2", LOOK),
        "0.9.18": ("2", "3", "Purpose and scope stay with the brief."),
    }
    for release, (stage, following, look) in expectations.items():
        seq = open_sequence()
        _plant(seq, release)
        assert load_state(seq)["essay_id"] == seq
        assert load_pointer(seq)["current"] == stage
        assert _note_look(seq, stage) == look
        saved = _advance(seq, stage, look)
        assert saved.get("stored") is True, saved
        assert load_pointer(seq)["current"] == following
        assert "guidance-only" not in _codes()


def test_the_current_snapshot_writes_word_and_advances(workspace) -> None:
    """0.9.19 is at stage 6 with a saved draft. Word applies, then stage 6 advances."""
    seq = open_sequence()
    _plant(seq, "0.9.19")
    state = load_state(seq)
    assert state["essay_id"] == seq
    assert state["saved_pack"]["title"] == "Kept draft"
    assert load_pointer(seq)["current"] == "6"
    look = _note_look(seq, "5")
    assert look == "The corridor depends on a narrow strait."
    written = write_first_draft_word(seq)
    assert written["wrote"] is True, written
    assert Path(str(work_dir(seq) / "output" / f"{seq}.docx")).is_file()
    saved = _advance(seq, "6", "The draft is saved in Word.")
    assert saved.get("stored") is True, saved
    assert load_pointer(seq)["current"] == "7"
    assert "guidance-only" not in _codes()


def test_an_unknown_pointer_field_survives_a_save(workspace) -> None:
    seq = open_sequence()
    path = work_dir(seq) / "tracking" / "stage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    pointer = blank_pointer()
    pointer["shipped_by"] = "0.9.14"
    path.write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")
    before = path.read_bytes()
    loaded = load_pointer(seq)
    assert loaded["shipped_by"] == "0.9.14"
    assert path.read_bytes() == before
    assert "pointer-unknown-field" in _codes()
    saved = _advance(seq, "1", LOOK)
    assert saved.get("stored") is True, saved
    again = json.loads(path.read_text(encoding="utf-8"))
    assert again["shipped_by"] == "0.9.14"
    assert again["current"] == "2"


def test_an_unknown_state_field_is_kept(workspace) -> None:
    seq = open_sequence()
    path = work_dir(seq) / "state.json"
    state = load_state(seq)
    state["legacy_marker"] = "kept"
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    before = path.read_bytes()
    loaded = load_state(seq)
    assert loaded["legacy_marker"] == "kept"
    assert path.read_bytes() == before
    assert "state-unknown-field" in _codes()


def test_a_missing_pointer_field_is_filled_without_rewriting(workspace) -> None:
    seq = open_sequence()
    path = work_dir(seq) / "tracking" / "stage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    pointer = blank_pointer()
    del pointer["room_grant"]
    path.write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")
    before = path.read_bytes()
    loaded = load_pointer(seq)
    assert loaded["room_grant"] is None
    assert "room_grant" not in json.loads(path.read_text(encoding="utf-8"))
    assert path.read_bytes() == before
    assert "pointer-field-filled" in _codes()


def test_a_missing_state_field_is_filled_without_rewriting(workspace) -> None:
    seq = open_sequence()
    path = work_dir(seq) / "state.json"
    state = load_state(seq)
    del state["shelf"]
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    before = path.read_bytes()
    loaded = load_state(seq)
    assert loaded["shelf"] == {}
    assert "shelf" not in json.loads(path.read_text(encoding="utf-8"))
    assert path.read_bytes() == before
    assert "state-field-filled" in _codes()


def test_an_unknown_current_stays_on_disk(workspace) -> None:
    seq = open_sequence()
    path = work_dir(seq) / "tracking" / "stage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    pointer = blank_pointer()
    pointer["current"] = "nope"
    path.write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")
    before = path.read_bytes()
    loaded = load_pointer(seq)
    assert loaded["current"] == "1"
    assert path.read_bytes() == before
    assert "pointer-unknown-current" in _codes()


def test_a_saved_value_that_is_not_a_list_stays_on_disk(workspace) -> None:
    seq = open_sequence()
    path = work_dir(seq) / "tracking" / "stage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    pointer = blank_pointer()
    pointer["saved"] = "1"
    path.write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")
    before = path.read_bytes()
    loaded = load_pointer(seq)
    assert loaded["saved"] == []
    assert path.read_bytes() == before
    assert "pointer-field-dropped" in _codes()


def test_an_unknown_saved_entry_and_file_key_survive_an_advance(workspace) -> None:
    """An unknown saved entry and an unknown files key stay through load, advance, and save.

    The stage machine still stores stage 1 and moves to a real stage.
    """
    seq = open_sequence()
    path = work_dir(seq) / "tracking" / "stage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    pointer = blank_pointer()
    pointer["saved"] = ["kept-earlier"]
    pointer["files"] = {"kept-file": "notes/kept.txt"}
    path.write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")
    loaded = load_pointer(seq)
    assert "kept-earlier" in loaded["saved"]
    assert loaded["files"]["kept-file"] == "notes/kept.txt"
    saved = _advance(seq, "1", LOOK)
    assert saved.get("stored") is True, saved
    again = json.loads(path.read_text(encoding="utf-8"))
    assert "kept-earlier" in again["saved"]
    assert "1" in again["saved"]
    assert again["files"]["kept-file"] == "notes/kept.txt"
    assert again["current"] in STAGE_ORDER


def test_a_normalized_unknown_current_is_written_as_a_stage(workspace) -> None:
    """A current value that is not a stage is saved as a usable stage on the next save."""
    seq = open_sequence()
    path = work_dir(seq) / "tracking" / "stage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    pointer = blank_pointer()
    pointer["current"] = "nope"
    path.write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")
    loaded = load_pointer(seq)
    assert loaded["current"] == "1"
    assert json.loads(path.read_text(encoding="utf-8"))["current"] == "nope"
    saved = _advance(seq, "1", LOOK)
    assert saved.get("stored") is True, saved
    again = json.loads(path.read_text(encoding="utf-8"))
    assert again["current"] == "2"
    assert again["current"] in STAGE_ORDER


def test_a_damaged_state_file_is_refused_and_not_rewritten(workspace) -> None:
    seq = open_sequence()
    path = work_dir(seq) / "state.json"
    path.write_text("{not json", encoding="utf-8")
    refused = record_damage_refusal(seq)
    assert refused is not None
    assert refused["refused"] == "state"
    assert path.read_text(encoding="utf-8") == "{not json"
    assert "state-damaged" in _codes()
