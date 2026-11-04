"""Live mid-office, same digest, dig confirm, diary cover, multi-miss, empty Confirm, and gates.

AC1: a live mid-office job refuses a second start for Cursor and for Build.
AC2: the same waiting stage digest returns that card and does not start another child.
AC3: a second dig confirm on the same query and look-up card does not write again.
AC4: Build covered. Cursor and Grok Build share the live-job guard.
AC5: a reflective diary cover prints the sequence id.
AC6: one refuse lists every current miss and names the house word.
AC7: Confirm with no waiting card does not advance and does not start file work.
AC8: an essay.gates failure records the gate code.
"""

from __future__ import annotations

import inspect
import json
import os
import shutil
from pathlib import Path

from helpers import ESSAY, open_sequence, picked

from essay_writer.build_status import finish_mid_process
from essay_writer.cursor_office import start_stage_mid
from essay_writer.debug_log import ml_events_path
from essay_writer.diary import diary_cover_lines
from essay_writer.dig import essay_dig
from essay_writer.paths import essay_dir, work_dir
from essay_writer.shells import front_office_call
from essay_writer.stage_track import essay_stage, load_pointer
from essay_writer.word import cover_lines

REPO = Path(__file__).resolve().parents[1]
GROK_LAUNCH = {"command": ["grok", "--print", "stage"], "settings": None}


def _alive(command):
    return {
        "started": True,
        "reason": "",
        "pid": os.getpid(),
        "command": list(command),
        "stdout": None,
    }


def _count(calls):
    def spawn(command):
        calls["n"] += 1
        return _alive(command)

    return spawn


def test_ac1_live_mid_office_refuses_second_start_for_cursor_and_build(workspace, monkeypatch):
    """AC1. A live job blocks the next start for Cursor and for Build."""
    calls = {"n": 0}
    monkeypatch.setattr("essay_writer.cursor_office.spawn_agent", _count(calls))
    monkeypatch.setattr("essay_writer.build_office.spawn_grok", _count(calls))
    seq = open_sequence()
    try:
        first = start_stage_mid(seq, "6")
        assert first["started"] is True
        assert first["shell"] == "cursor"
        assert calls["n"] == 1
        second = start_stage_mid(seq, "8", launch=GROK_LAUNCH)
        assert second["ok"] is True
        assert second["started"] is False
        assert second["reason"] == "mid-office-live"
        assert second["live"] is True
        assert second["status"] == []
        assert calls["n"] == 1
        finish_mid_process(seq)
        third = start_stage_mid(seq, "8", launch=GROK_LAUNCH)
        assert third["started"] is True
        assert third["shell"] == "grok"
        assert calls["n"] == 2
        fourth = start_stage_mid(seq, "6")
        assert fourth["started"] is False
        assert fourth["reason"] == "mid-office-live"
        assert fourth["shell"] == "grok"
        assert calls["n"] == 2
    finally:
        finish_mid_process(seq)


def test_ac2_same_stage_digest_returns_waiting_card_without_another_child(workspace, monkeypatch):
    """AC2. The same waiting digest returns the card and does not start another child."""
    calls = {"n": 0}
    monkeypatch.setattr("essay_writer.cursor_office.spawn_agent", _count(calls))
    seq = open_sequence()
    try:
        look = "Saved from the brief."
        for stage in ("1", "2", "3"):
            draft = essay_stage(seq, stage, "draft", look)
            assert draft["ok"] is True, draft
            saved = essay_stage(seq, stage, "confirm", look, **picked(draft))
            assert saved["stored"] is True, saved
        assert calls["n"] == 0
        mid = "One source is gathered."
        first = essay_stage(seq, "4a", "draft", mid)
        assert first["ok"] is True, first
        assert first.get("mid_started") is True
        assert calls["n"] == 1
        second = essay_stage(seq, "4a", "draft", mid)
        assert second["ok"] is True, second
        assert second["wrote"] is False
        assert second["digest"] == first["digest"]
        assert second["card"]["digest"] == first["digest"]
        assert second.get("mid_started") is not True
        assert "mid_office_launch" not in second
        assert calls["n"] == 1
    finally:
        finish_mid_process(seq)


def test_ac3_second_dig_confirm_is_a_noop(workspace, monkeypatch):
    """AC3. The second confirm of the same dig card does not write or download again."""
    fetched: list[str] = []

    def fake_json(url, headers=None):
        return {"results": []}

    def fake_fetch(url):
        fetched.append(url)
        return 200, "application/pdf", b"%PDF-1.4"

    monkeypatch.setattr("essay_writer.dig._get_json", fake_json)
    monkeypatch.setattr("essay_writer.downloads.fetch_url", fake_fetch)
    seq = open_sequence()
    query = "corridor chokepoints"
    draft = essay_dig(seq, query, "draft")
    assert draft["ok"] is True, draft
    assert draft["wrote"] is False
    first = essay_dig(seq, query, "confirm")
    assert first["wrote"] is True, first
    assert first["stored"] is True
    path = work_dir(seq) / "dig-card.json"
    raw = path.read_bytes()
    assert json.loads(raw)["digest"] == first["digest"]
    second = essay_dig(seq, query, "confirm")
    assert second["wrote"] is False
    assert second["stored"] is False
    assert second["noop"] is True
    assert path.read_bytes() == raw
    assert (work_dir(seq) / "dig-card.md").is_file()
    assert fetched == []


def test_ac4_build_covered_cursor_and_build_share_the_guards(workspace):
    """AC4. Build covered. One live-job check sits in front of both spawns."""
    source = inspect.getsource(start_stage_mid)
    assert source.count("live_mid_job(") == 1
    assert source.index("live_mid_job") < source.index("spawn_agent")
    assert source.index("live_mid_job") < source.index("spawn_grok")
    assert source.count("note_mid_office(") == 1
    build = (REPO / "src" / "essay_writer" / "build_office.py").read_text(encoding="utf-8")
    assert "live_mid_job" not in build
    assert "note_mid_office" not in build


def test_ac5_diary_cover_prints_the_sequence_id(workspace):
    """AC5. A reflective diary cover prints the sequence id. A report cover still does."""
    folder = essay_dir("RPT5001AA")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(
        "\n".join(
            [
                "Assignment title: Individual reflective diary",
                "Aim: Understand the practice by reflecting on your own decisions.",
                "Assignment task: Write four entries. Each entry names one decision and critically analyses it with theory and evidence.",
                "Title page: registration number.",
                "DO NOT include your name.",
            ]
        ),
        encoding="utf-8",
    )
    seq = open_sequence("RPT5001AA")
    pack = {
        "essay_id": seq,
        "title": "Workshop notes",
        "registration_number": "445566",
        "sections": [{"heading": "Quay watch", "body": "A decision in the workshop."}],
    }
    report = {"title": "Workshop notes", "word_count": {"counted": 6}, "sections": pack["sections"]}
    diary = diary_cover_lines(seq, pack, report)
    assert seq in diary
    assert cover_lines(seq, pack, report).count(seq) == 1
    report_folder = essay_dir(ESSAY)
    report_folder.mkdir(parents=True, exist_ok=True)
    (report_folder / "brief.md").write_text(
        "Format: report\nQuestion: How do chokepoints constrain the corridor?\n",
        encoding="utf-8",
    )
    report_seq = open_sequence()
    report_pack = {
        "essay_id": report_seq,
        "title": "Corridor report",
        "sections": [{"heading": "Draft", "body": "The corridor is narrow."}],
    }
    report_body = {
        "title": "Corridor report",
        "word_count": {"counted": 4},
        "sections": report_pack["sections"],
    }
    assert report_seq in cover_lines(report_seq, report_pack, report_body)


def test_ac6_multi_miss_refuse_lists_every_current_miss(workspace):
    """AC6. One reply names every current miss, including the house word."""
    folder = essay_dir(ESSAY)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(
        "Format: report\nQuestion: How do chokepoints constrain the corridor?\n",
        encoding="utf-8",
    )
    seq = open_sequence()
    reply = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "1",
            "confirmPhase": "draft",
            "look": "Confirm the pack before EQR.",
        },
    )
    assert reply["ok"] is False
    assert reply["refused"] == "house-jargon"
    assert reply.get("basics_seeded") is True
    assert reply["wrote"] is False
    assert reply.get("advanced") is not True
    assert reply["words"] == ["Confirm", "EQR", "pack"]
    assert "invent-forbid" not in reply["reason"].casefold()


def test_ac7_confirm_with_nothing_waiting_is_a_noop(workspace, monkeypatch):
    """AC7. Confirm with no card on disk does not advance and does not start file work."""
    calls = {"n": 0}
    monkeypatch.setattr("essay_writer.cursor_office.spawn_agent", _count(calls))
    monkeypatch.setattr("essay_writer.build_office.spawn_grok", _count(calls))
    seq = open_sequence()
    drafts = work_dir(seq) / ".drafts"
    if drafts.is_dir():
        shutil.rmtree(drafts)
    before = load_pointer(seq)
    reply = essay_stage(seq, "1", "confirm", "Confirm")
    assert reply["ok"] is True, reply
    assert reply["noop"] is True
    assert reply["wrote"] is False
    assert reply["stored"] is False
    assert reply["advanced"] is False
    assert "next" not in reply
    assert "mid_office_launch" not in reply
    assert calls["n"] == 0
    after = load_pointer(seq)
    assert after["current"] == before["current"]
    assert after["saved"] == before["saved"]


def test_ac8_gates_fail_event_includes_gate_code(workspace, monkeypatch):
    """AC8. A failed essay.gates outcome names the gate."""
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    seq = open_sequence()
    body = front_office_call("essay.gates", {"essay_id": seq})
    assert body["ok"] is False
    rows = [
        json.loads(line)
        for line in ml_events_path(seq).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    outcomes = [row for row in rows if row.get("kind") == "outcome" and row.get("tool") == "essay.gates"]
    assert outcomes
    assert outcomes[-1]["ok"] is False
    assert outcomes[-1]["gate"] == "brief"
