"""Stage launch and status. Stable ids: AC1, AC2, AC3, AC4, AC5.

Stage 4a research starts the Cursor CLI. The front office does not run
that research. Status stays plain English and does not skip Confirm.
"""

import ast
import inspect
import subprocess
from pathlib import Path

import pytest
from helpers import ESSAY, open_sequence, picked

from essay_writer.build_office import stage_launch
from essay_writer.build_status import (
    _BANNED,
    HEARTBEAT_SECONDS,
    due_lines,
    heartbeat_sentence,
    milestone_sentence,
    note_milestone,
    reset_status,
    start_sentence,
)
from essay_writer.cursor_office import (
    REMOTE_CLOUD_BANNED,
    _resolved_launch,
    cursor_stage_launch,
    spawn_agent,
    stage_host_launch,
    start_4a_research,
    start_stage_mid,
)
from essay_writer.dig import essay_dig
from essay_writer.server import HANDLERS, REVIEW_HANDLERS
from essay_writer.setup import SHELL_GROK_BUILD
from essay_writer.shells import cursor_shell, front_office, front_office_call
from essay_writer.specialists import researcher
from essay_writer.specialists.grok_bot import front_office_call as grok_speak
from essay_writer.spine import advances_without_confirm, stage_uses_confirm_card
from essay_writer.stage_llm import stage_settings
from essay_writer.stage_track import _attach_mid_run, essay_stage, load_pointer

REPO = Path(__file__).resolve().parents[1]
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


def _plain(line: str) -> None:
    assert _BANNED.search(line) is None
    folded = line.casefold()
    for word in ("cli", "path", "review", "agent", "dig", "door", "watch"):
        assert word not in folded
    assert "http" not in folded
    assert "/" not in line


def _save_through(seq: str, look: str, stages: tuple[str, ...]) -> None:
    for stage in stages:
        draft = essay_stage(seq, stage, "draft", look)
        assert draft["ok"] is True, draft
        saved = essay_stage(seq, stage, "confirm", look, **picked(draft))
        assert saved["ok"] is True, saved


class _Proc:
    pid = 4242
    stdout = None


_REMOTE_COMMANDS = (
    ["cloud-agent"],
    ["cloud-agent", "--model", "grok-4.7-high"],
    ["agent", "--cloud"],
    ["agent", "--remote"],
    ["agent", "--cloud-agent"],
    ["agent", "https://cursor.com/agents/bc-1"],
    ["agent", "--model", "grok-4.7-high", "https://cursor.com/agents/bc-1"],
)


def test_ac1_stage_4a_launches_cursor_cli_not_the_front_office(
    requires_pty, workspace, monkeypatch
):
    """E2E #7. Local agent only. Remote and cloud agents are refused."""
    seen: list[list[str]] = []

    def fake_spawn(command):
        seen.append(list(command))
        return {"started": True, "reason": "", "pid": 7, "command": list(command)}

    monkeypatch.setattr("essay_writer.cursor_office.spawn_agent", fake_spawn)
    seq = open_sequence()
    look = "The task is a short report."
    _save_through(seq, look, ("1", "2", "3"))
    assert seen == []
    draft = essay_stage(seq, "4a", "draft", look)
    assert draft["ok"] is True, draft
    research = draft["mid_office_launch"]["research"]
    assert research["runner"] == "cursor-cli"
    assert research["command"] == ["agent", "--model", "grok-4.7-high"]
    assert research["command"] == cursor_stage_launch("4a")["command"]
    assert research["command"] == stage_host_launch("4a")["command"]
    assert research["command"][0] == "agent"
    assert "url" not in research
    assert "http" not in " ".join(research["command"])
    assert "cursor.com" not in " ".join(research["command"])
    launch_command = draft["mid_office_launch"]["command"]
    assert launch_command == ["agent", "--model", "grok-4.7-high"]
    assert "url" not in draft["mid_office_launch"]
    assert "cursor.com/agents" not in " ".join(launch_command)
    assert research["heartbeat_seconds"] == HEARTBEAT_SECONDS
    assert seen == [["agent", "--model", "grok-4.7-high"]]
    assert draft["card"]["kind"] == "confirm"
    spoken = front_office_call(
        "essay.stage",
        {"essay_id": seq, "stage": "4a", "confirmPhase": "draft", "look": look},
    )
    assert spoken["ok"] is True, spoken
    assert "mid_office_launch" not in spoken
    assert spoken["card"]["kind"] == "confirm"
    office = inspect.getsource(grok_speak)
    assert "subprocess" not in office
    assert "Popen" not in office
    assert "spawn_agent" not in office
    assert "essay_dig" not in office
    runner = "\n".join(
        inspect.getsource(fn)
        for fn in (start_4a_research, start_stage_mid, _resolved_launch, _attach_mid_run)
    )
    assert "start_stage_mid" in inspect.getsource(start_4a_research)
    assert "stage_host_launch" in runner
    assert "spawn_agent" in runner
    assert "spawn_grok" in runner
    assert "essay_dig" not in runner
    assert "essay.dig" not in runner
    assert "shell=True" not in runner
    assert "shell=True" not in inspect.getsource(spawn_agent)
    assert "start_4a_research" in inspect.getsource(_attach_mid_run)
    assert "_attach_mid_run" in inspect.getsource(essay_stage)
    spawn_source = inspect.getsource(spawn_agent)
    assert "CloudAgent" not in runner
    assert "CloudAgent" not in spawn_source
    assert spawn_source.index("REMOTE_CLOUD_BANNED") < spawn_source.index("open_mid_child(")
    office_source = Path(cursor_stage_launch.__code__.co_filename).read_text(encoding="utf-8")
    stage_source = inspect.getsource(essay_stage)
    assert "CloudAgent" not in office_source
    assert "CloudAgent" not in stage_source
    for command in _REMOTE_COMMANDS:
        refused = spawn_agent(command)
        assert refused["started"] is False
        assert refused["reason"] == REMOTE_CLOUD_BANNED
    kept = start_4a_research(
        seq,
        launch={
            "command": ["agent", "--cloud", "https://cursor.com/agents/bc-1"],
            "settings": stage_settings("4a"),
        },
    )
    assert kept["command"] == ["agent", "--model", "grok-4.7-high"]
    assert kept["reason"] != REMOTE_CLOUD_BANNED
    assert "url" not in kept
    assert "cursor.com" not in " ".join(kept["command"])

    monkeypatch.setattr("essay_writer.cursor_office.spawn_agent", spawn_agent)
    skipped = spawn_agent(["agent", "--model", "grok-4.7-high"])
    assert skipped["started"] is False
    assert skipped["reason"] == "skipped-under-test"

    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_GROK_BUILD)
    host = stage_host_launch("4a")
    assert host["command"][0] == "grok"
    switched = start_4a_research(seq)
    assert switched["command"][0] == "grok"
    assert switched["command"] == host["command"]
    assert switched["runner"] == "grok-build"
    assert switched["started"] is False
    assert switched["status"] == []
    assert switched["settings"] == stage_settings("4a")

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    popen_calls: list[tuple[list[str], dict]] = []

    def fake_popen(argv, **kwargs):
        popen_calls.append((list(argv), kwargs))
        return _Proc()

    monkeypatch.setattr("essay_writer.mid_spawn.subprocess.Popen", fake_popen)
    monkeypatch.setattr("essay_writer.setup.cursor_cli_binary", lambda: "/bin/agent")
    started = spawn_agent(["agent", "--model", "grok-4.7-high"])
    assert started["started"] is True
    assert started["pid"] == 4242
    argv, kwargs = popen_calls[0]
    assert argv == ["/bin/agent", "--model", "grok-4.7-high"]
    assert kwargs["shell"] is False
    assert kwargs["stdin"] not in (None, subprocess.DEVNULL)
    assert kwargs["stdout"] == kwargs["stdin"]
    assert kwargs["stderr"] is subprocess.PIPE
    monkeypatch.setattr("essay_writer.setup.cursor_cli_binary", lambda: None)
    missing = spawn_agent(["agent", "--model", "grok-4.7-high"])
    assert missing["started"] is False
    assert missing["reason"] == "agent-cli-missing"
    assert len(popen_calls) == 1
    for command in _REMOTE_COMMANDS:
        refused = spawn_agent(command)
        assert refused["started"] is False
        assert refused["reason"] == REMOTE_CLOUD_BANNED
    assert len(popen_calls) == 1


def test_ac2_essay_dig_stays_the_shared_handler(workspace, monkeypatch):
    """The look-up door stays one HANDLERS entry. The 4a chat path does not run it."""
    package = Path(essay_dig.__code__.co_filename).resolve().parent
    found = 0
    for path in package.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "essay_dig":
                found += 1
    assert found == 1
    server = (package / "server.py").read_text(encoding="utf-8")
    assert server.count("\nHANDLERS = {") == 1
    assert HANDLERS["essay.dig"] is essay_dig
    assert researcher.essay_dig is essay_dig
    assert cursor_shell()["handlers"] is HANDLERS
    assert front_office()["handlers"] is HANDLERS
    assert "essay.dig" not in REVIEW_HANDLERS
    calls = {"n": 0}
    original = HANDLERS["essay.dig"]

    def wrapped(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setitem(HANDLERS, "essay.dig", wrapped)
    seq = open_sequence()
    look = "The task is a short report."
    _save_through(seq, look, ("1", "2", "3"))
    draft = front_office_call(
        "essay.stage",
        {"essay_id": seq, "stage": "4a", "confirmPhase": "draft", "look": look},
    )
    assert draft["ok"] is True, draft
    assert calls["n"] == 0
    start_4a_research(seq)
    assert calls["n"] == 0
    assert "essay_dig" not in inspect.getsource(start_4a_research)
    assert "essay_dig" not in inspect.getsource(grok_speak)


def test_ac3_same_run_posts_start_milestone_and_heartbeat(workspace, monkeypatch):
    """E2E #11. Start, a real milestone, and the five-minute line. No watch card."""
    def _started(command):
        return {"started": True, "reason": "", "pid": 11, "command": list(command)}

    monkeypatch.setattr("essay_writer.cursor_office.spawn_agent", _started)
    clock = {"t": 0.0}
    monkeypatch.setattr("essay_writer.build_status._now", lambda: clock["t"])
    seq = open_sequence()
    brief = workspace / "Essay-writer" / ESSAY / "brief.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(f"Format: report\nQuestion: {QUESTION}\n", encoding="utf-8")
    run = start_4a_research(seq)
    assert HEARTBEAT_SECONDS == 300
    assert run["heartbeat_seconds"] == 300
    assert run["status"] == [start_sentence("gathering", QUESTION)]
    for line in run["status"]:
        _plain(line)
    assert QUESTION in run["status"][0]
    assert run.get("kind") != "watch"
    assert "url" not in run
    assert "watch" not in run
    gathered = note_milestone(seq, "sources")
    assert gathered == [milestone_sentence("sources", QUESTION)]
    assert start_sentence("gathering", QUESTION) not in gathered
    for line in gathered:
        _plain(line)
    annotated = note_milestone(seq, "annotation", activity="annotating")
    assert annotated == [milestone_sentence("annotation", QUESTION)]
    assert "annotated the sources" in annotated[0]
    _plain(annotated[0])
    clock["t"] = HEARTBEAT_SECONDS - 1
    assert due_lines(seq) == []
    clock["t"] = HEARTBEAT_SECONDS
    beat = due_lines(seq)
    assert beat == [heartbeat_sentence("annotating", QUESTION)]
    assert "still working" in beat[0]
    _plain(beat[0])
    assert run["runner"] == "cursor-cli"


def test_ac4_status_does_not_skip_basics_or_confirm(workspace, monkeypatch):
    """Status lines do not clear Basics or the assignment Confirm gate."""
    calls: list[list[str]] = []

    def fake_spawn(command):
        calls.append(list(command))
        return {"started": True, "reason": "", "pid": 11, "command": list(command)}

    monkeypatch.setattr("essay_writer.cursor_office.spawn_agent", fake_spawn)
    seq = open_sequence()
    brief = workspace / "Essay-writer" / ESSAY / "brief.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(f"Format: report\nQuestion: {QUESTION}\n", encoding="utf-8")
    _save_through(seq, LOOK, ("1", "2", "3"))
    assert calls == []
    assert advances_without_confirm("4a") is None
    assert stage_uses_confirm_card("4a") is True
    seeded = front_office_call(
        "essay.stage",
        {"essay_id": seq, "stage": "4a", "confirmPhase": "draft", "look": "hello"},
    )
    assert seeded["ok"] is True, seeded
    assert seeded.get("basics_seeded") is True
    assert seeded.get("stored") is not True
    assert seeded["status"] == [start_sentence("gathering", QUESTION)]
    for line in seeded["status"]:
        _plain(line)
    assert calls == [["agent", "--model", "grok-4.7-high"]]
    assert load_pointer(seq)["current"] == "4a"
    draft = front_office_call(
        "essay.stage",
        {"essay_id": seq, "stage": "4a", "confirmPhase": "draft", "look": LOOK},
    )
    assert draft["ok"] is True, draft
    assert draft["stored"] is False
    assert draft["card"]["kind"] == "confirm"
    assert draft["card"]["actions"][0]["label"] == "Confirm"
    assert draft["basics_pass"][2] == f"Question: {QUESTION}"
    assert "mid_office_launch" not in draft
    assert draft.get("kind") != "watch"
    assert len(calls) == 2 and all(
        entry == ["agent", "--model", "grok-4.7-high"] for entry in calls
    )
    assert "4a" not in load_pointer(seq)["saved"]
    typed = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "4a",
            "confirmPhase": "confirm",
            "look": LOOK,
            "cardAction": "yes",
            "cardDigest": draft["digest"],
        },
    )
    assert typed["ok"] is False
    assert typed["refused"] == "confirm-card"
    assert typed.get("stored") is not True
    assert "status" not in typed
    assert load_pointer(seq)["saved"] == ["1", "2", "3"]
    held = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "4a",
            "confirmPhase": "confirm",
            "look": LOOK,
            **picked(draft),
        },
    )
    assert held["ok"] is False
    assert held.get("advanced") is False
    assert held.get("stored") is not True
    assert load_pointer(seq)["current"] == "4a"
    assert len(calls) == 2 and all(
        entry == ["agent", "--model", "grok-4.7-high"] for entry in calls
    )


def test_ac5_build_covered_shared_handlers_and_stage_settings(monkeypatch):
    """Cursor and Grok Build share HANDLERS and the stage 4a settings row."""
    item = stage_settings("4a")
    cursor = cursor_stage_launch("4a")
    grok = stage_launch("4a")
    assert cursor["settings"] == item
    assert grok["settings"] == item
    assert cursor["settings"]["rules"] == grok["settings"]["rules"]
    assert cursor["settings"]["model"] == grok["settings"]["model"] == "grok-4.7"
    assert cursor["settings"]["reasoning"] == grok["settings"]["reasoning"] == "high"
    assert stage_host_launch("4a")["settings"] == item
    assert stage_host_launch("4a")["command"] == cursor["command"]
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_GROK_BUILD)
    hosted = stage_host_launch("4a")
    assert hosted["command"][0] == "grok"
    assert hosted["settings"] == item
    assert cursor_stage_launch("4a")["settings"] == item
    assert front_office()["handlers"] is HANDLERS
    assert cursor_shell()["handlers"] is HANDLERS
    assert HANDLERS["essay.dig"] is essay_dig
    office = Path(stage_launch.__code__.co_filename).read_text(encoding="utf-8")
    assert "HANDLERS" not in office
