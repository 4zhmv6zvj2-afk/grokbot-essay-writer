"""Stage confirm isolation. Stable ids: AC1, AC2, AC3, AC4.

One Confirm saves one stage. Press Confirm for Stage 1 does not save 2 or 3.
Stage 4a stays unsaved until its own Confirm. A typed yes saves only the waiting card,
and the reply still names the Confirm card.
"""

from pathlib import Path

from helpers import OTHER, open_sequence, picked, plant_gathered_source

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.prompt_loader import text as prompt_text
from essay_writer.server import HANDLERS, INSTRUCTIONS
from essay_writer.setup import SHELL_GROK_BUILD
from essay_writer.shells import cursor_shell, front_office, front_office_call
from essay_writer.spine import AUTO_START, advances_without_confirm
from essay_writer.stage_llm import stage_settings, stage_tool_description
from essay_writer.stage_state import load_pointer
from essay_writer.stage_track import essay_stage
from essay_writer.writing_basics import STAGE_ORDER

STAGE_CONFIRM_EACH = prompt_text("front_office/confirm.md", "stage_confirm_each")

REPO = Path(__file__).resolve().parents[1]
LOOK = "Kept."


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


def test_ac1_stage_confirm_saves_only_that_stage(workspace):
    """AC1: stage N needs its own Confirm. Press Confirm for Stage 1 does not save 2 or 3."""
    seq = open_sequence()
    look = "The task is a short report."
    draft = essay_stage(seq, "1", "draft", look)
    assert draft["stored"] is False

    pressed = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "1",
            "confirmPhase": "confirm",
            "look": "Press Confirm for Stage 1",
        },
    )
    assert pressed["ok"] is False
    assert pressed["stored"] is not True
    assert pressed["waiting_confirm"] is True
    assert load_pointer(seq)["saved"] == []
    assert load_pointer(seq)["current"] == "1"

    saved = essay_stage(
        seq,
        "1",
        "confirm",
        cardAction=pressed["cardAction"],
        cardDigest=pressed["cardDigest"],
    )
    assert saved["ok"] is True, saved
    assert saved["stored"] is True
    assert load_pointer(seq)["saved"] == ["1"]
    assert load_pointer(seq)["current"] == "2"
    assert "2" not in load_pointer(seq)["saved"]
    assert "3" not in load_pointer(seq)["saved"]
    assert saved.get("card") is None
    assert saved["repost"] is False
    assert load_pointer(seq)["waiting_stage"] is None
    assert load_pointer(seq)["waiting_digest"] is None

    reused = essay_stage(seq, "2", "confirm", look="Press Confirm for Stage 1")
    assert reused.get("stored") is not True
    assert reused["stored"] is not True
    assert load_pointer(seq)["saved"] == ["1"]
    assert "2" not in load_pointer(seq)["saved"]

    draft2 = essay_stage(seq, "2", "draft", "Purpose and scope stay with the brief.")
    assert draft2["ok"] is True, draft2
    assert draft2["stored"] is False
    jumped = essay_stage(seq, "2", "confirm", **picked(draft2))
    assert jumped["ok"] is False
    assert jumped["stored"] is not True
    assert jumped["waiting_confirm"] is True
    assert "Confirm card" in jumped["next"]
    assert load_pointer(seq)["saved"] == ["1"]
    assert load_pointer(seq)["current"] == "2"
    assert "3" not in load_pointer(seq)["saved"]

    early3 = essay_stage(seq, "3", "confirm", **picked(draft2))
    assert early3["stored"] is not True
    assert load_pointer(seq)["saved"] == ["1"]
    assert isinstance(early3.get("next"), str) and early3["next"].strip()

    press2 = essay_stage(seq, "2", "confirm", look="Press Confirm for Stage 2")
    assert press2["stored"] is not True
    assert load_pointer(seq)["saved"] == ["1"]
    saved2 = essay_stage(
        seq,
        "2",
        "confirm",
        cardAction=press2["cardAction"],
        cardDigest=press2["cardDigest"],
    )
    assert saved2["stored"] is True, saved2
    assert load_pointer(seq)["saved"] == ["1", "2"]
    assert "3" not in load_pointer(seq)["saved"]
    assert load_pointer(seq)["current"] == "3"

    chain = open_sequence(OTHER)
    _through(chain, "6")
    assert load_pointer(chain)["current"] == "6"
    assert "5" in load_pointer(chain)["saved"]
    assert "6" not in load_pointer(chain)["saved"]
    assert AUTO_START == {"5": "6"}
    assert advances_without_confirm("5") == "6"
    for stage in ("1", "2", "3", "4a", "4b", "6", "7", "8", "9", "10"):
        assert advances_without_confirm(stage) is None

    assert STAGE_CONFIRM_EACH in INSTRUCTIONS
    assert STAGE_CONFIRM_EACH not in stage_tool_description()
    sheet = (REPO / "docs" / "templates" / "bot.md").read_text(encoding="utf-8")
    assert STAGE_CONFIRM_EACH in sheet
    assert "does not save stage N+1" in STAGE_CONFIRM_EACH


def test_ac2_stage_4a_needs_its_own_confirm(workspace, monkeypatch):
    """AC2: stage 4a is saved only by its own Confirm, and only then does current become 4b."""
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_GROK_BUILD)
    seq = open_sequence()
    _through(seq, "4a")
    assert load_pointer(seq)["current"] == "4a"
    assert load_pointer(seq)["saved"] == ["1", "2", "3"]
    assert "4a" not in load_pointer(seq)["saved"]

    drafted = essay_stage(seq, "4a", "draft", "The annotated list is still empty.")
    assert drafted["ok"] is True, drafted
    assert drafted["stored"] is False
    assert "4a" not in load_pointer(seq)["saved"]
    assert load_pointer(seq)["current"] == "4a"

    typed = front_office_call(
        "essay.stage",
        {"essay_id": seq, "stage": "4a", "confirmPhase": "confirm", "look": "Confirm"},
    )
    assert typed["ok"] is False
    assert typed["stored"] is not True
    assert typed["waiting_confirm"] is True
    assert "Confirm card" in typed["next"]
    assert "4a" not in load_pointer(seq)["saved"]
    assert load_pointer(seq)["current"] == "4a"

    other_press = essay_stage(seq, "4a", "confirm", look="Press Confirm for Stage 1")
    assert other_press["stored"] is not True
    assert other_press["advanced"] is not True
    assert "4a" not in load_pointer(seq)["saved"]
    assert load_pointer(seq)["current"] == "4a"
    assert load_pointer(seq)["current"] != "4b"

    plant_gathered_source(seq)
    saved = essay_stage(seq, "4a", "confirm", **picked(drafted))
    assert saved["ok"] is True, saved
    assert saved["stored"] is True
    assert "4a" in load_pointer(seq)["saved"]
    assert load_pointer(seq)["current"] == "4b"
    assert "4b" not in load_pointer(seq)["saved"]
    assert saved.get("card") is None
    assert saved["repost"] is False
    assert load_pointer(seq)["waiting_stage"] is None

    cursor_rules = cursor_stage_launch("4a")["settings"]["rules"]
    build_rules = stage_launch("4a")["settings"]["rules"]
    assert cursor_rules == build_rules == stage_settings("4a")["rules"]
    build_source = Path(stage_launch.__code__.co_filename).read_text(encoding="utf-8")
    cursor_source = Path(cursor_stage_launch.__code__.co_filename).read_text(encoding="utf-8")
    assert "def essay_stage" not in build_source
    assert "def essay_stage" not in cursor_source
    assert cursor_shell()["handlers"]["essay.stage"] is HANDLERS["essay.stage"]
    assert front_office()["handlers"]["essay.stage"] is HANDLERS["essay.stage"]


def test_ac3_typed_confirm_saves_the_waiting_card(workspace):
    """AC3: a typed Confirm, yes, or ok on a waiting card saves that stage."""
    for index, typed in enumerate(("Confirm", "yes", "ok", "Yes"), start=1):
        seq = open_sequence()
        look = f"The task is a short report. Pass {index}."
        draft = essay_stage(seq, "1", "draft", look)
        assert draft["ok"] is True, draft
        spoken = front_office_call(
            "essay.stage",
            {"essay_id": seq, "stage": "1", "confirmPhase": "confirm", "look": typed},
        )
        assert spoken["ok"] is True, spoken
        assert spoken["stored"] is True
        assert spoken["current"] == "2"
        assert load_pointer(seq)["saved"] == ["1"]

    # A card field that is not the Confirm action still refuses.
    seq = open_sequence()
    look = "The task is a short report."
    draft = essay_stage(seq, "1", "draft", look)
    refused = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "1",
            "confirmPhase": "confirm",
            "look": look,
            "cardAction": "yes",
            "cardDigest": draft["digest"],
        },
    )
    assert refused["ok"] is False
    assert refused["refused"] == "confirm-card"
    assert refused["stored"] is not True
    assert load_pointer(seq)["saved"] == []

    saved = essay_stage(seq, "1", "confirm", **picked(draft))
    assert saved["stored"] is True
    assert saved["current"] == "2"
    assert load_pointer(seq)["saved"] == ["1"]


def test_ac4_typed_confirm_does_not_resave_a_saved_stage(workspace):
    """AC4: a typed yes saves only the waiting card, never an earlier saved stage."""
    seq = open_sequence()
    look = "The task is a short report."
    draft = essay_stage(seq, "1", "draft", look)
    saved = essay_stage(seq, "1", "confirm", **picked(draft))
    assert saved["stored"] is True, saved
    assert load_pointer(seq)["saved"] == ["1"]

    early = front_office_call(
        "essay.stage",
        {"essay_id": seq, "stage": "1", "confirmPhase": "confirm", "look": "yes"},
    )
    assert early["ok"] is False, early
    assert early["stored"] is not True
    assert load_pointer(seq)["saved"] == ["1"]
    assert load_pointer(seq)["current"] == "2"
