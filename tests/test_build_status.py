"""Mid-build progress: a start, a finished step, and a line about every five minutes."""

import json

import pytest
from helpers import ESSAY, open_sequence, picked, plant_gathered_source, write_upload

from essay_writer.build_office import stage_launch
from essay_writer.build_status import (
    HEARTBEAT_SECONDS,
    begin_mid_build,
    due_lines,
    heartbeat_sentence,
    launch_status,
    milestone_sentence,
    note_milestone,
    reply_status,
    reset_status,
    saved_pack_status,
    start_sentence,
)
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.shells import front_office_call

QUESTION = "How should Inditex manage its supply chain?"
LOOK = (
    "No mark scheme is on this module.\n"
    "Format: report.\n"
    f"Question: {QUESTION}\n"
    "This report asks how Inditex should manage its supply chain."
)


@pytest.fixture(autouse=True)
def _clear_status():
    reset_status()
    yield
    reset_status()


def _clock(monkeypatch, clock: dict[str, float]) -> None:
    monkeypatch.setattr("essay_writer.build_status._now", lambda: clock["t"])


def _plain(line: str) -> None:
    folded = line.casefold()
    assert "cli" not in folded
    assert "cursor" not in folded
    assert "grok" not in folded
    assert "path" not in folded
    assert "review" not in folded
    assert "heartbeat" not in folded
    assert "milestone" not in folded
    assert "http" not in folded
    assert "/" not in line
    assert "watch" not in folded


def test_clock_posts_a_start_then_a_line_every_five_minutes(monkeypatch):
    clock = {"t": 0.0}
    _clock(monkeypatch, clock)
    started = begin_mid_build("MOD1004AA-2", "gathering", subject="the Inditex question")
    assert started == [start_sentence("gathering", "the Inditex question")]
    assert "Inditex" in started[0]
    _plain(started[0])

    clock["t"] = HEARTBEAT_SECONDS - 1
    assert due_lines("MOD1004AA-2") == []
    clock["t"] = HEARTBEAT_SECONDS
    beat = due_lines("MOD1004AA-2")
    assert beat == [heartbeat_sentence("gathering", "the Inditex question")]
    assert "still working on the Inditex question" in beat[0]
    _plain(beat[0])

    clock["t"] = (HEARTBEAT_SECONDS * 2) - 1
    assert due_lines("MOD1004AA-2") == []
    clock["t"] = HEARTBEAT_SECONDS * 2
    assert due_lines("MOD1004AA-2") == []


def test_a_finished_step_resets_the_five_minute_gap(monkeypatch):
    clock = {"t": 0.0}
    _clock(monkeypatch, clock)
    begin_mid_build("MOD1004AA-2", "gathering", subject="the Inditex question")
    clock["t"] = 100
    done = note_finished()
    assert done == [milestone_sentence("annotation", "the Inditex question")]
    assert "annotated the sources for the Inditex question" in done[0]
    _plain(done[0])
    clock["t"] = 100 + HEARTBEAT_SECONDS - 1
    assert due_lines("MOD1004AA-2") == []
    clock["t"] = 100 + HEARTBEAT_SECONDS
    beat = due_lines("MOD1004AA-2")
    assert beat == [heartbeat_sentence("annotating", "the Inditex question")]
    assert "still working on the Inditex question" in beat[0]
    assert "Inditex" in beat[0]


def note_finished():
    from essay_writer.build_status import note_milestone

    return note_milestone("MOD1004AA-2", "annotation", activity="annotating")


def test_jargon_in_the_subject_stays_off_the_sentence():
    hostile = "Cursor CLI path /tmp/review"
    for line in (
        start_sentence("gathering", hostile),
        milestone_sentence("sources", hostile),
        heartbeat_sentence("drafting", hostile),
    ):
        _plain(line)
        assert line == "I am still working on your assignment." or "your assignment" in line
        assert "tmp" not in line.casefold()


def test_cursor_and_build_share_the_same_sentences(workspace):
    launch = stage_launch("4a")
    cursor = cursor_stage_launch("4a")
    assert launch["command"][0] == "grok"
    assert "--rules" in launch["command"]
    assert cursor["command"] == ["agent", "--model", "grok-4.7-high"]
    assert launch["status"] == launch_status("4a")
    assert cursor["status"] == launch["status"]
    assert "status" not in cursor_stage_launch("6")
    assert launch_status("4a") == [start_sentence("gathering", "your assignment")]
    assert launch_status("4b") == [start_sentence("notes", "your assignment")]
    assert launch_status("5") == [start_sentence("drafting", "your assignment")]
    assert launch_status("1") == []
    assert "status" not in stage_launch("6")
    assert "status" not in stage_launch("eqr")

    assert saved_pack_status("MOD1004AA-2") == []
    begin_mid_build("MOD1004AA-2", "gathering", subject="MOD1004AA-2")
    note_milestone("MOD1004AA-2", "sources")
    note_milestone("MOD1004AA-2", "annotation", activity="annotating")
    pack = saved_pack_status("MOD1004AA-2")
    assert start_sentence("gathering", "MOD1004AA-2") not in pack
    assert pack == [
        milestone_sentence("sources", "MOD1004AA-2"),
        milestone_sentence("annotation", "MOD1004AA-2"),
    ]

    reset_status()
    spoken = reply_status(
        "essay.stage",
        {"essay_id": "MOD1004AA-2", "stage": "4a", "confirmPhase": "draft"},
        {"ok": True, "essay_id": "MOD1004AA-2", "mid_started": True},
    )
    assert spoken == [start_sentence("gathering", "MOD1004AA-2")]
    assert spoken[0].startswith("I have started gathering sources for ")
    assert launch["status"][0].startswith("I have started gathering sources for ")

    ready = reply_status(
        "essay.stage",
        {
            "essay_id": "MOD1004AA-2",
            "stage": "5",
            "confirmPhase": "confirm",
            "look": "The first draft answers the question.",
        },
        {"ok": True, "stored": True, "essay_id": "MOD1004AA-2"},
    )
    assert ready == [milestone_sentence("draft", "MOD1004AA-2")]
    assert due_lines("MOD1004AA-2") == []

    reset_status()
    stored_draft = reply_status(
        "essay.stage",
        {
            "essay_id": "MOD1004AA-2",
            "stage": "5",
            "confirmPhase": "draft",
            "look": "The first draft answers the question.",
        },
        {"ok": True, "stored": True, "essay_id": "MOD1004AA-2", "started": {"stage": "6"}},
    )
    assert stored_draft == [milestone_sentence("draft", "MOD1004AA-2")]
    assert start_sentence("drafting", "MOD1004AA-2") not in stored_draft
    assert "card" not in stored_draft
    assert due_lines("MOD1004AA-2") == []
    assert all(isinstance(line, str) for line in spoken + ready + stored_draft + pack + launch["status"])


def test_front_office_posts_start_milestone_and_five_minute_line(workspace, monkeypatch):
    def _started(command):
        return {"started": True, "reason": "", "pid": 5, "command": list(command)}

    monkeypatch.setattr("essay_writer.cursor_office.spawn_agent", _started)
    clock = {"t": 0.0}
    _clock(monkeypatch, clock)
    write_upload(workspace)
    seq = open_sequence()
    brief = workspace / "Essay-writer" / ESSAY / "brief.md"
    brief.write_text(f"Format: report\nQuestion: {QUESTION}\n", encoding="utf-8")

    for stage in ("1", "2", "3"):
        draft = front_office_call(
            "essay.stage",
            {"essay_id": seq, "stage": stage, "confirmPhase": "draft", "look": LOOK},
        )
        assert draft["ok"] is True, draft
        assert "status" not in draft
        confirmed = front_office_call(
            "essay.stage",
            {
                "essay_id": seq,
                "stage": stage,
                "confirmPhase": "confirm",
                "look": LOOK,
                "cardAction": "confirm",
                "cardDigest": draft["digest"],
            },
        )
        assert confirmed["ok"] is True, confirmed
        assert "status" not in confirmed

    started = front_office_call(
        "essay.stage",
        {"essay_id": seq, "stage": "4a", "confirmPhase": "draft", "look": LOOK},
    )
    assert started["ok"] is True, started
    assert started["status"] == [start_sentence("gathering", QUESTION)]
    assert QUESTION in started["status"][0]
    for line in started["status"]:
        _plain(line)
    assert started.get("kind") != "watch"
    assert "url" not in started["status"][0]

    plant_gathered_source(seq)
    finished = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "4a",
            "confirmPhase": "confirm",
            "look": LOOK,
            "cardAction": "confirm",
            "cardDigest": started["digest"],
        },
    )
    assert finished["ok"] is True, finished
    assert finished["status"] == [f"{QUESTION} is saved."]
    assert "Open the Confirm card" not in " ".join(finished["status"])
    assert "gathered the sources" not in " ".join(finished["status"])
    assert "annotated the sources" not in " ".join(finished["status"])
    assert QUESTION in finished["status"][0]
    for line in finished["status"]:
        _plain(line)
    assert isinstance(finished.get("next"), str) and finished["next"].strip()

    clock["t"] = HEARTBEAT_SECONDS
    pulsed = front_office_call("essay.originals", {"essay_id": seq})
    assert pulsed["ok"] is True
    assert "status" not in pulsed


def test_stage5_draft_that_stores_says_the_first_draft_is_ready(workspace):
    write_upload(workspace)
    seq = open_sequence()
    brief = workspace / "Essay-writer" / ESSAY / "brief.md"
    brief.write_text(f"Format: report\nQuestion: {QUESTION}\n", encoding="utf-8")
    for stage in ("1", "2", "3", "4a", "4b"):
        draft = front_office_call(
            "essay.stage",
            {"essay_id": seq, "stage": stage, "confirmPhase": "draft", "look": LOOK},
        )
        assert draft["ok"] is True, draft
        assert "card" in draft
        if stage == "4a":
            plant_gathered_source(seq)
        saved = front_office_call(
            "essay.stage",
            {
                "essay_id": seq,
                "stage": stage,
                "confirmPhase": "confirm",
                "look": LOOK,
                **picked(draft),
            },
        )
        assert saved["ok"] is True, saved
        assert saved["stored"] is True

    done = front_office_call(
        "essay.stage",
        {"essay_id": seq, "stage": "5", "confirmPhase": "draft", "look": LOOK},
    )
    assert done["ok"] is True, done
    assert done["stored"] is True
    assert done["started"]["stage"] == "6"
    assert "card" not in done
    assert done["quiet"] is True
    assert done["status"] == [milestone_sentence("draft", QUESTION)]
    assert start_sentence("drafting", QUESTION) not in done["status"]
    assert "ready" in done["status"][-1]
    assert QUESTION in done["status"][-1]
    for line in done["status"]:
        _plain(line)
    assert due_lines(seq) == []

    refused = front_office_call(
        "essay.stage",
        {"essay_id": seq, "stage": "5", "confirmPhase": "confirm", "look": LOOK},
    )
    assert refused["ok"] is False
    assert "status" not in refused
    assert milestone_sentence("draft", QUESTION) not in json.dumps(refused)
