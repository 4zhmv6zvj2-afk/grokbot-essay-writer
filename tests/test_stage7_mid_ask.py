"""The stage 7 questions ask survives a started mid step.

A stage 7 draft that has not been edited is the ask: read the draft, answer
these questions, or say all fine. A mid step that starts in the same turn used
to replace that whole ask with "Wait while this step finishes in this chat.",
so the student never saw the all-fine line. The ask now comes first in both
replies: the door body and the shaped front-office speech. The wait line still
appears while a step is actually running, on the stages and the turns where it
belongs.

The wait is exercised here with a started step, the way a host with the Cursor
CLI or Grok Build present starts one.

Each hyphen id is seated once, in the docstring of the test that proves it.
"""

from __future__ import annotations

import inspect
import os

import pytest
import test_confirm_card_save as card_save
from docx import Document
from helpers import OTHER, open_sequence, picked, plant_gathered_source

from essay_writer.setup import SHELL_CURSOR, SHELL_GROK_BUILD
from essay_writer.shells import front_office_call
from essay_writer.stage7 import _QUESTIONS
from essay_writer.stage_state import load_pointer
from essay_writer.stage_track import essay_stage
from essay_writer.student_progress import mid_run_wait_next, shape_student_reply
from essay_writer.writing_basics import STAGE_ORDER

ALL_FINE = "If the draft is fine as it is, say all fine."
WAIT_LINE = "Wait while this step finishes in this chat."
LOOK = "Kept."
DRAFT_SENTENCE = "The firm cut emissions in 2024."


def _started(command):
    """A step that really started: a live pid and a command, no stdout stream."""
    return {
        "started": True,
        "reason": "",
        "pid": os.getpid(),
        "command": [str(part) for part in command],
    }


def _through(seq: str, stop: str) -> None:
    for stage in STAGE_ORDER:
        if stage == stop:
            return
        draft = essay_stage(seq, stage, "draft", f"{LOOK} This sentence belongs to stage {stage}.")
        assert draft["ok"] is True, draft
        if stage == "4a":
            plant_gathered_source(seq)
        if stage == "5":
            assert draft["stored"] is True, draft
            continue
        saved = essay_stage(seq, stage, "confirm", LOOK, **picked(draft))
        assert saved["stored"] is True, saved


def _write_docx(seq: str) -> None:
    from essay_writer.paths import work_dir

    path = work_dir(seq) / "output" / f"{seq}.docx"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.add_paragraph(DRAFT_SENTENCE)
    document.save(str(path))


def _ask_stage7(seq: str) -> dict:
    from essay_writer.build_status import reset_status

    _through(seq, "7")
    _write_docx(seq)
    # Stage 6 starts a step of its own. Clear it so the stage 7 turn is the one
    # that starts a step, which is the turn this seat is about.
    reset_status()
    asked = essay_stage(seq, "7", "draft", LOOK)
    assert asked["ok"] is True, asked
    assert asked["questions"]
    return asked


@pytest.mark.parametrize("case_id", [pytest.param("essay-confirm-d1", id="essay-confirm-d1")])
def test_the_stage7_ask_is_the_next_when_a_step_starts(case_id, workspace, monkeypatch):
    """essay-confirm-d1: The finished stage 7 ask names all fine, not only the wait."""
    assert case_id == "essay-confirm-d1"
    monkeypatch.setattr("essay_writer.cursor_office.spawn_agent", _started)
    monkeypatch.setattr("essay_writer.build_office.spawn_grok", _started)

    seq = open_sequence()
    asked = _ask_stage7(seq)
    # The step really started, so the wait path was live for this turn.
    assert asked.get("mid_started") is True
    assert mid_run_wait_next("7") == WAIT_LINE

    assert ALL_FINE in asked["next"]
    assert asked["next"] != WAIT_LINE
    assert asked["next"].strip() != WAIT_LINE
    assert "Please answer these questions" in asked["next"]
    for question in _QUESTIONS:
        assert question in asked["next"]
    assert load_pointer(seq)["current"] == "7"
    assert "7" not in load_pointer(seq)["saved"]

    spoken = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "7",
            "confirmPhase": "draft",
            "look": "All fine for now, please ask again.",
            "answers": "all fine / none",
        },
    )
    assert spoken["ok"] is True, spoken
    assert spoken["stored"] is False
    # After the answers the card ask stands, and the wait line does not hide it.
    assert spoken["next"] != WAIT_LINE
    assert "Open the Confirm card to save Stage 7" in spoken["next"]

    # The shaping path alone, with the door's own ask and a started step.
    shaped = shape_student_reply(
        {
            "ok": True,
            "essay_id": seq,
            "stage": "7",
            "next": asked["next"],
            "card": {"kind": "confirm", "digest": asked["digest"]},
            "cardDigest": asked["digest"],
        },
        tool="essay.stage",
        mid_started=True,
        status_lines=["I have started work on your assignment."],
    )
    assert shaped["next"] != WAIT_LINE
    assert ALL_FINE in shaped["next"]
    assert "Please answer these questions" in shaped["next"]

    # With no card on the reply the ask is not spoken, so no Confirm line is
    # invented. The wait line takes the turn instead.
    cardless = shape_student_reply(
        {
            "ok": True,
            "essay_id": seq,
            "stage": "7",
            "next": asked["next"],
        },
        tool="essay.stage",
        mid_started=True,
        status_lines=[],
    )
    assert ALL_FINE not in cardless.get("next", "")
    assert "Confirm" not in cardless.get("next", "")

    # The wait line keeps its place while a step runs on a stage that has no ask.
    for stage in ("6", "8", "9", "10"):
        waiting = shape_student_reply(
            {
                "ok": True,
                "essay_id": seq,
                "stage": stage,
                "next": "Open the Confirm card to save this stage.",
                "card": {"kind": "confirm", "digest": asked["digest"]},
                "cardDigest": asked["digest"],
            },
            tool="essay.stage",
            mid_started=True,
            status_lines=[],
        )
        assert waiting["next"] == mid_run_wait_next(stage), stage


@pytest.mark.parametrize("case_id", [pytest.param("essay-confirm-d2", id="essay-confirm-d2")])
def test_the_neighbouring_confirm_checks_hold(case_id, workspace, monkeypatch):
    """essay-confirm-d2: Skip is refused, all fine opens Confirm, the neighbours hold."""
    assert case_id == "essay-confirm-d2"
    monkeypatch.setattr("essay_writer.cursor_office.spawn_agent", _started)
    monkeypatch.setattr("essay_writer.build_office.spawn_grok", _started)

    seq = open_sequence()
    asked = _ask_stage7(seq)
    skipped = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "7",
            "confirmPhase": "confirm",
            "look": "skip",
            "cardAction": asked["cardAction"],
            "cardDigest": asked["cardDigest"],
        },
    )
    assert skipped["ok"] is False, skipped
    assert skipped["refused"] == "stage"
    assert skipped["stored"] is not True
    assert "Skipping the questions does not save" in skipped["reason"]
    assert "Please answer these questions" in skipped["next"]
    for question in _QUESTIONS:
        assert question in skipped["next"]
    note = (card_save.work_dir(seq) / "tracking" / "7.md").read_text(encoding="utf-8")
    assert "Status: draft" in note
    assert "Status: final" not in note
    assert load_pointer(seq)["current"] == "7"
    assert "7" not in load_pointer(seq)["saved"]

    opened = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "7",
            "confirmPhase": "confirm",
            "look": "all fine / no changes",
        },
    )
    assert opened["ok"] is True, opened
    assert opened["stored"] is False
    assert opened["cardAction"] == "confirm"
    assert opened["cardDigest"] == opened["digest"]
    assert len(opened["cardDigest"]) == 64
    assert opened["next"].startswith("Open the Confirm card to save Stage 7")
    assert "7" not in load_pointer(seq)["saved"]

    saved = essay_stage(seq, "7", "confirm", **picked(opened))
    assert saved["ok"] is True, saved
    assert saved["stored"] is True
    assert saved["current"] == "8"
    assert "7" in load_pointer(seq)["saved"]
    final_note = (card_save.work_dir(seq) / "tracking" / "7.md").read_text(encoding="utf-8")
    assert "Status: final" in final_note

    # A stage 2 Confirm leaves the pointer on stage 3. A fresh module has no
    # earlier sequence to inherit a lock from.
    other = open_sequence(OTHER)
    first = essay_stage(other, "1", "draft", f"{LOOK} This sentence belongs to stage 1.")
    one = essay_stage(other, "1", "confirm", LOOK, **picked(first))
    assert one["stored"] is True
    second = essay_stage(other, "2", "draft", f"{LOOK} This sentence belongs to stage 2.")
    assert second["stored"] is False
    two = essay_stage(other, "2", "confirm", LOOK, **picked(second))
    assert two["stored"] is True
    assert two["current"] == "3"
    assert load_pointer(other)["saved"] == ["1", "2"]
    assert "3" not in load_pointer(other)["saved"]

    # Press Confirm with the waiting card saves that stage in one call.
    third = essay_stage(other, "3", "draft", f"{LOOK} This sentence belongs to stage 3.")
    pressed = front_office_call(
        "essay.stage",
        {
            "essay_id": other,
            "stage": "3",
            "confirmPhase": "confirm",
            "look": "Press Confirm for Stage 3",
            "cardAction": third["cardAction"],
            "cardDigest": third["cardDigest"],
        },
    )
    assert pressed["ok"] is True, pressed
    assert pressed["stored"] is True
    assert pressed["current"] == "4a"
    assert load_pointer(other)["saved"] == ["1", "2", "3"]

    # Cursor CLI and Grok Build share the mid-build status for a stage.
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_CURSOR)
    cursor_status = card_save.stage_host_launch("4b")["status"]
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_GROK_BUILD)
    build_status = card_save.stage_host_launch("4b")["status"]
    assert cursor_status == build_status

    # The confirm-card checks this fix sits beside still carry their assertions.
    # The all-fine line and the questions ask sit in AC4's own ask helper, so
    # both the helper and the test body are checked.
    for name, marks in (
        (
            "test_ac1_stage2_confirm_does_not_save_stage3",
            ('assert pointer["current"] == following', 'assert following not in pointer["saved"]'),
        ),
        (
            "test_ac2_press_with_card_saves_in_one_call",
            (
                'assert finished["stored"] is True',
                'assert load_pointer(chain)["saved"][-1] == "4b"',
            ),
        ),
        (
            "test_ac3_mid_build_status_is_wired_for_both_shells",
            ('assert MID_BUILD_STATUS_ID == "mid-build-status"', "assert cursor_tip == build_tip"),
        ),
        (
            "test_ac4_stage7_skip_refuses_and_all_fine_opens_confirm",
            (
                'assert skipped["refused"] == "stage"',
                'assert "Skipping the questions does not save" in skipped["reason"]',
                'assert "Please answer these questions" in skipped["next"]',
                'assert opened["next"].startswith("Open the Confirm card to save Stage 7")',
                'assert "Status: draft" in _stage_note(seq, "7")',
                'assert saved["stored"] is True',
            ),
        ),
    ):
        body = inspect.getsource(getattr(card_save, name))
        for mark in marks:
            assert mark in body, (name, mark)
    ask_helper = inspect.getsource(card_save._ask_stage7)
    assert 'assert "If the draft is fine as it is, say all fine." in asked["next"]' in ask_helper
    assert 'assert "Please answer these questions" in asked["next"]' in ask_helper
    assert 'assert "all fine saves" not in asked["next"].casefold()' in ask_helper
