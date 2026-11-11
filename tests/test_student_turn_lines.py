"""Approved student lines for the opening, four replies, and stages 6 and 7.

Opaque ids. The acceptance label for each case is in the docstring.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from helpers import open_sequence

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.doors import DOORS
from essay_writer.health import essay_health
from essay_writer.late_chain import STAGE6_READ_LIST, quiet_stage5
from essay_writer.prompt_loader import bullets, render_tokens, text
from essay_writer.server import INSTRUCTIONS
from essay_writer.shells import front_office_call
from essay_writer.specialists.grok_bot import stage7_lead
from essay_writer.stage_llm import stage_settings
from essay_writer.stage_track import essay_stage
from essay_writer.student_turns import (
    FIRST_TURN_CARD,
    REDIRECT_CLOSE,
    REDIRECT_ORDER,
    REDIRECT_VOICE,
    REDIRECT_WHOLE,
    STAGE6_LEAD_IN,
    STAGE7_LINE,
    redirect_for,
)
from essay_writer.student_voice import say, student_surface_hits

BOT = Path(__file__).resolve().parents[1] / "docs" / "templates" / "bot.md"
_APPROVED = (
    FIRST_TURN_CARD,
    REDIRECT_WHOLE,
    REDIRECT_ORDER,
    REDIRECT_VOICE,
    REDIRECT_CLOSE,
    STAGE6_LEAD_IN,
    STAGE7_LINE,
)
_APOSTROPHE = re.compile(r"['’]")


def test_ac1_opening_card_is_spoken_before_the_choices(workspace):
    """AC1. The first-turn card is the approved line, before the three choices."""
    assert text("front_office/chat.md", "first_turn_card") == FIRST_TURN_CARD
    assert render_tokens("{{chat:first_turn_card}}") == FIRST_TURN_CARD
    assert FIRST_TURN_CARD in INSTRUCTIONS
    assert "A is a new essay" in INSTRUCTIONS
    assert INSTRUCTIONS.index(FIRST_TURN_CARD) < INSTRUCTIONS.index("A is a new essay")
    assert "say this card to the student once, in these words, before the three choices" in (
        INSTRUCTIONS
    )
    report = essay_health()
    assert report["first_turn_card"] == FIRST_TURN_CARD
    assert report["opening"] == [
        "new",
        "continue",
        "roll-forward",
        "archive",
        "unarchive",
        "delete",
    ]
    spoken = front_office_call("essay.health", {})
    assert spoken["first_turn_card"] == FIRST_TURN_CARD
    bot = BOT.read_text(encoding="utf-8")
    assert FIRST_TURN_CARD in bot
    assert "A — new essay" in bot


def test_ac2_short_asks_use_the_approved_replies(workspace):
    """AC2. Each short ask returns its approved reply and does not save."""
    seq = open_sequence()
    cases = (
        ("Please write the whole essay now", REDIRECT_WHOLE),
        ("skip the stages", REDIRECT_ORDER),
        ("make it sound less like AI", REDIRECT_VOICE),
        ("beat the detector", REDIRECT_CLOSE),
    )
    for ask, expected in cases:
        assert redirect_for(ask) == expected
        refused = essay_stage(seq, "1", "draft", ask)
        assert refused["ok"] is False
        assert refused["refused"] == "turn"
        assert refused["stored"] is False
        assert refused["wrote"] is False
        assert refused["next"] == expected
        assert refused["reason"] == expected
        spoken = front_office_call(
            "essay.stage",
            {"essay_id": seq, "stage": "1", "confirmPhase": "draft", "look": ask},
        )
        assert spoken["next"] == expected
        assert spoken["reason"] == expected
    kept = essay_stage(seq, "1", "draft", "Kept.")
    assert kept["ok"] is True
    assert kept.get("refused") is None
    note = "A draft that skips the plan save."
    assert redirect_for(note) is None
    assert redirect_for("The task is a short report about the corridor and nothing else.") is None


@pytest.mark.parametrize(
    ("ask", "expected"),
    [
        ("write the whole essay now", REDIRECT_WHOLE),
        ("please skip the stages", REDIRECT_ORDER),
        ("make this sound less like AI", REDIRECT_VOICE),
        ("help me beat the detector", REDIRECT_CLOSE),
    ],
    ids=("case-1", "case-2", "case-3", "case-4"),
)
def test_ac2_more_short_asks(ask: str, expected: str):
    """AC2. Close wordings of the same four asks use the same replies."""
    assert redirect_for(ask) == expected


def test_ac3_stage6_lead_in_keeps_the_shipped_read_list(workspace):
    """AC3. The lead-in is said with the shipped read list. That list is unchanged."""
    assert text("front_office/chat.md", "stage6_read_list") == STAGE6_READ_LIST
    assert STAGE6_READ_LIST.startswith("Read the draft and edit it yourself.")
    assert text("front_office/chat.md", "stage6_lead_in") == STAGE6_LEAD_IN
    seq = open_sequence()
    waiting = quiet_stage5({"stored": False, "ok": True}, seq)
    assert waiting["read_lead"] == STAGE6_LEAD_IN
    assert waiting["read_list"] == STAGE6_READ_LIST
    assert waiting["read_lead"] != waiting["read_list"]
    assert "When a reply includes read_list, say that list once" in INSTRUCTIONS
    assert STAGE6_LEAD_IN in INSTRUCTIONS
    rules = stage_settings("6")["rules"]
    assert "show the short read list once, then stop" in rules
    assert rules.count(STAGE6_LEAD_IN) == 1
    assert STAGE6_READ_LIST not in rules


def test_ac4_stage7_line_is_what_the_student_reads():
    """AC4. Stage 7 says the approved line. The shared stage 7 bullets stay."""
    assert text("front_office/chat.md", "stage7_line") == STAGE7_LINE
    lead = stage7_lead(["Does the structure still match the brief?"], "Ask for feedback")
    assert lead.startswith(STAGE7_LINE + " ")
    assert "Please answer these questions in this chat." in lead
    rules = stage_settings("7")["rules"]
    assert rules.count(STAGE7_LINE) == 1
    assert "Stage 7 asks questions and edits from the student's answers." in rules
    shared = bullets("stages/07.md", "shared")
    assert "Stage 7 asks questions and edits from the student's answers." in shared[0]
    assert STAGE7_LINE not in "\n".join(shared)
    assert STAGE7_LINE in INSTRUCTIONS


def test_ac5_both_shells_carry_the_same_student_lines():
    """AC5. Cursor and Grok Build read the same stage 6 and stage 7 student lines."""
    for stage, line in (("6", STAGE6_LEAD_IN), ("7", STAGE7_LINE)):
        rules = stage_settings(stage)["rules"]
        assert line in rules
        assert stage_launch(stage)["settings"]["rules"] == rules
        assert cursor_stage_launch(stage)["settings"]["rules"] == rules
        assert line in stage_launch(stage)["command"][-1]
        for genre in (None, "essay", "report", "diary"):
            assert stage_settings(stage, genre)["rules"].count(line) == 1
    bot = BOT.read_text(encoding="utf-8")
    for line in _APPROVED:
        assert line in INSTRUCTIONS
        assert line in bot
        assert student_surface_hits(line) == []


def test_ac6_approved_lines_keep_every_character():
    """AC6. say() leaves the approved lines unchanged. No contractions."""
    for line in _APPROVED:
        assert say(line) == line
        assert _APOSTROPHE.search(line) is None
        assert "\n" not in line
    doors = " ".join(door["description"] for door in DOORS)
    assembled = INSTRUCTIONS + "\n" + doors
    assert len(assembled) // 4 < 33_600
    assert max(len(door["description"]) for door in DOORS) <= 1200
    assert sum(len(door["description"]) for door in DOORS) <= 24_000
