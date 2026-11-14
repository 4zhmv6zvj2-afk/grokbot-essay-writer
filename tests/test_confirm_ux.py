"""The Confirm fallback and student-facing reply copy.

A host that cannot show a tappable card still has a path: a typed yes, ok, or
Confirm saves the waiting card when no card fields are supplied. Student copy
does not carry model directives ("do not...", "never...") and refuses with a
plain next action.
"""

from helpers import open_sequence

from essay_writer.confirm import phase_refusal
from essay_writer.server import INSTRUCTIONS
from essay_writer.specialists.grok_bot import (
    STAGE9_OWN_WORDS,
    missing_confirm_next,
    saved_next,
)
from essay_writer.stage_state import load_pointer
from essay_writer.stage_track import essay_stage
from essay_writer.writing_basics import STAGE_ORDER

LOOK = "The task is a short report."


def _assert_student_copy(value: str) -> None:
    lowered = value.casefold()
    for directive in ("do not", "never", "show the card", "pick the next stage"):
        assert directive not in lowered, (directive, value)
    for jargon in ("basics pass", "stage file", "tracking note"):
        assert jargon not in lowered, (jargon, value)


def test_saved_next_is_student_copy():
    for stage in STAGE_ORDER:
        text = saved_next(stage, "Stage title")
        _assert_student_copy(text)
        assert "Stage" in text
        assert "The Confirm card for that stage is in this reply." not in text
        assert text.startswith("Start Stage") or text.index("Start Stage") > 0
    assert saved_next("10", "Submit the final draft").startswith(STAGE9_OWN_WORDS)


def test_missing_confirm_next_names_the_typed_fallback():
    text = missing_confirm_next("2", "Establish a thesis")
    _assert_student_copy(text)
    assert "Confirm card" in text
    assert "type yes" in text.casefold()


def test_confirm_phase_refusal_is_plain():
    refused = phase_refusal(None)
    assert refused["ok"] is False
    assert "do not" not in refused["reason"].casefold()
    assert "silently" not in refused["reason"].casefold()
    assert "show this step" in refused["reason"].casefold()


def test_server_instructions_offer_the_typed_fallback():
    """essay-u1-d2: a typed yes does not remove a module, and the stage paragraph does not repeat the typed-yes sentence.

    The server-instructions snapshot matches this briefing.
    """
    from pathlib import Path

    briefing = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "essay_writer"
        / "prompts"
        / "front_office"
        / "briefing.md"
    ).read_text(encoding="utf-8")
    delete = next(
        line for line in briefing.splitlines() if line.startswith("Call essay.project.delete")
    )
    stage = next(
        line
        for line in briefing.splitlines()
        if line.startswith("essay.stage and essay.project.delete")
    )
    assert "a typed yes does not remove anything." in delete
    assert "Not yet does not remove anything." in delete
    assert "a typed ok, yes, or confirm saves" not in delete.casefold()
    assert "If the card cannot be used, a typed ok, yes, or confirm saves that waiting step." not in stage
    assert "A typed reply does not save a stage unless it is a yes, ok, or Confirm on a waiting card." not in stage
    assert "Not yet does not save." in stage
    assert "Stage 5 stores on the draft" in stage
    assert "cardAction confirm and cardDigest from that card" in stage
    assert "If the stage is in saved, or current is a later stage, do not show that card." in stage
    import json

    snapshot = json.loads(
        (
            Path(__file__).resolve().parents[1] / "tests" / "snapshots" / "prompts.json"
        ).read_text(encoding="utf-8")
    )
    assert snapshot["instructions"] == INSTRUCTIONS
    assert "a typed yes does not remove anything." in snapshot["instructions"]
    assert "a typed ok, yes, or confirm saves that waiting step" not in INSTRUCTIONS
    assert "A typed ok, yes, or confirm is not a pick" not in INSTRUCTIONS


def test_typed_ok_saves_a_waiting_card(workspace):
    seq = open_sequence()
    draft = essay_stage(seq, "1", "draft", LOOK)
    assert draft["stored"] is False
    spoken = essay_stage(seq, "1", "confirm", "ok")
    assert spoken["ok"] is True, spoken
    assert spoken["stored"] is True
    assert load_pointer(seq)["saved"] == ["1"]
    assert load_pointer(seq)["current"] == "2"


def test_typed_fallback_does_not_override_a_supplied_card_field(workspace):
    seq = open_sequence()
    draft = essay_stage(seq, "1", "draft", LOOK)
    refused = essay_stage(
        seq, "1", "confirm", "yes", cardAction="not_yet", cardDigest=draft["digest"]
    )
    assert refused["ok"] is False
    assert load_pointer(seq)["saved"] == []
