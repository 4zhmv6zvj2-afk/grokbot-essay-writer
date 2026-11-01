"""Confirm atomic architecture. One write moves the pointer and the next card.

AC1: a confirm that expects a next card returns that cardDigest with the
pointer advanced, or it does not advance.
AC2: a diary task that says "Entry 1…" still returns the stage 2 card from
the live door, or the pointer stays on stage 1.
AC3: stage 5 and the last stage may advance with no card, and they say so.
AC4: Cursor and Grok Build share that Confirm path.
AC5: a closed pack or the wrong sequence does not mint a postable card.
"""

import inspect
import json

from helpers import open_sequence, plant_renderable_pack

from essay_writer.build_office import stage_launch
from essay_writer.confirm import save_draft
from essay_writer.cursor_office import cursor_stage_launch, stage_host_launch
from essay_writer.paths import essay_dir, work_dir
from essay_writer.server import HANDLERS
from essay_writer.setup import SHELL_CURSOR, SHELL_GROK_BUILD
from essay_writer.shells import cursor_shell, front_office, mount_handler
from essay_writer.specialists.grok_bot import basics_pass_lines
from essay_writer.stage_track import (
    TOOL,
    _draft_next_card,
    _save_confirm,
    essay_stage,
    load_pointer,
)
from essay_writer.writing_basics import STAGE_ORDER

DIARY = """
Assignment title: Individual reflective diary

Module title: Practice module
Module code: RPT5001AA

Aim: Understand the practice by reflecting on your own decisions.

Assignment task: Entry 1 names the first decision. Write four entries. Each entry names one decision and critically analyses it with theory and evidence.

The main body of the report is the diary. First person is allowed.

One entry for each occasion: North occasion, South occasion, East occasion, and West occasion.

# Marking criteria/feedback form

| Criterion | 0-39 | 40-49 | 50-59 | 60-69 | 70+ |
| --- | --- | --- | --- | --- | --- |
| Clarity of the decisions | thin | partial | sound | clear | exact and evidenced |
"""
LOOK = "The task is a short report on the corridor."
LAST = "The last stage is saved here."


def _brief(module: str, text: str) -> None:
    folder = essay_dir(module)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(text, encoding="utf-8")


def _live(**kwargs):
    """The function the stdio server mounts for essay.stage."""
    return mount_handler("essay.stage")(**kwargs)


def _plant(seq: str, current: str, saved: list[str]) -> None:
    pointer = {
        "current": current,
        "saved": saved,
        "files": {},
        "closed": False,
        "revisit_open": None,
        "revisit_after_lock": False,
        "chain_armed": False,
        "room_grant": None,
        "room_lock": False,
        "waiting_stage": None,
        "waiting_digest": None,
        "revision": 4,
    }
    path = work_dir(seq) / "tracking" / "stage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pointer), encoding="utf-8")


def _close(seq: str) -> str:
    pointer = load_pointer(seq)
    pointer["current"] = "10"
    pointer["saved"] = list(STAGE_ORDER)
    pointer["closed"] = True
    pointer["waiting_stage"] = None
    pointer["waiting_digest"] = None
    path = work_dir(seq) / "tracking" / "stage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pointer), encoding="utf-8")
    return save_draft(
        seq,
        TOOL,
        {"essay_id": seq, "stage": "10", "look": LAST},
        {"stage": "10"},
    )


def test_ac1_confirm_returns_card_or_does_not_advance(workspace, monkeypatch):
    """AC1. Next card and pointer move in one write, or the pointer stays."""
    seq = open_sequence("MOD1004AA")
    draft = _live(essay_id=seq, stage="1", confirmPhase="draft", look=LOOK)
    assert draft["ok"] is True, draft
    before = load_pointer(seq)
    saved = _live(
        essay_id=seq,
        stage="1",
        confirmPhase="confirm",
        cardAction="confirm",
        cardDigest=draft["cardDigest"],
    )
    assert saved["ok"] is True, saved
    assert saved["stored"] is True
    assert saved["advanced"] is True
    assert saved["current"] == "2"
    assert saved["card"]["stage"] == "2"
    assert saved["cardDigest"] == saved["card"]["digest"]
    assert len(saved["cardDigest"]) == 64
    assert saved["digest"] != saved["cardDigest"]
    pointer = load_pointer(seq)
    assert pointer["revision"] == before["revision"] + 1
    assert pointer["current"] == "2"
    assert pointer["saved"] == ["1"]
    assert pointer["waiting_stage"] == "2"
    assert pointer["waiting_digest"] == saved["cardDigest"]

    held_seq = open_sequence("RPT1008AA")
    opened = _live(essay_id=held_seq, stage="1", confirmPhase="draft", look=LOOK)
    assert opened["ok"] is True, opened
    held_before = load_pointer(held_seq)

    def _fail(essay_id: str, following: str) -> dict:
        return {
            "ok": False,
            "refused": "named-parts",
            "reason": "The brief names these parts: North occasion.",
        }

    monkeypatch.setattr("essay_writer.stage_track._draft_next_card", _fail)
    refused = _live(
        essay_id=held_seq,
        stage="1",
        confirmPhase="confirm",
        cardAction="confirm",
        cardDigest=opened["cardDigest"],
    )
    assert refused.get("stored") is not True
    assert refused.get("advanced") is not True
    assert "not saved" in refused["reason"]
    stayed = load_pointer(held_seq)
    assert stayed["revision"] == held_before["revision"]
    assert stayed["current"] == "1"
    assert stayed["saved"] == []
    assert stayed["waiting_stage"] == "1"
    assert stayed["waiting_digest"] == held_before["waiting_digest"]
    assert refused.get("card", {}).get("stage") == "1"
    assert refused.get("cardDigest") == stayed["waiting_digest"]


def test_ac2_diary_entry_1_confirm_returns_stage2_card_or_stays(workspace):
    """AC2. Live door. A task that says Entry 1 does not advance without a card."""
    _brief("RPT5001AA", DIARY)
    seq = open_sequence("RPT5001AA")
    look = "\n".join(basics_pass_lines(seq))
    draft = _live(essay_id=seq, stage="1", confirmPhase="draft", look=look)
    assert draft["ok"] is True, draft
    before = load_pointer(seq)
    saved = _live(
        essay_id=seq,
        stage="1",
        confirmPhase="confirm",
        cardAction="confirm",
        cardDigest=draft["cardDigest"],
    )
    pointer = load_pointer(seq)
    advanced_without_card = pointer["current"] != "1" and not saved.get("cardDigest")
    assert advanced_without_card is False
    assert saved["ok"] is True, saved
    assert saved["stored"] is True
    assert saved["current"] == "2"
    assert saved["card"]["stage"] == "2"
    assert saved["card"]["essay_id"] == seq
    assert saved["cardDigest"] == saved["card"]["digest"]
    assert pointer["revision"] == before["revision"] + 1
    assert pointer["waiting_stage"] == "2"
    assert pointer["waiting_digest"] == saved["cardDigest"]
    assert "1" in pointer["saved"]

    student = _live(
        essay_id=seq,
        stage="2",
        confirmPhase="draft",
        look=look + "\nEntry 1 is the decision.",
    )
    assert student["ok"] is False, student
    assert student["refused"] == "named-parts"
    still = load_pointer(seq)
    assert still["current"] == "2"
    assert still["waiting_stage"] == "2"
    assert still["waiting_digest"] == saved["cardDigest"]


def test_ac3_stage5_and_last_stage_advance_without_card(workspace):
    """AC3. Stage 5 and the last stage name an advance that has no card."""
    stage5 = open_sequence("MOD1004AA")
    _plant(stage5, "5", ["1", "2", "3", "4a", "4b"])
    done = _live(essay_id=stage5, stage="5", confirmPhase="draft", look=LOOK)
    assert done["ok"] is True, done
    assert done["stored"] is True
    assert done["advanced"] is True
    assert done["current"] == "6"
    assert done["explicit_end"] is True
    assert done.get("card") is None
    assert done.get("cardDigest") is None
    assert done.get("next_card_ok") is not False
    pointer = load_pointer(stage5)
    assert pointer["current"] == "6"
    assert "5" in pointer["saved"]
    assert pointer["waiting_stage"] is None
    assert pointer["waiting_digest"] is None

    last = open_sequence("RPT1008AA")
    _plant(last, "10", ["1", "2", "3", "4a", "4b", "5", "6", "7", "8", "9"])
    opened = _live(essay_id=last, stage="10", confirmPhase="draft", look=LAST)
    assert opened["ok"] is True, opened
    plant_renderable_pack(last)
    before = load_pointer(last)
    closed = _live(
        essay_id=last,
        stage="10",
        confirmPhase="confirm",
        cardAction="confirm",
        cardDigest=opened["cardDigest"],
    )
    assert closed["ok"] is True, closed
    assert closed["stored"] is True
    assert closed["closed"] is True
    assert closed["current"] == "10"
    assert closed["explicit_end"] is True
    assert closed.get("card") is None
    assert closed.get("cardDigest") is None
    finished = load_pointer(last)
    assert finished["revision"] == before["revision"] + 1
    assert finished["closed"] is True
    assert "10" in finished["saved"]
    assert finished["waiting_stage"] is None
    assert finished["waiting_digest"] is None


def test_ac4_cursor_and_grok_build_share_confirm(monkeypatch):
    """AC4. Build covered. Cursor and Grok Build share the atomic Confirm path."""
    assert cursor_shell()["handlers"]["essay.stage"] is front_office()["handlers"]["essay.stage"]
    assert HANDLERS["essay.stage"] is essay_stage
    assert mount_handler("essay.stage").__wrapped__ is essay_stage
    source = inspect.getsource(_save_confirm)
    assert "return _commit_with_next_card(" in source
    assert "_MINTING.set(True)" in inspect.getsource(_draft_next_card)
    assert "_commit_with_next_card" not in inspect.getsource(stage_launch)
    assert "_commit_with_next_card" not in inspect.getsource(cursor_stage_launch)
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_CURSOR)
    cursor = stage_host_launch("1")
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_GROK_BUILD)
    grok = stage_host_launch("1")
    assert cursor["settings"]["rules"] == grok["settings"]["rules"]
    assert cursor_shell()["entry"]["command"] == front_office()["entry"]["command"] == "essay-writer"


def test_ac5_closed_or_wrong_sequence_does_not_mint_a_card(workspace):
    """AC5. A closed pack and a foreign digest do not mint a postable card."""
    closed = open_sequence("RPT5001AA")
    closed_digest = _close(closed)
    opened_id = open_sequence("RPT5001AA")
    draft = _live(essay_id=opened_id, stage="1", confirmPhase="draft", look=LOOK)
    assert draft["ok"] is True, draft
    assert draft["card"]["essay_id"] == opened_id

    for stage in ("10", "9", "1"):
        for digest in (closed_digest, draft["cardDigest"]):
            body = _live(
                essay_id=closed,
                stage=stage,
                confirmPhase="confirm",
                cardAction="confirm",
                cardDigest=digest,
            )
            assert body.get("stored") is not True
            assert body.get("card") is None
            assert body.get("cardAction") is None
            assert body.get("cardDigest") is None
    assert load_pointer(closed)["closed"] is True
    assert load_pointer(closed)["current"] == "10"

    foreign = _live(
        essay_id=opened_id,
        stage="1",
        confirmPhase="confirm",
        cardAction="confirm",
        cardDigest=closed_digest,
    )
    assert foreign.get("stored") is not True
    assert load_pointer(opened_id)["current"] == "1"
    assert "1" not in load_pointer(opened_id)["saved"]
    card = foreign.get("card") or {}
    assert card.get("essay_id") != closed
    assert foreign.get("cardDigest") != closed_digest
    assert load_pointer(closed)["closed"] is True
