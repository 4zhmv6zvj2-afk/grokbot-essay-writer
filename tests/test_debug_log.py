"""Opt-in shell log. Off unless asked. Secrets stay out. Students are not shown it."""

import asyncio
import inspect
import json
import os
from pathlib import Path

from helpers import open_sequence

from essay_writer.debug_log import LOG_FILENAME, debug_enabled, debug_log_path, traced
from essay_writer.doors import DOORS
from essay_writer.ml_events import FILENAME as ML_EVENTS_FILENAME
from essay_writer.paths import workspace_root
from essay_writer.server import INSTRUCTIONS, build_review_server, build_server
from essay_writer.setup import essay_setup
from essay_writer.shells import front_office_call
from essay_writer.word import essay_pack_render_word

REPO = Path(__file__).resolve().parents[1]
KEY = "consensus-secret-value"
EMAIL = "reader@example.com"
TOKEN = "sk-live-secret-token-value"


def _log(workspace: Path) -> Path:
    return workspace / LOG_FILENAME


def test_debug_log_is_off_by_default(workspace, monkeypatch):
    monkeypatch.delenv("ESSAY_WRITER_DEBUG", raising=False)
    assert debug_enabled() is False
    report = front_office_call("essay.health", {})
    assert report["alive"] is True
    assert not _log(workspace).exists()
    assert debug_log_path() == workspace_root() / LOG_FILENAME


def test_explicit_off_beats_the_setup_record(workspace, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "0")
    monkeypatch.setattr("essay_writer.paths.load_saved_setup", lambda: {"debug": True})
    assert debug_enabled() is False
    front_office_call("essay.health", {})
    assert not _log(workspace).exists()
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "no")
    assert debug_enabled() is False


def test_setup_record_turns_the_log_on_when_the_env_is_unset(workspace, monkeypatch):
    monkeypatch.delenv("ESSAY_WRITER_DEBUG", raising=False)
    monkeypatch.setattr("essay_writer.paths.load_saved_setup", lambda: {"debug": True})
    assert debug_enabled() is True
    front_office_call("essay.health", {})
    text = _log(workspace).read_text(encoding="utf-8")
    assert "essay.health" in text
    assert "read" in text


def test_debug_log_on_writes_lines_for_delete_dig_and_setup(workspace, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    sequence = open_sequence()
    deleted = front_office_call(
        "essay.project.delete",
        {"module": "MOD1004AA", "confirmPhase": "draft"},
    )
    assert deleted["ok"] is True
    assert deleted["wrote"] is False
    dug = front_office_call(
        "essay.dig",
        {"essay_id": sequence, "query": "chokepoints", "confirmPhase": "draft"},
    )
    assert dug["ok"] is True
    assert dug["wrote"] is False
    prepared = front_office_call(
        "essay.setup",
        {
            "confirmPhase": "draft",
            "app_path": str(workspace / "app"),
            "kb1_path": str(workspace / "KB1"),
            "consensus_api_key": KEY,
            "unpaywall_email": EMAIL,
        },
    )
    assert prepared["wrote"] is False
    from essay_writer.debug_log import debug_log_path

    global_text = debug_log_path().read_text(encoding="utf-8") if debug_log_path().is_file() else ""
    seq_text = debug_log_path(sequence).read_text(encoding="utf-8") if debug_log_path(sequence).is_file() else ""
    text = f"{global_text}\n{seq_text}"
    assert "essay.project.delete" in text
    assert "draft" in text
    assert "MOD1004AA" in text
    assert "Where grokbot." in text
    assert "Nothing written." in text
    assert "essay.dig" in text
    assert sequence in text
    assert "Query chokepoints." in text
    assert "essay.setup" in text
    assert "Consensus key present." in text
    assert "Unpaywall email present." in text
    assert KEY not in text
    assert EMAIL not in text
    assert "debug.log" not in json.dumps(deleted)
    assert "debug.log" not in json.dumps(dug)
    assert "debug.log" not in json.dumps(prepared)


def test_secrets_are_redacted(workspace, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    monkeypatch.setenv("CONSENSUS_API_KEY", KEY)
    from essay_writer.debug_log import note_call

    note_call(
        "essay.setup",
        {
            "confirmPhase": "confirm",
            "consensus_api_key": KEY,
            "unpaywall_email": EMAIL,
            "authorization": f"Bearer {TOKEN}",
        },
        result={
            "ok": False,
            "refused": "setup",
            "reason": f"echo {KEY} and {EMAIL} and Bearer {TOKEN}",
            "wrote": False,
        },
    )

    def boom() -> None:
        raise RuntimeError(f"saw {KEY} and {TOKEN}")

    wrapped = traced("essay.health", boom)
    try:
        wrapped()
    except RuntimeError:
        pass
    else:
        raise AssertionError("the door error should still surface")
    text = _log(workspace).read_text(encoding="utf-8")
    assert KEY not in text
    assert EMAIL not in text
    assert TOKEN not in text
    assert "[redacted]" in text
    assert "Refused (setup)." in text
    assert "Failed (RuntimeError)." in text


def _no_consecutive_duplicate_lines(text: str) -> None:
    lines = [line for line in text.splitlines() if line.strip()]
    for left, right in zip(lines, lines[1:], strict=False):
        assert left != right


def test_mounted_door_logs_once_without_consecutive_duplicate(workspace, monkeypatch):
    """AC1. One MCP door call appends one prose line and one ML outcome, with no dupes."""
    import asyncio

    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    server = build_server()

    async def run():
        await server.call_tool("essay.health", {})

    asyncio.run(run())
    debug_text = _log(workspace).read_text(encoding="utf-8")
    prose = [line for line in debug_text.splitlines() if line.startswith("20") and " essay." in line]
    assert len(prose) == 1
    _no_consecutive_duplicate_lines(debug_text)

    ml_path = workspace / ML_EVENTS_FILENAME
    assert ml_path.is_file()
    ml_text = ml_path.read_text(encoding="utf-8")
    _no_consecutive_duplicate_lines(ml_text)
    outcomes = []
    for line in ml_text.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("tool") == "essay.health":
            outcomes.append(row)
    assert len(outcomes) == 1


def test_mounted_call_writes_a_line_and_keeps_the_door_arguments(workspace, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    server = build_server()
    reviewer = build_review_server()

    async def run():
        tools = await server.list_tools()
        health = await server.call_tool("essay.health", {})
        review = await reviewer.call_tool(
            "essay.review",
            {"essay_id": "MOD1004AA", "stage": "6", "verdict": "PASS", "confirmPhase": "draft"},
        )
        return tools, health, review

    tools, health, review = asyncio.run(run())
    setup = next(tool for tool in tools if tool.name == "essay.setup")
    assert "consensus_api_key" in setup.input_schema["properties"]
    assert "confirmPhase" in setup.input_schema["properties"]
    assert "consensus_api_key" in inspect.signature(essay_setup).parameters
    from essay_writer.paths import work_dir

    global_text = _log(workspace).read_text(encoding="utf-8") if _log(workspace).is_file() else ""
    review_log = work_dir("MOD1004AA") / LOG_FILENAME
    review_text = review_log.read_text(encoding="utf-8") if review_log.is_file() else ""
    text = f"{global_text}\n{review_text}"
    assert "essay.health read." in text
    assert "essay.review" in text
    health_text = health.content[0].text
    review_text = review.content[0].text
    assert "debug.log" not in health_text
    assert "debug.log" not in review_text
    assert "ESSAY_WRITER_DEBUG" not in health_text


def test_setup_keeps_an_operator_flag_out_of_the_reply(workspace, monkeypatch):
    monkeypatch.delenv("ESSAY_WRITER_DEBUG", raising=False)
    app = workspace / "app"
    kb1 = workspace / "KB1"
    draft = essay_setup(
        app_path=str(app), kb1_path=str(kb1), confirmPhase="draft", acknowledge_skipped_searches=True
    )
    assert draft["ok"] is True
    confirmed = essay_setup(
        app_path=str(app), kb1_path=str(kb1), confirmPhase="confirm", acknowledge_skipped_searches=True
    )
    assert confirmed["wrote"] is True
    record_path = workspace / "setup.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["debug"] = True
    record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    again = essay_setup(
        app_path=str(app), kb1_path=str(kb1), confirmPhase="draft", acknowledge_skipped_searches=True
    )
    saved = essay_setup(
        app_path=str(app), kb1_path=str(kb1), confirmPhase="confirm", acknowledge_skipped_searches=True
    )
    assert saved["wrote"] is True
    kept = json.loads(record_path.read_text(encoding="utf-8"))
    assert kept["debug"] is True
    reply = json.dumps(again) + json.dumps(saved)
    assert "debug" not in reply.casefold()
    assert "debug.log" not in reply
    assert not _log(workspace).exists()


def test_path_is_documented_for_operators_and_shells():
    note = (REPO / "docs" / "operator-log.md").read_text(encoding="utf-8")
    assert "debug.log" in note
    assert "ESSAY_WRITER_DEBUG" in note
    assert "Operators and shells use this file." in note
    assert "End users do not." in note
    assert "Students do not use it." in note
    assert "Cursor, and Grok Build" in note or "Essay Bot" in note
    assert "not shown in chat" in note
    assert "not written into Word" in note
    word = (REPO / "src" / "essay_writer" / "word.py").read_text(encoding="utf-8")
    assert "debug.log" not in word
    assert "debug_log" not in word
    assert "debug.log" not in INSTRUCTIONS
    assert all("debug.log" not in door["description"] for door in DOORS)
    assert "debug.log" not in inspect.getsource(essay_pack_render_word)
    assert LOG_FILENAME in (REPO / ".gitignore").read_text(encoding="utf-8")
    assert "Student installs leave it off." in note
    assert "grokbot-cloud-computer" in note
    assert "ESSAY_WRITER_OPERATOR_E2E" not in note
    assert "Avery" not in note
    assert "operator e2e" in note.casefold()


def test_student_install_stays_off_and_cloud_where_does_not_turn_the_log_on(workspace, monkeypatch):
    """Student where stays off. Cloud-computer where alone stays off. The operator flag still turns the log on."""
    monkeypatch.delenv("ESSAY_WRITER_DEBUG", raising=False)
    monkeypatch.delenv("ESSAY_WRITER_OPERATOR_E2E", raising=False)
    monkeypatch.setattr("essay_writer.paths.load_saved_setup", lambda: {"where": "user-local"})
    assert debug_enabled() is False
    front_office_call("essay.health", {})
    assert not _log(workspace).exists()

    monkeypatch.setattr(
        "essay_writer.paths.load_saved_setup",
        lambda: {"where": "grokbot-cloud-computer"},
    )
    assert debug_enabled() is False
    front_office_call("essay.health", {})
    assert not _log(workspace).exists()
    monkeypatch.setattr("essay_writer.paths.load_saved_setup", lambda: {"operator_e2e": True})
    assert debug_enabled() is True
    monkeypatch.setattr("essay_writer.paths.load_saved_setup", lambda: None)
    monkeypatch.setenv("ESSAY_WRITER_OPERATOR_E2E", "1")
    assert debug_enabled() is True
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "0")
    assert debug_enabled() is False
    front_office_call("essay.health", {})
    assert not _log(workspace).exists()


def test_health_reads_land_sha_from_dot_land_sha_file(workspace, monkeypatch, tmp_path):
    """AC5. essay.health names the pinned land SHA when .land-sha is present."""
    from essay_writer import debug_log

    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    pinned = "deadbeef" * 5
    monkeypatch.setattr(debug_log, "_install_root", lambda: tmp_path)
    monkeypatch.setattr(debug_log, "_land_sha_from_git", lambda: "")
    (tmp_path / ".land-sha").write_text(f"{pinned}\n", encoding="utf-8")
    prior = debug_log._LAND_SHA
    debug_log._LAND_SHA = None
    try:
        front_office_call("essay.health", {})
        text = _log(workspace).read_text(encoding="utf-8")
        assert f"Land {pinned} pid" in text
        assert "Land unknown" not in text
    finally:
        debug_log._LAND_SHA = prior


def test_health_and_confirm_lines_name_the_card_and_the_land(workspace, monkeypatch):
    """Health names land, pid, and tool count. Confirm names the card beside what would be posted."""
    import os
    import subprocess

    from essay_writer import debug_log

    debug_log._LAND_SHA = None
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    sequence = open_sequence()
    front_office_call("essay.health", {})
    draft = front_office_call(
        "essay.stage",
        {"essay_id": sequence, "stage": "1", "confirmPhase": "draft", "look": "The task is a short report."},
    )
    assert draft["ok"] is True, draft
    saved = front_office_call(
        "essay.stage",
        {
            "essay_id": sequence,
            "stage": "1",
            "confirmPhase": "confirm",
            "cardAction": "confirm",
            "cardDigest": draft["cardDigest"],
        },
    )
    assert saved["stored"] is True, saved
    from essay_writer.debug_log import debug_log_path

    global_text = debug_log_path().read_text(encoding="utf-8") if debug_log_path().is_file() else ""
    seq_text = debug_log_path(sequence).read_text(encoding="utf-8") if debug_log_path(sequence).is_file() else ""
    text = f"{global_text}\n{seq_text}"
    land = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    assert f"Land {land} pid {os.getpid()} tools {len(DOORS)}." in text
    assert f"Card digest {saved['cardDigest']}." in text
    assert "Card present." in text
    assert f"Posted {saved['card']['digest']}." in text
    assert "Confirm store yes advance yes next-card" in text
    assert "debug.log" not in json.dumps(saved)


def test_mid_office_logs_start_and_done_only_when_the_process_did(workspace, monkeypatch):
    """A missing CLI does not invent a start. A real start and a real exit name the shell."""
    from essay_writer.build_status import begin_mid_build, bind_job, finish_mid_process
    from essay_writer.cursor_office import start_stage_mid
    from essay_writer.debug_log import debug_log_path, note_mid_office

    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    sequence = open_sequence()
    def seq_log() -> Path:
        return debug_log_path(sequence)
    monkeypatch.setattr(
        "essay_writer.cursor_office.spawn_agent",
        lambda command: {"started": False, "reason": "agent-cli-missing", "command": command},
    )
    missed = start_stage_mid(sequence, "6")
    assert missed["started"] is False
    assert not seq_log().exists()

    monkeypatch.setattr(
        "essay_writer.cursor_office.spawn_agent",
        lambda command: {"started": True, "reason": "", "pid": os.getpid(), "command": command, "stdout": None},
    )
    started = start_stage_mid(sequence, "6")
    assert started["started"] is True
    text = seq_log().read_text(encoding="utf-8")
    assert "Mid-office start Cursor." in text
    assert "Mid-office start Build." not in text
    finish_mid_process(sequence)

    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: "grok_build")
    monkeypatch.setattr(
        "essay_writer.build_office.spawn_grok",
        lambda command: {"started": True, "reason": "", "pid": os.getpid(), "command": command, "stdout": None},
    )
    built = start_stage_mid(sequence, "8")
    assert built["started"] is True
    assert built["shell"] == "grok"
    text = seq_log().read_text(encoding="utf-8")
    assert "Mid-office start Build." in text

    note_mid_office("start", sequence, "neither")
    begin_mid_build(sequence, "work")
    bind_job(sequence, pid=os.getpid(), stage="6", shell="cursor")
    finish_mid_process(sequence)
    text = seq_log().read_text(encoding="utf-8")
    assert "Mid-office done Cursor." in text
    assert "neither" not in text
