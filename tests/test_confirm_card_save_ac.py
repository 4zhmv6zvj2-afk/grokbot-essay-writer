"""Confirm card save. Stable ids: AC1, AC2, AC3, AC4.

Stage 2 Confirm does not save stage 3. Press Confirm together with the waiting
card saves that stage in one call. Mid-build status is the same for Cursor CLI
and Grok Build. After stage 7 questions, skip is refused and all fine opens Confirm.
"""

import hashlib
from pathlib import Path

from docx import Document
from helpers import OTHER, open_sequence, picked, plant_gathered_source

from essay_writer.build_office import report_phase as build_report_phase
from essay_writer.build_office import stage_launch
from essay_writer.build_status import (
    HEARTBEAT_SECONDS,
    MID_BUILD_DOOR,
    MID_BUILD_STATUS,
    MID_BUILD_STATUS_ID,
    TIP_SHEET,
    basis_for,
    begin_mid_build,
    due_lines,
    launch_status,
    reply_status,
    reset_status,
    tip_sheet,
)
from essay_writer.cursor_office import (
    cursor_stage_launch,
    report_phase,
    stage_host_launch,
)
from essay_writer.paths import work_dir
from essay_writer.server import HANDLERS, INSTRUCTIONS
from essay_writer.setup import SHELL_CURSOR, SHELL_GROK_BUILD
from essay_writer.shells import cursor_shell, front_office, front_office_call
from essay_writer.stage7 import _QUESTIONS
from essay_writer.stage_llm import stage_tool_description
from essay_writer.stage_track import essay_stage, load_pointer
from essay_writer.writing_basics import STAGE_ORDER

REPO = Path(__file__).resolve().parents[1]
LOOK = "Kept."
DRAFT_SENTENCE = "The firm cut emissions in 2024."
MID_BUILD_STATUS_SHA = "1176fc960d1a0c53dc2e52cb64ffd28aa3cdd1a6897a31eea65a9cf3c4a9b6b7"
TIP_SHEET_SHA = "8c32946fcbfd8025cecac0e6c8979cfe53c09bb644bf684ca942743ff18929d2"


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


def _write_docx(seq: str, text: str) -> None:
    path = work_dir(seq) / "output" / f"{seq}.docx"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.add_paragraph(text)
    document.save(str(path))


def _ask_stage7(seq: str) -> dict:
    _through(seq, "7")
    _write_docx(seq, DRAFT_SENTENCE)
    asked = essay_stage(seq, "7", "draft", LOOK)
    assert asked["ok"] is True, asked
    assert asked["questions"]
    assert "Please answer these questions" in asked["next"]
    return asked


def _stage_note(seq: str, stage: str) -> str:
    return (work_dir(seq) / "tracking" / f"{stage}.md").read_text(encoding="utf-8")


def _press_card(seq: str, stage: str, draft: dict, *, door: bool = False) -> dict:
    """One call: Press Confirm for this stage plus the waiting card."""
    fields = {
        "essay_id": seq,
        "stage": stage,
        "confirmPhase": "confirm",
        "look": f"Press Confirm for Stage {stage}",
        "cardAction": draft["cardAction"],
        "cardDigest": draft["cardDigest"],
    }
    if door:
        return essay_stage(
            seq,
            stage,
            "confirm",
            fields["look"],
            cardAction=fields["cardAction"],
            cardDigest=fields["cardDigest"],
        )
    return front_office_call("essay.stage", fields)


def test_ac1_stage2_confirm_does_not_save_stage3(workspace):
    """AC1: Stage 2 Confirm leaves current at 3. Stage 3 waits for its own Confirm."""
    seq = open_sequence()
    saved: list[str] = []
    hops = (("1", "2"), ("2", "3"), ("3", "4a"))
    for stage, following in hops:
        draft = essay_stage(seq, stage, "draft", LOOK)
        assert draft["ok"] is True, draft
        assert draft["stored"] is False
        assert stage not in load_pointer(seq)["saved"]

        saved_now = _press_card(seq, stage, draft)
        assert saved_now["ok"] is True, saved_now
        assert saved_now["stored"] is True
        assert isinstance(saved_now.get("next"), str) and saved_now["next"].strip()
        saved.append(stage)
        pointer = load_pointer(seq)
        assert pointer["saved"] == saved
        assert pointer["current"] == following
        assert following not in pointer["saved"]
        assert pointer["room_grant"] is None
        assert pointer["room_lock"] is True
        later = work_dir(seq) / "tracking" / f"{following}.md"
        if later.is_file():
            later_text = later.read_text(encoding="utf-8")
            assert "Status: draft" in later_text
            assert "Status: final" not in later_text
        assert "Status: final" in _stage_note(seq, stage)

        nxt = essay_stage(seq, following, "draft", LOOK)
        assert nxt["ok"] is True, nxt
        assert nxt["stored"] is False
        jumped = essay_stage(seq, following, "confirm", **picked(nxt))
        assert jumped["ok"] is False, jumped
        assert jumped["stored"] is not True
        assert isinstance(jumped.get("next"), str) and "Confirm card" in jumped["next"]
        assert load_pointer(seq)["saved"] == saved
        assert load_pointer(seq)["current"] == following
        assert "Status: final" not in _stage_note(seq, following)

    assert load_pointer(seq)["saved"] == ["1", "2", "3"]
    assert load_pointer(seq)["current"] == "4a"
    assert "4a" not in load_pointer(seq)["saved"]
    reused = essay_stage(seq, "3", "confirm", look="Press Confirm for Stage 2")
    assert reused["stored"] is not True
    assert load_pointer(seq)["saved"] == ["1", "2", "3"]


def test_ac2_press_with_card_saves_in_one_call(workspace, monkeypatch):
    """AC2: Press Confirm plus the waiting card saves. A second poke is not the save."""
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_GROK_BUILD)
    chain = open_sequence()
    _through(chain, "4b")
    assert load_pointer(chain)["current"] == "4b"
    assert "4b" not in load_pointer(chain)["saved"]
    notes = essay_stage(chain, "4b", "draft", LOOK)
    assert notes["ok"] is True, notes
    assert notes["stored"] is False
    finished = _press_card(chain, "4b", notes)
    assert finished["ok"] is True, finished
    assert finished["stored"] is True
    assert finished["current"] == "5"
    assert isinstance(finished.get("next"), str) and finished["next"].strip()
    assert load_pointer(chain)["saved"][-1] == "4b"
    assert "5" not in load_pointer(chain)["saved"]
    assert load_pointer(chain)["room_grant"] is None
    assert load_pointer(chain)["room_lock"] is True
    bare = essay_stage(chain, "5", "confirm", LOOK)
    assert bare["stored"] is not True
    assert isinstance(bare.get("next"), str) and bare["next"].strip()
    assert load_pointer(chain)["current"] == "5"

    seq = open_sequence(OTHER)
    draft = essay_stage(seq, "1", "draft", LOOK)
    assert draft["stored"] is False
    press = {
        "essay_id": seq,
        "stage": "1",
        "confirmPhase": "confirm",
        "look": "Press Confirm for Stage 1",
    }
    held = front_office_call("essay.stage", press)
    assert held["ok"] is False
    assert held["stored"] is not True
    assert isinstance(held.get("next"), str) and held["next"].strip()
    assert load_pointer(seq)["room_grant"] == "1"
    assert load_pointer(seq)["room_lock"] is False
    assert load_pointer(seq)["saved"] == []
    again = front_office_call("essay.stage", press)
    assert again["stored"] is not True
    assert isinstance(again.get("next"), str) and again["next"].strip()
    assert load_pointer(seq)["saved"] == []
    assert load_pointer(seq)["current"] == "1"

    saved = _press_card(seq, "1", draft)
    assert saved["ok"] is True, saved
    assert saved["stored"] is True
    assert saved["current"] == "2"
    assert isinstance(saved.get("next"), str) and saved["next"].strip()
    assert load_pointer(seq)["saved"] == ["1"]
    assert load_pointer(seq)["room_grant"] is None
    assert load_pointer(seq)["room_lock"] is True
    repeat = front_office_call(
        "essay.stage",
        {
            **press,
            "cardAction": draft["cardAction"],
            "cardDigest": draft["cardDigest"],
        },
    )
    assert repeat["stored"] is not True
    assert isinstance(repeat.get("next"), str) and repeat["next"].strip()
    assert load_pointer(seq)["saved"] == ["1"]
    assert load_pointer(seq)["current"] == "2"

    draft2 = essay_stage(seq, "2", "draft", LOOK)
    mute = essay_stage(
        seq,
        "2",
        "confirm",
        "huh",
        cardAction="not_yet",
        cardDigest=draft2["digest"],
    )
    assert mute["ok"] is False
    assert mute["stored"] is not True
    assert isinstance(mute.get("next"), str) and mute["next"].strip()
    assert load_pointer(seq)["saved"] == ["1"]
    assert load_pointer(seq)["current"] == "2"

    door = _press_card(seq, "2", draft2, door=True)
    assert door["ok"] is True, door
    assert door["stored"] is True
    assert door["current"] == "3"
    assert isinstance(door.get("next"), str) and door["next"].strip()
    assert load_pointer(seq)["saved"] == ["1", "2"]
    assert "3" not in load_pointer(seq)["saved"]
    assert load_pointer(seq)["room_grant"] is None
    assert load_pointer(seq)["room_lock"] is True

    assert cursor_shell()["handlers"]["essay.stage"] is HANDLERS["essay.stage"]
    assert front_office()["handlers"]["essay.stage"] is HANDLERS["essay.stage"]
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_CURSOR)
    assert stage_host_launch("4b")["status"] == stage_launch("4b")["status"]


def test_ac3_mid_build_status_is_wired_for_both_shells(workspace, monkeypatch):
    """AC3: start, signaled tips, one stale line, then done or Confirm. No invented phase."""
    reset_status()
    assert MID_BUILD_STATUS_ID == "mid-build-status"
    assert HEARTBEAT_SECONDS == 300
    digest = hashlib.sha256(MID_BUILD_STATUS.encode("utf-8")).hexdigest()
    assert digest == MID_BUILD_STATUS_SHA
    sheet_bytes = TIP_SHEET.read_text(encoding="utf-8")
    assert hashlib.sha256(sheet_bytes.encode("utf-8")).hexdigest() == TIP_SHEET_SHA
    assert "do not invent a phase" in MID_BUILD_STATUS.casefold()
    assert "not only research" in MID_BUILD_STATUS
    assert "stage 1 to 10" in MID_BUILD_STATUS
    assert "Never invent a band." in MID_BUILD_STATUS
    assert "no mid-office path is running" in MID_BUILD_STATUS
    assert "fixed clock" in MID_BUILD_STATUS
    assert MID_BUILD_STATUS in INSTRUCTIONS
    assert MID_BUILD_DOOR in stage_tool_description()
    assert "Cursor" not in MID_BUILD_DOOR
    assert "Grok Build" not in MID_BUILD_DOOR
    bot = (REPO / "docs" / "templates" / "bot.md").read_text(encoding="utf-8")
    workflow = (REPO / "docs" / "workflow.md").read_text(encoding="utf-8")
    for doc in (bot, workflow):
        assert "file-work path" in doc
        assert "do not invent a phase" in doc.casefold()
        assert "not only research" in doc
        assert "stage 1 to 10" in doc
        assert "Never invent a band." in doc
        assert "no file-work path is running" in doc
        assert "fixed clock" in doc
        assert "docs/templates/mid-status.md" in doc
    loaded = tip_sheet()
    for section, keys in (
        ("any", ("start", "still", "ready")),
        ("sources", ("gathering", "open_full", "list_notes")),
        ("deep_read", ("carefully", "helps_mark", "notes_ready")),
        ("draft", ("structure", "nearly", "confirm")),
        ("quality", ("check", "rewrite", "fixing", "clear")),
        ("ask_edit", ("questions", "apply", "currency", "heavier", "confirm")),
        ("word_final", ("together", "comments", "no_submit", "keep")),
    ):
        for key in keys:
            assert loaded[section][key]
            assert key in sheet_bytes or f"{key}:" in sheet_bytes

    for stage in ("4a", "4b", "5"):
        assert launch_status(stage)
        assert cursor_stage_launch(stage)["status"] == launch_status(stage)
        assert stage_launch(stage)["status"] == launch_status(stage)
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_CURSOR)
    cursor_launch = stage_host_launch("4b")
    assert cursor_launch["command"][0] == "agent"
    assert cursor_launch["status"] == launch_status("4b")
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_GROK_BUILD)
    build_launch = stage_host_launch("4b")
    assert build_launch["command"][0] == "grok"
    assert build_launch["status"] == launch_status("4b")
    for stage in ("1", "2", "3", "6", "7"):
        assert launch_status(stage) == []
        assert "status" not in cursor_stage_launch(stage)
        assert "status" not in stage_launch(stage)


    clock = {"t": 0.0}
    monkeypatch.setattr("essay_writer.build_status._now", lambda: clock["t"])
    seq = open_sequence()
    chat = front_office_call(
        "essay.stage",
        {"essay_id": seq, "stage": "1", "confirmPhase": "draft", "look": LOOK},
    )
    assert chat["ok"] is True, chat
    assert "status" not in chat
    quiet = reply_status(
        "essay.stage",
        {"essay_id": seq, "stage": "8", "confirmPhase": "draft"},
        {"ok": True, "essay_id": seq},
    )
    assert quiet == []

    _through(seq, "4b")
    started = front_office_call(
        "essay.stage",
        {"essay_id": seq, "stage": "4b", "confirmPhase": "draft", "look": LOOK},
    )
    assert started["ok"] is True, started
    assert started["stored"] is False
    assert "status" not in started
    clock["t"] = HEARTBEAT_SECONDS
    quiet_card = front_office_call("essay.originals", {"essay_id": seq})
    assert quiet_card["ok"] is True, quiet_card
    assert "status" not in quiet_card

    tipped = reply_status(
        "essay.stage",
        {"essay_id": seq, "stage": "4b", "confirmPhase": "draft", "look": LOOK},
        {"ok": True, "essay_id": seq, "mid_phases": ["open_full"]},
    )
    assert any("opens in full" in line for line in tipped)
    assert any("against" in line for line in tipped)
    invented = reply_status(
        "essay.stage",
        {"essay_id": seq, "stage": "4b", "confirmPhase": "confirm"},
        {"ok": True, "essay_id": seq, "stored": True},
    )
    assert not any("written a note on each source" in line for line in invented)
    assert any(line.endswith("is saved.") for line in invented)
    assert not any("Open the Confirm card" in line for line in invented)

    reset_status()
    clock["t"] = 0.0
    begin_mid_build(seq, "drafting", subject="the assignment ask")
    clock["t"] = HEARTBEAT_SECONDS
    assert due_lines(seq) == ["I am still working on the assignment ask."]
    clock["t"] = HEARTBEAT_SECONDS * 2
    assert due_lines(seq) == []
    reset_status()
    clock["t"] = 0.0
    begin_mid_build("other-seq", "editing", subject="the edit")
    clock["t"] = HEARTBEAT_SECONDS
    assert due_lines("other-seq") == ["I am still working on the edit."]

    reset_status()
    cursor_tip = report_phase(seq, "list_notes")
    reset_status()
    build_tip = build_report_phase(seq, "list_notes")
    assert cursor_tip == build_tip
    assert "source list and notes" in " ".join(cursor_tip)
    assert "Distinction" not in basis_for(seq)
    reset_status()


def test_ac4_stage7_skip_refuses_and_all_fine_opens_confirm(workspace):
    """AC4: skip is refused in-path. All fine opens Confirm and stays Status draft."""
    seq = open_sequence()
    asked = _ask_stage7(seq)
    assert load_pointer(seq)["current"] == "7"
    assert "7" not in load_pointer(seq)["saved"]

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
    assert "Status: draft" in _stage_note(seq, "7")
    assert "Status: final" not in _stage_note(seq, "7")
    assert load_pointer(seq)["current"] == "7"
    assert "7" not in load_pointer(seq)["saved"]

    probe = essay_stage(seq, "7", "draft", "Skip.")
    assert probe["ok"] is False, probe
    assert probe["stored"] is not True
    assert "Please answer these questions" in probe["next"]
    assert "Skipping the questions does not save" in probe["next"]
    assert load_pointer(seq)["current"] == "7"

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
    assert "Please answer these questions" not in opened["next"]
    assert isinstance(opened.get("next"), str) and opened["next"].strip()
    assert "Status: draft" in _stage_note(seq, "7")
    assert "Status: final" not in _stage_note(seq, "7")
    assert load_pointer(seq)["current"] == "7"
    assert "7" not in load_pointer(seq)["saved"]

    saved = essay_stage(seq, "7", "confirm", **picked(opened))
    assert saved["ok"] is True, saved
    assert saved["stored"] is True
    assert saved["current"] == "8"
    assert "7" in load_pointer(seq)["saved"]
    assert "8" not in load_pointer(seq)["saved"]
    assert "Status: final" in _stage_note(seq, "7")
