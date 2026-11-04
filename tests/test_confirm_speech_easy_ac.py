"""Easy Confirm speech. Stable ids: AC1–AC5."""

from __future__ import annotations

import re

import pytest
from helpers import ESSAY, open_sequence, picked, plant_gathered_source

from essay_writer.build_status import reset_status, start_sentence
from essay_writer.cursor_office import start_stage_mid
from essay_writer.server import INSTRUCTIONS
from essay_writer.shells import front_office_call
from essay_writer.specialists.grok_bot import STAGE_CONFIRM_EACH, card_next
from essay_writer.stage_track import essay_stage
from essay_writer.student_progress import (
    may_speak_confirm,
    shape_student_reply,
    upload_reconcile_next,
)

_CONFIRM = re.compile(r"\bconfirm\b|confirm card|button above", re.IGNORECASE)
_PHANTOM = re.compile(r"don't click|do not click", re.IGNORECASE)


def _assert_no_confirm_speech(text: str) -> None:
    assert not _CONFIRM.search(text or "")
    assert not _PHANTOM.search(text or "")


@pytest.fixture(autouse=True)
def _clear_status():
    reset_status()
    yield
    reset_status()


def test_ac1_upload_success_names_the_file_without_confirm(workspace, monkeypatch):
    """AC1. After upload-success, spoken next does not point at Confirm."""
    seq = open_sequence()
    check = {"matched": [{"name": "fresh.pdf", "where": "disk"}]}
    line = upload_reconcile_next(check)
    assert line
    assert "fresh.pdf" in line
    _assert_no_confirm_speech(line)

    digest = "a" * 64
    monkeypatch.setattr(
        "essay_writer.research_packs.reconcile_before_4b",
        lambda essay_id, documents=None: check,
    )
    for stage, look in (
        ("1", "The task is a report."),
        ("2", "Purpose and scope are locked."),
        ("3", "The plan holds the central theme."),
    ):
        draft = essay_stage(seq, stage, "draft", look)
        essay_stage(seq, stage, "confirm", look, **picked(draft))
    plant_gathered_source(seq)
    drafted_4a = essay_stage(seq, "4a", "draft", "One source is gathered.")
    essay_stage(seq, "4a", "confirm", "One source is gathered.", **picked(drafted_4a))

    spoken = front_office_call(
        "essay.stage",
        {"essay_id": seq, "stage": "4b", "confirmPhase": "draft", "look": "Continue the read."},
    )
    assert spoken["ok"] is True
    assert "fresh.pdf" in spoken["next"]
    _assert_no_confirm_speech(spoken["next"])
    _assert_no_confirm_speech(" ".join(spoken.get("status") or []))
    shaped = shape_student_reply(
        {"stage": "4b", "download_check": check, "card": {"kind": "confirm", "digest": digest}, "cardDigest": digest},
        tool="essay.stage",
        mid_started=False,
        status_lines=[f"{ESSAY} is ready. Open the Confirm card to save this step."],
    )
    assert shaped["next"] == line
    _assert_no_confirm_speech(" ".join(shaped.get("status") or []))


def test_ac2_mid_run_4b_start_is_notes_not_gathering(workspace, monkeypatch):
    """AC2. While stage 4b work runs, the wait is stage 4b, not 4a gathering."""
    seq = open_sequence()
    monkeypatch.setattr(
        "essay_writer.cursor_office.spawn_agent",
        lambda argv: {"started": True, "reason": "", "pid": 99, "command": list(argv)},
    )
    started = start_stage_mid(seq, "4b")
    assert started["started"] is True
    line = started["status"][0]
    assert "notes" in line.casefold()
    assert "gathering" not in line.casefold()
    assert start_sentence("notes", "your assignment").split(" for ")[0].casefold() in line.casefold()


def test_ac3_mid_run_without_card_does_not_phantom_confirm(workspace, monkeypatch):
    """AC3. Mid-run with no card in the result does not invent don't-click Confirm speech."""
    open_sequence()
    body = {
        "ok": True,
        "stage": "4b",
        "stage_title": "Critical review",
        "mid_started": True,
    }
    briefing = (
        "Do not show the Stage 4b Confirm card yet. "
        "Don't click the Stage 4b Confirm card until the notes are ready."
    )
    shaped = shape_student_reply(
        body,
        tool="essay.stage",
        mid_started=True,
        status_lines=[briefing, "I am still working on your assignment."],
    )
    joined = " ".join(shaped.get("status") or []) + " " + str(shaped.get("next") or "")
    _assert_no_confirm_speech(joined)
    assert "4a" not in joined.casefold()


def test_ac4_ready_draft_still_offers_confirm_card(workspace):
    """AC4. When the artifact is ready, next still offers the Confirm card."""
    seq = open_sequence()
    spoken = front_office_call(
        "essay.stage",
        {"essay_id": seq, "stage": "1", "confirmPhase": "draft", "look": "The task is a short report."},
    )
    assert spoken["card"]["kind"] == "confirm"
    assert spoken["next"].startswith("Open the Confirm card to save Stage 1")
    assert may_speak_confirm(spoken, mid_started=False) is True


def test_ac5_briefing_and_mid_status_build_covered():
    """AC4 docs. Operator rules stay in briefing; mid sheet splits ready vs ready_confirm."""
    bot = (pytest.importorskip("pathlib").Path(__file__).resolve().parents[1] / "docs/templates/bot.md").read_text(
        encoding="utf-8"
    )
    mid = (pytest.importorskip("pathlib").Path(__file__).resolve().parents[1] / "docs/templates/mid-status.md").read_text(
        encoding="utf-8"
    )
    assert STAGE_CONFIRM_EACH.startswith("Operator only.")
    assert "Operator only." in INSTRUCTIONS or "Never read operator-only Confirm rules" in INSTRUCTIONS
    assert "ready_confirm" in mid
    assert "name the file" in bot.casefold() or "pdf upload" in bot.casefold()
    assert card_next("4a", "Annotated bibliography").startswith("Open the Confirm card")
