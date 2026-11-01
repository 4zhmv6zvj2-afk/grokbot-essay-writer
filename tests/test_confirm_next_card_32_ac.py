"""Bugs #32 and #33. The live Confirm returns the next card for the open sequence.

AC1: a successful Confirm, except stage 5, returns the next draft card.
The next waiting digest is stored in that same pointer write.
AC2: a closed pack or the wrong sequence does not mint a postable card.
AC3: the briefing posts only the door card for the current open sequence.
AC4: Build covered. Cursor and Grok Build share that Confirm path.
"""

import inspect
import json
from pathlib import Path

from helpers import open_sequence

from essay_writer.assignment_gate import read_assignment
from essay_writer.build_office import stage_launch
from essay_writer.confirm import save_draft
from essay_writer.cursor_office import cursor_stage_launch, stage_host_launch
from essay_writer.paths import essay_dir, work_dir
from essay_writer.server import HANDLERS, INSTRUCTIONS
from essay_writer.setup import SHELL_CURSOR, SHELL_GROK_BUILD
from essay_writer.shells import cursor_shell, front_office, mount_handler
from essay_writer.specialists.grok_bot import STAGE_CONFIRM_EACH, basics_pass_lines
from essay_writer.stage_track import TOOL, essay_stage, load_pointer
from essay_writer.writing_basics import STAGE_ORDER

REPO = Path(__file__).resolve().parents[1]
BOT = REPO / "docs" / "templates" / "bot.md"
WORKFLOW = REPO / "docs" / "workflow.md"
OPEN_CARD = (
    "Post a Confirm only when its cardDigest matches the door's latest result "
    "for the current open sequence. "
    "Refuse a closed pack, a wrong sequence, and inventing the next stage."
)
DIARY = """
Assignment title: Individual reflective diary

Module title: Practice module
Module code: RPT5001AA

Aim: Understand the practice by reflecting on your own decisions.

Assignment task: Write four entries. Each entry names one decision and critically analyses it with theory and evidence.

The main body of the report is the diary. First person is allowed.

One entry for each occasion: North occasion, South occasion, East occasion, and West occasion.

# Marking criteria/feedback form

| Criterion | 0-39 | 40-49 | 50-59 | 60-69 | 70+ |
| --- | --- | --- | --- | --- | --- |
| Clarity of the decisions | thin | partial | sound | clear | exact and evidenced |
"""
REPORT = "Genre: report\nQuestion: How should the firm manage the corridor?\n"
SCHEME = "High Distinction (80-100): the question is answered with evidence\n"


def _brief(module: str, text: str, scheme: str | None = None) -> None:
    folder = essay_dir(module)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(text, encoding="utf-8")
    if scheme:
        (folder / "mark-scheme.md").write_text(scheme, encoding="utf-8")


def _live(**kwargs):
    """The function the stdio server mounts for essay.stage."""
    return mount_handler("essay.stage")(**kwargs)


def _card(body: dict, stage: str, essay_id: str) -> None:
    card = body["card"]
    assert card["kind"] == "confirm"
    assert card["stage"] == stage
    assert card["essay_id"] == essay_id
    assert body["cardAction"] == "confirm"
    assert body["cardDigest"] == card["digest"]
    assert len(body["cardDigest"]) == 64
    assert body.get("digest") != body["cardDigest"]


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
        {"essay_id": seq, "stage": "10", "look": "The final look stays on this pack."},
        {"stage": "10"},
    )


def test_ac1_confirm_returns_the_next_draft_card(workspace):
    """AC1. Live Confirm returns the next card and stores its digest with the advance."""
    _brief("RPT5001AA", DIARY)
    seq = open_sequence("RPT5001AA")
    record = read_assignment(seq)
    assert record["active"] is True
    assert record["named_entries"] == [
        "North occasion",
        "South occasion",
        "East occasion",
        "West occasion",
    ]
    look = "\n".join(basics_pass_lines(seq))
    draft = _live(essay_id=seq, stage="1", confirmPhase="draft", look=look)
    assert draft["ok"] is True, draft
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
    assert load_pointer(seq)["waiting_stage"] == "2"
    assert load_pointer(seq)["waiting_digest"] == saved["cardDigest"]
    _card(saved, "2", seq)

    for stage, nxt in (("2", "3"), ("3", "4a")):
        pressed = _live(
            essay_id=seq,
            stage=stage,
            confirmPhase="confirm",
            cardAction=saved["cardAction"],
            cardDigest=saved["cardDigest"],
        )
        assert pressed["stored"] is True, pressed
        assert pressed["current"] == nxt
        assert stage in load_pointer(seq)["saved"]
        assert load_pointer(seq)["waiting_stage"] == nxt
        assert load_pointer(seq)["waiting_digest"] == pressed["cardDigest"]
        _card(pressed, nxt, seq)
        saved = pressed

    _brief("MOD1004AA", REPORT, SCHEME)
    report = open_sequence("MOD1004AA")
    report_look = "\n".join(basics_pass_lines(report))
    opened = _live(essay_id=report, stage="1", confirmPhase="draft", look=report_look)
    hopped = _live(
        essay_id=report,
        stage="1",
        confirmPhase="confirm",
        cardAction="confirm",
        cardDigest=opened["cardDigest"],
    )
    assert hopped["stored"] is True, hopped
    _card(hopped, "2", report)


def test_ac2_closed_or_wrong_sequence_does_not_mint_a_card(workspace):
    """AC2. A closed pack and a foreign digest do not mint a card for that pack."""
    closed = open_sequence("RPT5001AA")
    closed_digest = _close(closed)
    opened = open_sequence("RPT5001AA")
    draft = essay_stage(opened, "1", "draft", "The open sequence starts at stage 1.")
    assert draft["ok"] is True, draft
    assert draft["card"]["essay_id"] == opened

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
        essay_id=opened,
        stage="1",
        confirmPhase="confirm",
        cardAction="confirm",
        cardDigest=closed_digest,
    )
    assert foreign.get("stored") is not True
    assert load_pointer(opened)["current"] == "1"
    assert "1" not in load_pointer(opened)["saved"]
    card = foreign.get("card") or {}
    assert card.get("essay_id") != closed
    assert foreign.get("cardDigest") != closed_digest
    assert load_pointer(closed)["closed"] is True


def test_ac3_briefing_posts_only_the_open_sequence_card():
    """AC3. INSTRUCTIONS, bot.md, and workflow post only the open sequence's door card."""
    bot = BOT.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert OPEN_CARD in STAGE_CONFIRM_EACH
    for text in (INSTRUCTIONS, bot, workflow):
        assert "Essay Bot may only show the Confirm card the door returned" in text
        assert "does not pick the next stage itself" in text
        assert OPEN_CARD in text
        assert "current open sequence" in text
        assert "closed pack" in text
        assert "wrong sequence" in text
        assert "inventing the next stage" in text


def test_ac4_build_covered_shares_the_confirm_next_card_path(monkeypatch):
    """Build covered. Cursor and Grok Build share essay.stage and the atomic confirm write."""
    assert cursor_shell()["handlers"]["essay.stage"] is front_office()["handlers"]["essay.stage"]
    assert HANDLERS["essay.stage"] is essay_stage
    assert mount_handler("essay.stage").__wrapped__ is essay_stage
    assert "return _commit_with_next_card(" in inspect.getsource(essay_stage)
    assert "_commit_with_next_card" not in inspect.getsource(stage_launch)
    assert "_commit_with_next_card" not in inspect.getsource(cursor_stage_launch)
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_CURSOR)
    cursor = stage_host_launch("1")
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_GROK_BUILD)
    grok = stage_host_launch("1")
    assert cursor["settings"]["rules"] == grok["settings"]["rules"]
    assert cursor_shell()["entry"]["command"] == front_office()["entry"]["command"] == "essay-writer"
