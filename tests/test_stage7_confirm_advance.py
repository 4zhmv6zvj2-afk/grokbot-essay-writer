"""Stage 7 confirm advances. Stable ids: AC1, AC2, AC3, AC4.

A room agent confirms with cardAction and cardDigest copied from the draft.
Stage 7 answers, including no changes, present that card. Confirm saves
stage 7 and moves to stage 8. A typed yes still does not save.
"""

from pathlib import Path

from docx import Document
from helpers import OTHER, open_sequence, picked, plant_gathered_source

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.doors import DOORS
from essay_writer.paths import work_dir
from essay_writer.server import HANDLERS, INSTRUCTIONS
from essay_writer.setup import SHELL_GROK_BUILD
from essay_writer.shells import cursor_shell, front_office, front_office_call
from essay_writer.specialists.grok_bot import ROOM_CONFIRM_PATH, STAGE7_AFTER_ANSWERS
from essay_writer.stage7 import NEED_EDIT
from essay_writer.stage_llm import stage_settings, stage_tool_description
from essay_writer.stage_track import essay_stage, load_pointer
from essay_writer.writing_basics import STAGE_ORDER

REPO = Path(__file__).resolve().parents[1]
LOOK = "Kept."
DRAFT_SENTENCE = "The firm cut emissions in 2024."


def _pointer_text(seq: str) -> str:
    return (work_dir(seq) / "tracking" / "stage.json").read_text(encoding="utf-8")


def _stage_note(seq: str, stage: str) -> str:
    return (work_dir(seq) / "tracking" / f"{stage}.md").read_text(encoding="utf-8")


def _write_docx(seq: str, text: str) -> None:
    path = work_dir(seq) / "output" / f"{seq}.docx"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.add_paragraph(text)
    document.save(str(path))


def _through(seq: str, stop: str) -> None:
    for stage in STAGE_ORDER:
        if stage == stop:
            return
        draft = essay_stage(seq, stage, "draft", LOOK)
        assert draft["ok"] is True, draft
        if stage == "4a":
            plant_gathered_source(seq)
        if stage == "5":
            assert draft["stored"] is True, draft
            continue
        saved = essay_stage(seq, stage, "confirm", LOOK, **picked(draft))
        assert saved["stored"] is True, saved


def _ask_stage7(seq: str) -> dict:
    _through(seq, "7")
    _write_docx(seq, DRAFT_SENTENCE)
    asked = essay_stage(seq, "7", "draft", LOOK)
    assert asked["ok"] is True, asked
    assert asked["questions"]
    assert "Please answer these questions" in asked["next"]
    return asked


def test_ac1_room_agent_confirms_with_draft_fields(workspace):
    """AC1: confirm copies cardAction and cardDigest from the draft. Nothing is invented."""
    seq = open_sequence()
    look = "The task is a short report."
    draft = front_office_call(
        "essay.stage",
        {"essay_id": seq, "stage": "1", "confirmPhase": "draft", "look": look},
    )
    assert draft["ok"] is True, draft
    assert draft["stored"] is False
    assert draft["cardAction"] == "confirm"
    assert draft["cardDigest"] == draft["digest"]
    assert draft["card"]["cardAction"] == "confirm"
    assert draft["card"]["cardDigest"] == draft["digest"]
    assert draft["card"]["digest"] == draft["digest"]
    assert len(draft["cardDigest"]) == 64

    pressed = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "1",
            "confirmPhase": "confirm",
            "look": "Press Confirm for Stage N",
        },
    )
    assert pressed["ok"] is False
    assert pressed["refused"] == "confirm-card"
    assert pressed["stored"] is not True
    assert pressed.get("advanced") is not True
    assert pressed["cardAction"] == draft["cardAction"]
    assert pressed["cardDigest"] == draft["cardDigest"]
    assert pressed["card"]["cardDigest"] == draft["digest"]
    assert load_pointer(seq)["saved"] == []
    assert load_pointer(seq)["current"] == "1"

    invented = essay_stage(
        seq,
        "1",
        "confirm",
        cardAction="confirm",
        cardDigest="a" * 64,
    )
    assert invented["ok"] is False
    assert invented["stored"] is not True
    assert load_pointer(seq)["current"] == "1"

    saved = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "1",
            "confirmPhase": "confirm",
            "cardAction": pressed["cardAction"],
            "cardDigest": pressed["cardDigest"],
        },
    )
    assert saved["ok"] is True, saved
    assert saved["stored"] is True
    assert saved["current"] == "2"
    assert "1" in load_pointer(seq)["saved"]

    assert ROOM_CONFIRM_PATH in INSTRUCTIONS
    assert "Do not invent a digest." in ROOM_CONFIRM_PATH
    assert ROOM_CONFIRM_PATH in stage_tool_description()
    assert STAGE7_AFTER_ANSWERS in stage_tool_description()
    door = next(item["description"] for item in DOORS if item["tool"] == "essay.stage")
    assert "Do not invent a digest." in door
    sheet = (REPO / "docs" / "templates" / "bot.md").read_text(encoding="utf-8")
    assert "unable to tap the Confirm card" in sheet
    assert "Do not invent a digest." in sheet
    assert "Press Confirm for Stage N" in sheet


def test_ac2_stage7_answers_present_confirm(workspace):
    """AC2: stage 7 answers, including no changes, present Confirm and a next ask."""
    seq = open_sequence()
    _ask_stage7(seq)
    held = essay_stage(
        seq,
        "7",
        "draft",
        LOOK,
        answers="Change the year.",
        webCheck={"currency": True, "tone": True},
    )
    assert held["ok"] is False, held
    assert held["stored"] is not True
    assert isinstance(held.get("next"), str) and held["next"].strip()
    assert "no changes" in held["next"].casefold()
    assert "Status: draft" in _stage_note(seq, "7")
    assert "Status: final" not in _stage_note(seq, "7")
    assert load_pointer(seq)["current"] == "7"
    assert "7" not in load_pointer(seq)["saved"]

    blocked_check = essay_stage(
        seq,
        "7",
        "draft",
        LOOK,
        answers="all fine / none",
        webCheck={"currency": False},
    )
    assert blocked_check["ok"] is False, blocked_check
    assert isinstance(blocked_check.get("next"), str) and blocked_check["next"].strip()
    assert blocked_check["stored"] is not True
    assert load_pointer(seq)["current"] == "7"

    answered = essay_stage(seq, "7", "draft", LOOK, answers="all fine / none")
    assert answered["ok"] is True, answered
    assert answered["stored"] is False
    assert answered["delta"] == []
    assert answered["card"]["kind"] == "confirm"
    assert answered["cardAction"] == "confirm"
    assert answered["cardDigest"] == answered["digest"]
    assert answered["next"].startswith("Open the Confirm card to save Stage 7")
    assert "Please answer these questions" not in answered["next"]
    assert "Status: draft" in _stage_note(seq, "7")
    assert load_pointer(seq)["current"] == "7"
    assert "7" not in load_pointer(seq)["saved"]
    assert NEED_EDIT not in answered["next"]

    pressed = essay_stage(seq, "7", "confirm", look="Press Confirm for Stage 7")
    assert pressed["ok"] is False
    assert pressed["stored"] is not True
    assert pressed["cardDigest"] == answered["cardDigest"]
    assert "Status: draft" in _stage_note(seq, "7")
    assert load_pointer(seq)["current"] == "7"

    other = open_sequence(OTHER)
    _ask_stage7(other)
    spoken = front_office_call(
        "essay.stage",
        {"essay_id": other, "stage": "7", "confirmPhase": "draft", "look": "no changes"},
    )
    assert spoken["ok"] is True, spoken
    assert spoken["cardAction"] == "confirm"
    assert spoken["cardDigest"] == spoken["digest"]
    assert spoken["next"].startswith("Open the Confirm card to save Stage 7")
    assert spoken["stored"] is False
    assert "Status: draft" in _stage_note(other, "7")
    assert isinstance(spoken.get("next"), str) and spoken["next"].strip()


def test_ac3_typed_confirm_does_not_save(workspace):
    """AC3: typed Confirm, yes, or ok still does not save. The card path does."""
    seq = open_sequence()
    look = "The task is a short report."
    draft = essay_stage(seq, "1", "draft", look)
    before = _pointer_text(seq)
    for typed in ("Confirm", "yes", "ok", "Yes", "OK"):
        spoken = front_office_call(
            "essay.stage",
            {"essay_id": seq, "stage": "1", "confirmPhase": "confirm", "look": typed},
        )
        assert spoken["ok"] is False
        assert spoken["refused"] == "confirm-card"
        assert spoken["stored"] is not True
        assert spoken["wrote"] is False
        assert spoken["card"]["digest"] == draft["digest"]
        assert spoken["cardDigest"] == draft["digest"]
        assert "Confirm card" in spoken["next"]
        assert _pointer_text(seq) == before

        spoken = front_office_call(
            "essay.stage",
            {
                "essay_id": seq,
                "stage": "1",
                "confirmPhase": "confirm",
                "look": look,
                "cardAction": typed,
                "cardDigest": draft["digest"],
            },
        )
        assert spoken["ok"] is False
        assert spoken["refused"] == "confirm-card"
        assert spoken["stored"] is not True
        assert spoken["cardDigest"] == draft["digest"]
        assert _pointer_text(seq) == before

    saved = essay_stage(seq, "1", "confirm", **picked(draft))
    assert saved["stored"] is True
    assert saved["current"] == "2"


def test_ac4_stage7_confirm_advances(workspace, monkeypatch):
    """AC4: stage 7 Confirm saves and moves to stage 8 on the shared door."""
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_GROK_BUILD)
    seq = open_sequence()
    _ask_stage7(seq)
    answered = essay_stage(seq, "7", "draft", LOOK, answers="all fine / none")
    assert answered["ok"] is True, answered
    assert load_pointer(seq)["current"] == "7"
    assert "7" not in load_pointer(seq)["saved"]

    typed = essay_stage(
        seq,
        "7",
        "confirm",
        "yes",
        cardAction="yes",
        cardDigest=answered["cardDigest"],
    )
    assert typed["ok"] is False
    assert typed["refused"] == "confirm-card"
    assert typed["stored"] is not True
    assert load_pointer(seq)["current"] == "7"
    assert "Status: draft" in _stage_note(seq, "7")

    saved = essay_stage(
        seq,
        "7",
        "confirm",
        cardAction=answered["cardAction"],
        cardDigest=answered["cardDigest"],
    )
    assert saved["ok"] is True, saved
    assert saved["stored"] is True
    assert saved["advanced"] is True
    assert saved["current"] == "8"
    assert saved["current"] != "7"
    assert "7" in load_pointer(seq)["saved"]
    assert load_pointer(seq)["current"] == "8"
    assert saved["chain_armed"] is True
    assert saved["executed_runs"] == ["7"]
    assert saved["next_run"]["stage"] == "8"
    assert saved["next_run"]["runs_in_this_step"] == 1
    assert "Status: final" in _stage_note(seq, "7")
    assert '"current": "8"' in _pointer_text(seq)
    assert saved["mid_office_launch"]["command"][0] == "grok"

    cursor_rules = cursor_stage_launch("7")["settings"]["rules"]
    build_rules = stage_launch("7")["settings"]["rules"]
    assert cursor_rules == build_rules == stage_settings("7")["rules"]
    assert "ask questions" in build_rules.casefold() or "asks questions" in build_rules
    build_source = Path(stage_launch.__code__.co_filename).read_text(encoding="utf-8")
    cursor_source = Path(cursor_stage_launch.__code__.co_filename).read_text(encoding="utf-8")
    assert "def essay_stage" not in build_source
    assert "def confirm_card" not in build_source
    assert "def essay_stage" not in cursor_source
    assert "def confirm_card" not in cursor_source
    assert cursor_shell()["handlers"]["essay.stage"] is HANDLERS["essay.stage"]
    assert front_office()["handlers"]["essay.stage"] is HANDLERS["essay.stage"]

    assert STAGE7_AFTER_ANSWERS.split(".")[0] in INSTRUCTIONS
