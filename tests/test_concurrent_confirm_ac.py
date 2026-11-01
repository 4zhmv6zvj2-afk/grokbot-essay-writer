"""Concurrent confirm. Stable ids: AC1, AC2, AC3, AC4, AC5.

Overlapping essay.stage Confirms cannot roll current or saved backward.
A superseded cardDigest for the same stage does not store that older look.
"""

import inspect
import threading

from helpers import open_sequence

from essay_writer import stage_track
from essay_writer.paths import work_dir
from essay_writer.shells import front_office_call
from essay_writer.stage_track import essay_stage, load_pointer

LOOK = "Look A stays."
NEWER = "Look B replaces."


def _note(seq: str, stage: str) -> str:
    return (work_dir(seq) / "tracking" / f"{stage}.md").read_text(encoding="utf-8")


def _confirm(seq: str, stage: str, draft: dict, *, look: str | None = None, press: bool = False) -> dict:
    text = look
    if press:
        text = f"Press Confirm for Stage {stage}"
    return essay_stage(
        seq,
        stage,
        "confirm",
        text,
        cardAction="confirm",
        cardDigest=draft["digest"],
    )


def test_ac1_concurrent_confirm_cannot_roll_pointer_back(workspace, monkeypatch):
    """AC1: a Confirm that loaded an older pointer cannot roll current or saved backward."""
    seq = open_sequence()
    draft = essay_stage(seq, "1", "draft", LOOK)
    assert draft["ok"] is True, draft
    digest = draft["digest"]
    entered = threading.Event()
    release = threading.Event()
    real = stage_track._commit_pointer
    state = {"used": False}

    def pausing(essay_id, base, proposed, **kwargs):
        if not state["used"]:
            state["used"] = True
            entered.set()
            assert release.wait(10), "the overlapping confirm did not release the first writer"
        return real(essay_id, base, proposed, **kwargs)

    monkeypatch.setattr(stage_track, "_commit_pointer", pausing)
    box: dict = {}

    def runner():
        try:
            box["result"] = essay_stage(
                seq,
                "1",
                "confirm",
                None,
                cardAction="confirm",
                cardDigest=digest,
            )
        except Exception as exc:
            box["error"] = exc

    worker = threading.Thread(target=runner)
    worker.start()
    assert entered.wait(10), "the first Confirm never reached the pointer write"
    raced = essay_stage(seq, "1", "confirm", None, cardAction="confirm", cardDigest=digest)
    assert raced["ok"] is True, raced
    assert raced["stored"] is True
    assert load_pointer(seq)["current"] == "2"
    assert load_pointer(seq)["saved"] == ["1"]
    draft2 = essay_stage(seq, "2", "draft", "Stage two stays.")
    assert draft2["ok"] is True, draft2
    saved2 = _confirm(seq, "2", draft2, press=True)
    assert saved2["ok"] is True, saved2
    assert saved2["stored"] is True
    assert load_pointer(seq)["current"] == "3"
    assert load_pointer(seq)["saved"] == ["1", "2"]
    release.set()
    worker.join(10)
    assert not worker.is_alive()
    assert "error" not in box, box.get("error")
    lost = box["result"]
    assert lost["ok"] is False, lost
    assert lost["stored"] is False
    assert lost["advanced"] is False
    assert lost["refused"] == "stage"
    pointer = load_pointer(seq)
    assert pointer["current"] == "3"
    assert pointer["saved"] == ["1", "2"]
    assert "2" in pointer["saved"]
    note2 = _note(seq, "2")
    assert "Status: final" in note2
    assert "Stage two stays." in note2


def test_ac2_stale_pointer_write_loses(workspace):
    """AC2: a pointer write from an older revision is skipped. The newer pointer stays."""
    seq = open_sequence()
    draft = essay_stage(seq, "1", "draft", LOOK)
    early = load_pointer(seq)
    saved = _confirm(seq, "1", draft)
    assert saved["stored"] is True, saved
    draft2 = essay_stage(seq, "2", "draft", "Stage two stays.")
    pressed = _confirm(seq, "2", draft2, press=True)
    assert pressed["stored"] is True, pressed
    assert load_pointer(seq)["current"] == "3"
    rollback = {
        "current": "2",
        "saved": ["1"],
        "files": {"1": "tracking/1.md"},
        "closed": False,
        "revisit_open": None,
        "revisit_after_lock": False,
        "chain_armed": False,
        "room_grant": None,
        "room_lock": True,
    }
    lost = stage_track._commit_pointer(seq, early, rollback)
    assert lost is None
    fresh = load_pointer(seq)
    assert fresh["current"] == "3"
    assert fresh["saved"] == ["1", "2"]
    assert fresh["revision"] > early["revision"]
    assert "Status: final" in _note(seq, "2")
    assert "Stage two stays." in _note(seq, "2")


def test_ac3_superseded_card_digest_refused(workspace):
    """AC3: an older look's cardDigest does not store or advance. The latest body does."""
    seq = open_sequence()
    first = essay_stage(seq, "1", "draft", LOOK)
    second = essay_stage(seq, "1", "draft", NEWER)
    assert first["ok"] is True and second["ok"] is True
    assert first["digest"] != second["digest"]
    assert "Status: draft" in _note(seq, "1")
    assert NEWER in _note(seq, "1")
    stale = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "1",
            "confirmPhase": "confirm",
            "cardAction": "confirm",
            "cardDigest": first["digest"],
        },
    )
    assert stale["ok"] is False, stale
    assert stale["refused"] == "confirm"
    assert stale["stored"] is False
    assert stale["advanced"] is False
    assert stale.get("cardDigest") == second["digest"]
    assert "older draft" in stale["reason"]
    pointer = load_pointer(seq)
    assert pointer["current"] == "1"
    assert pointer["saved"] == []
    note = _note(seq, "1")
    assert "Status: final" not in note
    assert NEWER in note
    assert LOOK not in note
    typed = essay_stage(
        seq,
        "1",
        "confirm",
        LOOK,
        cardAction="confirm",
        cardDigest=first["digest"],
    )
    assert typed["ok"] is False, typed
    assert typed["stored"] is False
    assert load_pointer(seq)["current"] == "1"
    assert load_pointer(seq)["saved"] == []
    fresh = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "1",
            "confirmPhase": "confirm",
            "cardAction": "confirm",
            "cardDigest": second["digest"],
        },
    )
    assert fresh["ok"] is True, fresh
    assert fresh["stored"] is True
    assert fresh["current"] == "2"
    final = _note(seq, "1")
    assert "Status: final" in final
    assert NEWER in final
    assert LOOK not in final
    assert load_pointer(seq)["saved"] == ["1"]
    assert load_pointer(seq)["current"] == "2"


def test_ac4_double_confirm_and_moved_stage_still_refuse(workspace):
    """AC4: a second Confirm of the same digest, and a stage-N digest after the move, stay refused."""
    seq = open_sequence()
    draft = essay_stage(seq, "1", "draft", LOOK)
    saved = _confirm(seq, "1", draft)
    assert saved["stored"] is True, saved
    assert load_pointer(seq)["current"] == "2"
    again = _confirm(seq, "1", draft)
    assert again["ok"] is False, again
    assert again["refused"] == "stage"
    assert again["stored"] is False
    assert again["advanced"] is False
    assert load_pointer(seq)["saved"] == ["1"]
    assert load_pointer(seq)["current"] == "2"
    draft2 = essay_stage(seq, "2", "draft", "Stage two stays.")
    replay = essay_stage(
        seq,
        "2",
        "confirm",
        None,
        cardAction="confirm",
        cardDigest=draft["digest"],
    )
    assert replay["ok"] is False, replay
    assert replay["refused"] == "confirm-card"
    assert replay["stored"] is False
    assert replay["advanced"] is False
    assert load_pointer(seq)["current"] == "2"
    assert load_pointer(seq)["saved"] == ["1"]
    late = _confirm(seq, "1", draft)
    assert late["ok"] is False, late
    assert late["refused"] == "stage"
    assert late["stored"] is False
    assert load_pointer(seq)["saved"] == ["1"]
    assert load_pointer(seq)["current"] == "2"
    assert "Status: final" not in _note(seq, "2")
    pressed = _confirm(seq, "2", draft2, press=True)
    assert pressed["stored"] is True, pressed
    assert load_pointer(seq)["current"] == "3"
    assert load_pointer(seq)["saved"] == ["1", "2"]


def test_ac5_commit_is_shared_for_later_stages(workspace, monkeypatch):
    """AC5: stages 1 and 2 Confirm through the same pointer commit, not a stage-1 branch."""
    seen: list[str] = []
    real = stage_track._commit_pointer

    def spy(essay_id, base, proposed, **kwargs):
        current = base.get("current")
        if isinstance(current, str):
            seen.append(current)
        return real(essay_id, base, proposed, **kwargs)

    monkeypatch.setattr(stage_track, "_commit_pointer", spy)
    seq = open_sequence()
    first = essay_stage(seq, "1", "draft", "Stage one.")
    saved = _confirm(seq, "1", first)
    assert saved["stored"] is True, saved
    older = essay_stage(seq, "2", "draft", "Stage two old.")
    newer = essay_stage(seq, "2", "draft", "Stage two new.")
    assert older["digest"] != newer["digest"]
    stale = essay_stage(
        seq,
        "2",
        "confirm",
        None,
        cardAction="confirm",
        cardDigest=older["digest"],
    )
    assert stale["ok"] is False, stale
    assert stale["refused"] == "confirm"
    assert stale["stored"] is False
    assert load_pointer(seq)["current"] == "2"
    assert "Stage two new." in _note(seq, "2")
    assert "Status: final" not in _note(seq, "2")
    pressed = _confirm(seq, "2", newer, press=True)
    assert pressed["stored"] is True, pressed
    assert load_pointer(seq)["current"] == "3"
    assert load_pointer(seq)["saved"] == ["1", "2"]
    assert "Status: final" in _note(seq, "2")
    assert "Stage two new." in _note(seq, "2")
    assert "1" in seen
    assert "2" in seen
    assert "_save_pointer" not in inspect.getsource(stage_track._run_stage)
    assert "_commit_pointer" in inspect.getsource(stage_track._save_confirm)
    assert "_commit_pointer" in inspect.getsource(stage_track._store_stage)
    assert "stage ==" not in inspect.getsource(stage_track._commit_pointer)
