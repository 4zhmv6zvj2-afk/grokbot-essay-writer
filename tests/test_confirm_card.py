"""Stage Confirm is a clickable card. A stored stage 5 starts stage 6."""

from pathlib import Path

from helpers import open_sequence, picked, plant_gathered_source

from essay_writer.build_office import stage_launch
from essay_writer.late_chain import STAGE6_OPEN
from essay_writer.server import HANDLERS
from essay_writer.shells import cursor_shell, front_office, front_office_call
from essay_writer.spine import AUTO_START, advances_without_confirm
from essay_writer.stage_track import essay_stage, load_pointer
from essay_writer.writing_basics import STAGE_ORDER


def _save_until(seq: str, stop: str) -> None:
    look = "Saved from the brief."
    for stage in STAGE_ORDER:
        if stage == stop:
            return
        draft = essay_stage(seq, stage, "draft", look)
        assert draft["ok"] is True, draft
        if stage == "4a":
            plant_gathered_source(seq)
        if stage == "5":
            assert draft["stored"] is True, draft
            continue
        saved = essay_stage(seq, stage, "confirm", look, **picked(draft))
        assert saved["stored"] is True, saved


def test_a_stage_draft_is_a_card_and_typed_words_do_not_save(workspace):
    seq = open_sequence()
    draft = essay_stage(seq, "1", "draft", "The task is a short report.")
    card = draft["card"]
    assert card["deliver"] == "chat"
    assert card["kind"] == "confirm"
    assert card["essay_id"] == seq
    assert card["stage"] == "1"
    assert card["digest"] == draft["digest"]
    assert card["text"]
    assert card["actions"] == [
        {"id": "confirm", "label": "Confirm"},
        {"id": "not_yet", "label": "Not yet"},
    ]
    assert "Say yes" not in draft["next"]
    assert draft["stored"] is False
    for action in ("ok", "yes", "Confirm", None):
        refused = essay_stage(
            seq, "1", "confirm", "The task is a short report.",
            cardAction=action, cardDigest=draft["digest"],
        )
        assert refused["ok"] is False
        assert refused["refused"] == "confirm-card"
        assert load_pointer(seq)["saved"] == []
    mismatch = essay_stage(
        seq, "1", "confirm", "The task is a short report.",
        cardAction="confirm", cardDigest="not-the-card",
    )
    assert mismatch["refused"] == "confirm-card"
    assert mismatch["stored"] is not True
    held = essay_stage(
        seq, "1", "confirm", "The task is a short report.",
        cardAction="not_yet", cardDigest=draft["digest"],
    )
    assert held["refused"] == "confirm-card"
    saved = essay_stage(seq, "1", "confirm", "The task is a short report.", **picked(draft))
    assert saved["stored"] is True
    assert saved["current"] == "2"
    assert saved["repost"] is False
    assert saved["card"]["stage"] == "2"
    assert saved["card"]["kind"] == "confirm"


def test_both_shells_speak_the_same_stage_card(workspace):
    seq = open_sequence()
    arguments = {"essay_id": seq, "stage": "1", "confirmPhase": "draft", "look": "The task is a short report."}
    spoken = front_office_call("essay.stage", arguments)
    assert spoken["card"]["kind"] == "confirm"
    assert spoken["card"]["actions"][0]["label"] == "Confirm"
    assert cursor_shell()["handlers"]["essay.stage"] is HANDLERS["essay.stage"]
    assert front_office()["handlers"]["essay.stage"] is HANDLERS["essay.stage"]
    refused = front_office_call(
        "essay.stage",
        {"essay_id": seq, "stage": "1", "confirmPhase": "confirm", "look": "ok"},
    )
    assert refused["refused"] == "confirm-card"
    assert load_pointer(seq)["current"] == "1"


def test_stage5_starts_stage6_and_later_stages_keep_their_cards(workspace):
    seq = open_sequence()
    _save_until(seq, "5")
    assert load_pointer(seq)["current"] == "5"
    early = essay_stage(seq, "5", "confirm", "The first draft can start.")
    assert early["ok"] is False
    assert early["refused"] == "confirm-card"
    assert load_pointer(seq)["current"] == "5"
    done = essay_stage(seq, "5", "draft", "The first draft can start.")
    assert done["stored"] is True
    assert done["advanced"] is True
    assert done["current"] == "6"
    assert done["started"]["stage"] == "6"
    assert done["started"]["chain_started"] is False
    assert "card" not in done
    assert done["next"] == STAGE6_OPEN
    assert "Say yes" not in done["next"]
    assert done["checklist_in_chat"] is False
    assert "tracking/" not in done["next"]
    from essay_writer.paths import work_dir
    assert not (work_dir(seq) / "tracking" / "6.md").is_file()
    again = essay_stage(seq, "5", "confirm", "The first draft can start.", cardAction="confirm")
    assert again["ok"] is False
    assert AUTO_START == {"5": "6"}
    assert advances_without_confirm("7") is None
    assert advances_without_confirm("8") is None
    assert advances_without_confirm("9") is None
    launch = stage_launch("1")
    assert "kind" not in launch
    office = Path(stage_launch.__code__.co_filename).read_text(encoding="utf-8")
    assert "def confirm_card" not in office
    assert "def essay_stage" not in office
