"""Private banking Relationship Manager speech, idle heartbeat, and the curtain."""

from pathlib import Path

from helpers import open_sequence, picked, plant_gathered_source

from essay_writer.build_office import stage_launch
from essay_writer.build_status import (
    HEARTBEAT_SECONDS,
    attach_launch_status,
    begin_mid_build,
    heartbeat_sentence,
    pump_idle,
    reset_status,
)
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.late_chain import (
    FIRST_DRAFT_READY,
    QUIET_STEP,
    STAGE6_OPEN,
    quiet_next,
)
from essay_writer.projects import essay_project_delete, essay_projects
from essay_writer.server import INSTRUCTIONS
from essay_writer.shells import front_office_call, mount_handler
from essay_writer.specialists.grok_bot import (
    ROLE_NOTE,
    card_next,
    hide_curtain,
    stage7_lead,
)
from essay_writer.spine import AUTO_START
from essay_writer.stage7 import _QUESTIONS
from essay_writer.stage_track import essay_stage
from essay_writer.student_voice import say


def test_role_note_is_a_bespoke_private_banking_relationship_manager():
    text = ROLE_NOTE
    assert "private banking Relationship Manager" in text
    assert "bespoke" in text.casefold()
    assert "brief" in text
    assert "mark scheme" in text
    assert "Not sales." in text
    assert "Not thin customer service." in text
    assert "Not a generic bank role" in text
    assert "customer service only" not in text.casefold()
    assert "satisfaction" in text
    assert "behind the curtain" in text
    assert "Propose options" in text
    assert "first three steps" in text
    assert "the service failed" in text
    assert "private banking Relationship Manager" in INSTRUCTIONS
    assert "Not sales." in INSTRUCTIONS
    sheet = (Path(__file__).resolve().parents[1] / "docs" / "templates" / "bot.md").read_text(encoding="utf-8")
    assert "private banking Relationship Manager" in sheet
    assert "generic script" in sheet.casefold()


def test_stage6_and_quiet_lines_are_a_verb_and_a_destination():
    assert STAGE6_OPEN == "Your draft is saved. Start the first read in this chat."
    assert "saved" in STAGE6_OPEN.casefold()
    assert "first read" in STAGE6_OPEN.casefold()
    assert STAGE6_OPEN != "Stage 6 is the first read."
    assert QUIET_STEP == "Wait while the first draft is written."
    assert "Say yes" not in QUIET_STEP
    assert FIRST_DRAFT_READY == "Read the first draft in this chat."
    assert quiet_next("8", armed=True, blocked=False, place="Documents/x") is None
    assert quiet_next("9", armed=True, blocked=False, place="Documents/x") is None
    assert "Say yes" not in card_next("8", "Edit and redraft")
    assert card_next("4a", "Annotated bibliography").startswith("Open the Confirm card to save Stage 4a")
    assert "Confirm card" in say(card_next("4a", "Annotated bibliography"))
    assert AUTO_START == {"5": "6"}


def test_stage7_lead_names_the_questions_and_the_confirm_card():
    lead = stage7_lead(list(_QUESTIONS), "Ask for feedback")
    assert lead.startswith("Please answer these questions in this chat.")
    for question in _QUESTIONS:
        assert question in lead
    assert "Then open the Confirm card to save Stage 7" in lead
    assert "Not yet" in lead
    assert "waiting" not in lead.casefold()
    assert "Say yes" not in lead


def test_idle_clock_posts_a_heartbeat_without_a_door_reply(monkeypatch):
    reset_status()
    clock = {"t": 0.0}
    monkeypatch.setattr("essay_writer.build_status._now", lambda: clock["t"])
    begin_mid_build("MOD1004AA-2", "gathering", subject="the Inditex question")
    clock["t"] = HEARTBEAT_SECONDS
    posted = pump_idle()
    assert posted == [heartbeat_sentence("gathering", "the Inditex question")]
    assert "still working on the Inditex question" in posted[0]
    assert "cursor" not in posted[0].casefold()
    assert "cli" not in posted[0].casefold()
    assert "/" not in posted[0]
    cursor = Path(cursor_stage_launch.__code__.co_filename).read_text(encoding="utf-8")
    build = Path(stage_launch.__code__.co_filename).read_text(encoding="utf-8")
    assert "attach_launch_status" in cursor
    assert "attach_launch_status" in build
    assert "pump_idle" in Path(attach_launch_status.__code__.co_filename).read_text(encoding="utf-8")
    reset_status()


def test_front_office_hides_the_launch_and_curtain_echoes(workspace):
    seq = open_sequence()
    raw = essay_stage(seq, "1", "draft", "The task is a short report.")
    assert "command" in raw["mid_office_launch"]
    spoken = front_office_call(
        "essay.stage",
        {"essay_id": seq, "stage": "1", "confirmPhase": "draft", "look": "The task is a short report."},
    )
    assert spoken["ok"] is True
    assert "mid_office_launch" not in spoken
    assert "--model" not in spoken["next"]
    assert spoken["card"]["actions"][0]["label"] == "Confirm"
    assert spoken["next"].startswith("Open the Confirm card to save Stage 1")
    mounted = mount_handler("essay.stage")
    live = mounted(
        essay_id=seq,
        stage="1",
        confirmPhase="draft",
        look="The task is a short report.",
    )
    assert "mid_office_launch" not in live
    assert live["card"]["kind"] == "confirm"
    assert "status" not in live or all("agent" not in line.casefold() for line in live["status"])
    echoed = hide_curtain("launching Cursor CLI… see cli-prompt and status-run.txt")
    assert "cli" not in echoed.casefold()
    scratch = hide_curtain("Read output/5-draft-scratch/cli-prompt and agent-cli.log")
    assert scratch == echoed
    assert "draft-scratch" not in scratch
    assert "agent-cli" not in scratch
    assert "status" not in echoed.casefold()
    assert echoed == hide_curtain("The Researcher will run agent --model grok-4.7")


def test_delete_uses_a_confirm_card_and_a_typed_yes_does_not_remove(workspace):
    open_sequence()
    from helpers import ESSAY

    draft = essay_project_delete(ESSAY, "draft")
    assert draft["ok"] is True
    assert draft["wrote"] is False
    assert draft["card"]["kind"] == "confirm"
    assert draft["card"]["actions"] == [
        {"id": "confirm", "label": "Confirm"},
        {"id": "not_yet", "label": "Not yet"},
    ]
    assert "Confirm card" in draft["next"]
    assert "yes" not in draft["next"].casefold()
    typed = essay_project_delete(ESSAY, "confirm", cardAction="yes", cardDigest=draft["digest"])
    assert typed["refused"] == "confirm-card"
    assert typed["deleted"] is not True
    held = essay_project_delete(ESSAY, "confirm", cardAction="not_yet", cardDigest=draft["digest"])
    assert held["refused"] == "confirm-card"
    assert held["stored"] is not True
    removed = essay_project_delete(ESSAY, "confirm", **picked(draft))
    assert removed["deleted"] is True


def test_wrong_stage_refuse_stays_a_gate_in_student_english(workspace):
    seq = open_sequence()
    refused = essay_stage(seq, "7", "draft", "Still on the first step.")
    assert refused["ok"] is False
    assert refused["refused"] == "stage"
    assert refused["stored"] is not True
    assert "current stage is 1" in refused["reason"]
    assert "Send that stage" not in refused["reason"]
    assert "confirmPhase" not in refused["reason"]
    assert "before stage 7" in refused["reason"]


def test_roll_forward_speech_has_no_tool_id(workspace):
    open_sequence()
    from helpers import ESSAY

    row = essay_projects("continue")["rows"][0]
    speech = row["roll_forward_next"]
    assert "essay." not in speech
    assert "roll_forward_next" not in speech
    assert "confirmPhase" not in speech
    assert ESSAY in speech
    view = essay_projects("roll-forward", ESSAY)
    assert "essay." not in view["next"]
    assert "confirmPhase" not in view["next"]
    assert "yes" not in view["next"].casefold()


def test_stage7_draft_leads_with_questions(workspace):
    seq = open_sequence()
    look = "Kept."
    for stage in ("1", "2", "3", "4a", "4b", "5", "6"):
        draft = essay_stage(seq, stage, "draft", look)
        assert draft["ok"] is True, draft
        if stage == "4a":
            plant_gathered_source(seq)
        if stage == "5":
            assert "card" not in draft
            assert draft["next"] == STAGE6_OPEN
            continue
        saved = essay_stage(seq, stage, "confirm", look, **picked(draft))
        assert saved["stored"] is True, saved
    asked = essay_stage(seq, "7", "draft", look)
    assert asked["ok"] is True, asked
    assert asked["questions"]
    assert asked["next"].startswith("Please answer these questions")
    assert "Confirm card" in asked["next"]
    assert asked["card"]["actions"] == [
        {"id": "confirm", "label": "Confirm"},
        {"id": "not_yet", "label": "Not yet"},
    ]
    refused = essay_stage(seq, "7", "confirm", look, cardAction="yes", cardDigest=asked["digest"])
    assert refused["refused"] == "confirm-card"
    assert refused["stored"] is not True
