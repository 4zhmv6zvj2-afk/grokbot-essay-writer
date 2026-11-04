"""Closed parent roll-forward. Stable ids: AC1, AC2, AC3.

``essay.sequence.new`` from a closed or open parent must start the child
open on stage 1, with no writing_saved stages, so a stage 1 draft is
accepted. Research is still copied. The writing pointer is not.
"""

import json

from essay_writer.health import essay_health
from essay_writer.paths import sequence_dir
from essay_writer.projects import essay_sequence_new, save_sequence_state, sequence_id
from essay_writer.stage_track import essay_stage, load_pointer
from essay_writer.writing_basics import STAGE_ORDER

MODULE = "MOD2001BB"
PARENT = f"{MODULE}-2"
CHILD = f"{MODULE}-3"
LOOK = "The task is a short report."


def _pointer_path(module: str, number: int):
    return sequence_dir(module, number) / "tracking" / "stage.json"


def _write_pointer(module: str, number: int, pointer: dict) -> None:
    path = _pointer_path(module, number)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pointer, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _closed_pointer(number: int) -> dict:
    saved = list(STAGE_ORDER)
    return {
        "current": "10",
        "saved": saved,
        "files": {
            stage: f"Essay-writer/{MODULE}/sequences/{number}/tracking/{stage}.md"
            for stage in saved
        },
        "closed": True,
        "revisit_open": None,
        "revisit_after_lock": False,
        "chain_armed": True,
    }


def _plant_closed_parent() -> None:
    number = 2
    save_sequence_state(
        MODULE,
        number,
        {
            "essay_id": sequence_id(MODULE, number),
            "sequence": number,
            "sequence_id": sequence_id(MODULE, number),
            "research": {"summary": {"topic": "ports"}, "full": None},
            "validations": {},
            "word": {},
            "revisions": [],
            "shelf": {},
        },
    )
    _write_pointer(MODULE, number, _closed_pointer(number))
    note = sequence_dir(MODULE, number) / "tracking" / "10.md"
    note.write_text("# Stage 10 — final\n", encoding="utf-8")


def _confirm(parent: str | None = None) -> dict:
    draft = essay_sequence_new(MODULE, "draft", parent)
    assert draft["ok"] is True, draft
    assert draft["wrote"] is False
    opened = essay_sequence_new(MODULE, "confirm", parent)
    assert opened["ok"] is True, opened
    return opened


def test_ac1_closed_parent_child_is_open_with_no_writing_saved(workspace):
    """AC1: sequence.new from a closed parent does not copy closed or writing_saved."""
    _plant_closed_parent()
    parent_before = _pointer_path(MODULE, 2).read_bytes()
    opened = _confirm(PARENT)
    assert opened["sequence_id"] == CHILD
    assert opened["parent"] == PARENT
    assert opened["wrote"] is True
    assert opened["stored"] is True

    child = load_pointer(CHILD)
    assert child["closed"] is False
    assert child["saved"] == []
    assert child["current"] == "1"
    assert child["files"] == {}
    assert child["chain_armed"] is False
    assert child["revisit_open"] is None

    pack = essay_health()["packs"][0]
    assert pack["essay_id"] == CHILD
    assert pack["writing_stage"] == "1"
    assert pack["writing_saved"] == []

    state = json.loads((sequence_dir(MODULE, 3) / "state.json").read_text(encoding="utf-8"))
    assert state["branched_from"] == PARENT
    assert state["research"]["summary"]["topic"] == "ports"

    parent = load_pointer(PARENT)
    assert parent["closed"] is True
    assert parent["saved"] == list(STAGE_ORDER)
    assert parent["chain_armed"] is True
    assert _pointer_path(MODULE, 2).read_bytes() == parent_before


def test_ac2_stage1_draft_succeeds_on_closed_parent_child(workspace):
    """AC2: essay.stage stage 1 draft is accepted on that child."""
    _plant_closed_parent()
    opened = _confirm(PARENT)
    assert opened["sequence_id"] == CHILD
    assert load_pointer(CHILD)["closed"] is False
    assert load_pointer(CHILD)["saved"] == []

    draft = essay_stage(CHILD, "1", "draft", LOOK)
    assert draft["ok"] is True, draft
    assert draft["stored"] is False
    assert draft["wrote"] is True
    assert draft["closed"] is False
    assert draft["current"] == "1"
    assert draft["stage"] == "1"
    assert "already saved" not in str(draft.get("reason", ""))
    assert "card" in draft

    pointer = load_pointer(CHILD)
    assert pointer["closed"] is False
    assert pointer["saved"] == []
    assert pointer["current"] == "1"


def test_ac3_open_parent_roll_forward_still_works(workspace):
    """AC3: an open parent rolls forward onto stage 1 and still copies research."""
    first = _confirm()
    assert first["sequence_id"] == f"{MODULE}-1"
    state_path = sequence_dir(MODULE, 1) / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["research"]["summary"] = {"topic": "ports"}
    state_path.write_text(json.dumps(state), encoding="utf-8")

    second = _confirm()
    assert second["sequence_id"] == f"{MODULE}-2"
    assert second["parent"] == f"{MODULE}-1"
    assert second["wrote"] is True
    copied = json.loads((sequence_dir(MODULE, 2) / "state.json").read_text(encoding="utf-8"))
    assert copied["branched_from"] == f"{MODULE}-1"
    assert copied["research"]["summary"]["topic"] == "ports"
    assert not _pointer_path(MODULE, 2).is_file()
    fresh = load_pointer(f"{MODULE}-2")
    assert fresh["closed"] is False
    assert fresh["saved"] == []
    assert fresh["current"] == "1"
    draft = essay_stage(f"{MODULE}-2", "1", "draft", LOOK)
    assert draft["ok"] is True, draft
    assert draft["current"] == "1"
    assert "already saved" not in str(draft.get("reason", ""))

    progress = {
        "current": "3",
        "saved": ["1", "2"],
        "files": {"1": f"Essay-writer/{MODULE}/sequences/2/tracking/1.md"},
        "closed": False,
        "revisit_open": None,
        "revisit_after_lock": False,
        "chain_armed": False,
    }
    _write_pointer(MODULE, 2, progress)
    parent_before = _pointer_path(MODULE, 2).read_bytes()
    third = _confirm(f"{MODULE}-2")
    assert third["sequence_id"] == f"{MODULE}-3"
    assert third["parent"] == f"{MODULE}-2"
    assert third["wrote"] is True
    kept = load_pointer(f"{MODULE}-3")
    assert kept["closed"] is False
    assert kept["saved"] == []
    assert kept["current"] == "1"
    assert kept["files"] == {}
    rolled = json.loads((sequence_dir(MODULE, 3) / "state.json").read_text(encoding="utf-8"))
    assert rolled["branched_from"] == f"{MODULE}-2"
    assert rolled["research"]["summary"]["topic"] == "ports"
    assert load_pointer(f"{MODULE}-2")["saved"] == ["1", "2"]
    assert load_pointer(f"{MODULE}-2")["closed"] is False
    assert _pointer_path(MODULE, 2).read_bytes() == parent_before
