"""Download and citation locks. Stable ids: AC1, AC2, AC3.

Confirm card behaviour is the shipped door (PR #58, hydration PR #63).
The short Basics pass is Batch 0 (PR #64). This file locks the rest of that
"""

from helpers import ESSAY, open_sequence, picked, plant_gathered_source

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.paths import essay_dir, work_dir
from essay_writer.server import HANDLERS
from essay_writer.shells import cursor_shell, front_office, front_office_call
from essay_writer.specialists.grok_bot import BASICS_FIRST_LINES
from essay_writer.stage_llm import stage_settings
from essay_writer.stage_track import essay_stage, load_pointer
from essay_writer.writing_basics import STAGE_ORDER, basics_lines

QUESTION = "How should the firm manage the corridor?"
SCHEME = "High Distinction (80-100): the question is answered with evidence\n"


def _brief() -> None:
    folder = essay_dir(ESSAY)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(
        f"Genre: report\nQuestion: {QUESTION}\n",
        encoding="utf-8",
    )
    (folder / "mark-scheme.md").write_text(SCHEME, encoding="utf-8")


def _look(seq: str) -> str:
    from essay_writer.specialists.grok_bot import basics_pass_lines

    return "\n".join(basics_pass_lines(seq))


def _student_speech(reply: dict) -> str:
    parts: list[str] = []
    for key in ("next", "chat", "confirm_line"):
        value = reply.get(key)
        if isinstance(value, str):
            parts.append(value)
    card = reply.get("card")
    if isinstance(card, dict) and isinstance(card.get("text"), str):
        parts.append(card["text"])
    status = reply.get("status")
    if isinstance(status, list):
        parts.extend(line for line in status if isinstance(line, str))
    return "\n".join(parts)


def _tracking(seq: str, stage: str) -> str:
    return (work_dir(seq) / "tracking" / f"{stage}.md").read_text(encoding="utf-8")


def test_ac1_confirm_is_a_clickable_card_and_typed_yes_does_not_save(workspace):
    """E2E #10. A typed yes or ok does not save. The card pick does."""
    _brief()
    seq = open_sequence()
    look = _look(seq)
    draft = essay_stage(seq, "1", "draft", look)
    card = draft["card"]
    assert card["deliver"] == "chat"
    assert card["kind"] == "confirm"
    assert card["essay_id"] == seq
    assert card["stage"] == "1"
    assert card["digest"] == draft["digest"]
    assert card["actions"] == [
        {"id": "confirm", "label": "Confirm"},
        {"id": "not_yet", "label": "Not yet"},
    ]
    assert draft["stored"] is False
    assert load_pointer(seq)["saved"] == []

    for typed in ("yes", "ok", "Yes", "OK"):
        refused = essay_stage(seq, "1", "confirm", typed)
        assert refused["ok"] is False
        assert refused["refused"] == "confirm-card"
        assert refused["stored"] is not True
        assert load_pointer(seq)["saved"] == []
        refused = essay_stage(
            seq, "1", "confirm", look, cardAction=typed, cardDigest=draft["digest"],
        )
        assert refused["refused"] == "confirm-card"
        assert load_pointer(seq)["saved"] == []

    mismatch = essay_stage(
        seq, "1", "confirm", cardAction="confirm", cardDigest="not-the-card",
    )
    assert mismatch["refused"] == "confirm-card"
    assert load_pointer(seq)["saved"] == []

    held = essay_stage(
        seq, "1", "confirm", cardAction="not_yet", cardDigest=draft["digest"],
    )
    assert held["refused"] == "confirm-card"
    assert load_pointer(seq)["saved"] == []

    saved = essay_stage(seq, "1", "confirm", cardAction="confirm", cardDigest=draft["digest"])
    assert saved["stored"] is True, saved
    assert saved["current"] == "2"
    assert saved["card"]["stage"] == "2"
    assert load_pointer(seq)["saved"] == ["1"]


def test_ac2_rest_of_basics_walk_before_confirm(workspace):
    """Rest of E2E #8. First lines stay the chat opening. The rest is internal."""
    _brief()
    seq = open_sequence()
    look = _look(seq)
    lines = look.splitlines()
    assert lines[0].startswith("The mark scheme scores ")
    assert lines[1] == "Format: report."
    assert lines[2] == f"Question: {QUESTION}"

    for stage in ("1", "2", "3", "4a", "4b"):
        overlay = stage_settings(stage, "report")["prompt_overlay"]
        assert overlay.startswith(BASICS_FIRST_LINES)
        walk_at = overlay.index("Walk this Basics checklist internally before the save.")
        head = overlay[:walk_at]
        assert "mark scheme scores" in head
        assert "format the brief names" in head
        assert "assignment question" in head
        rest = basics_lines(stage, "report")
        assert rest
        for bullet in rest:
            assert overlay.index(bullet) > walk_at

    for stage in STAGE_ORDER:
        if stage == "5":
            break
        draft = essay_stage(seq, stage, "draft", look)
        assert draft["ok"] is True, draft
        assert draft["basics_pass"] == lines
        assert draft["stored"] is False
        speech = _student_speech(draft)
        note = _tracking(seq, stage)
        rules, _heading, body = note.partition("## Working look")
        assert _heading == "## Working look"
        assert body.strip().startswith(look)
        assert "Walk this Basics checklist internally before the save." in rules
        for bullet in basics_lines(stage, "report"):
            assert bullet in rules
            assert bullet not in speech
            assert bullet not in "\n".join(draft["basics_pass"])
        assert "Walk this Basics checklist" not in speech
        typed = essay_stage(seq, stage, "confirm", "yes", cardAction="yes", cardDigest=draft["digest"])
        assert typed["refused"] == "confirm-card"
        assert stage not in load_pointer(seq)["saved"]
        assert "Status: draft" in _tracking(seq, stage)
        if stage == "4a":
            plant_gathered_source(seq)
        saved = essay_stage(seq, stage, "confirm", **picked(draft))
        assert saved["stored"] is True, saved
        final = _tracking(seq, stage)
        _rules, heading, final_body = final.partition("## Final look")
        assert heading == "## Final look"
        assert final_body.strip().startswith(look)
        for bullet in basics_lines(stage, "report"):
            assert bullet in _rules
            assert bullet not in _student_speech(saved)

    quiet = essay_stage(seq, "5", "draft", look)
    assert quiet["stored"] is True, quiet
    assert quiet["quiet"] is True
    assert quiet["checklist_in_chat"] is False
    assert "card" not in quiet
    assert "basics_pass" not in quiet
    spoken = _student_speech(quiet)
    assert "Walk this Basics checklist" not in spoken
    for bullet in basics_lines("5"):
        assert bullet not in spoken
    final = _tracking(seq, "5")
    rules, heading, _body = final.partition("## Final look")
    assert heading == "## Final look"
    assert "Chat for this step stays quiet." in rules
    for bullet in basics_lines("5"):
        assert bullet in rules
    assert load_pointer(seq)["current"] == "6"


def test_ac3_build_covered_shared_confirm_handlers(workspace):
    """Cursor and Grok Build share essay.stage. No second Confirm path."""
    from essay_writer.stage_track import essay_stage as stage_door

    assert HANDLERS["essay.stage"] is stage_door
    assert cursor_shell()["handlers"]["essay.stage"] is HANDLERS["essay.stage"]
    assert front_office()["handlers"]["essay.stage"] is HANDLERS["essay.stage"]

    item = stage_settings("1", "report")
    build = stage_launch("1")
    cursor = cursor_stage_launch("1")
    assert build["source"] == "essay_writer.stage_llm.stage_settings"
    assert cursor["source"] == "essay_writer.stage_llm.stage_settings"
    assert build["settings"]["rules"] == item["rules"]
    assert cursor["settings"]["rules"] == item["rules"]
    assert "Walk this Basics checklist internally before the save." in item["rules"]
    for bullet in basics_lines("1"):
        assert bullet in "\n".join(build["command"])
        assert bullet in cursor["settings"]["rules"]

    _brief()
    seq = open_sequence()
    look = _look(seq)
    arguments = {
        "essay_id": seq,
        "stage": "1",
        "confirmPhase": "draft",
        "look": look,
    }
    spoken = front_office_call("essay.stage", arguments)
    direct = HANDLERS["essay.stage"](seq, "1", "draft", look)
    assert spoken["card"]["kind"] == "confirm"
    assert spoken["card"]["digest"] == direct["digest"]
    assert spoken["card"]["actions"][0]["id"] == "confirm"
    refused = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "1",
            "confirmPhase": "confirm",
            "look": "ok",
            "cardAction": "ok",
            "cardDigest": spoken["digest"],
        },
    )
    assert refused["refused"] == "confirm-card"
    assert load_pointer(seq)["saved"] == []
    saved = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "1",
            "confirmPhase": "confirm",
            "cardAction": "confirm",
            "cardDigest": spoken["digest"],
        },
    )
    assert saved["stored"] is True, saved
    assert "Walk this Basics checklist" not in _student_speech(saved)
    for bullet in basics_lines("1", "report"):
        assert bullet in _tracking(seq, "1")
        assert bullet not in _student_speech(spoken)
        assert bullet not in _student_speech(saved)
