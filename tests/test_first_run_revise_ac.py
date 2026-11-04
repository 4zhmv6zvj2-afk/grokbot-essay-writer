"""First-run revise: install the Cursor agent when it is missing, and keep operator steps out of the friend paste."""

import ast

from essay_writer.doors import DOORS
from essay_writer.first_run import (
    CURSOR_AGENT_INSTALL,
    _parse,
    enable_mcp_server,
    ensure_cursor_agent,
    first_run_prompt,
    install_uploaded_copy,
    package_root,
    write_bot_share,
)
from essay_writer.setup import (
    CURSOR_SETUP_PROMPT,
    SHELL_CURSOR,
    _file_work_report,
)

LOGIN_CARD = (
    "I'll sign in to Cursor on my computer. Open my computer and take over. "
    "On that screen, choose Allow or Continue. If Google appears, pick the Google account "
    "for this Cursor account. Tell me when you're signed in."
)
HOST_HANDOFF = "Open computer → Take over → I'm done"
GROK_BUILD_SKIP = (
    "When they explicitly choose Grok Build and grok version works, skip Cursor login. "
    "If grok is missing, stay on Cursor"
)
OLD_LOGIN_WINDOW = "A window will ask you to sign in to Cursor"
MAC_CARD = "Word copies go to Documents/Essay Bot — OK, another folder, later, or skip."
CONSENSUS_CARD = "Open Consensus → API keys → New key → paste once on the secret card. Ask Free or Pro."


def _both(name: str) -> tuple[str, str]:
    root = package_root()
    packaged = root / "src" / "essay_writer" / name
    disk = (root / name).read_text(encoding="utf-8")
    copy = packaged.read_text(encoding="utf-8")
    assert disk == copy
    return disk, copy


def test_ac1_first_run_installs_agent_on_grok_bot_computer_only():
    """AC1. Both FIRST-RUN copies install agent when missing. Mac and grok stay uninstalled."""
    text, _copy = _both("FIRST-RUN.txt")
    assert text == first_run_prompt()
    assert CURSOR_AGENT_INSTALL in text
    assert "agent --version" in text
    assert "agent mcp enable essay-writer" in text
    assert "agent mcp enable essay-reviewer" in text
    assert "Never install the Cursor CLI on the Mac." in text
    assert "Never install grok." in text
    assert "If grok is missing, stay on Cursor." in text
    assert "Do not install the Cursor CLI" not in text
    assert "On this computer" in text


def test_ac2_friend_prompt_stays_short_and_names_the_chat():
    """AC2. FRIEND-PROMPT names Essay Bot, Cursor, Build, and agent install, and omits operator filenames."""
    text, _copy = _both("FRIEND-PROMPT.txt")
    assert "Essay Bot" in text
    assert "defaults to Cursor" in text
    assert "Grok Build" in text
    assert "prefer" in text.casefold()
    assert "missing" in text.casefold()
    assert "install" in text.casefold()
    assert "FIRST-RUN" in text
    assert "python" not in text.casefold()
    assert "mcp" not in text.casefold()
    assert "CreateBotShareJson" not in text
    assert "essay-reviewer" not in text.casefold()


def test_ac3_installer_runs_only_when_agent_is_absent(monkeypatch):
    """AC3. Fake installer only when agent is absent. Version is required before enable. Never grok. Setup does not install."""
    monkeypatch.setattr("essay_writer.first_run._on_mac", lambda: False)
    calls: list[str] = []
    state = {"binary": None, "version": None}

    def binary():
        return state["binary"]

    def version(_path):
        return state["version"]

    def fake():
        calls.append(CURSOR_AGENT_INSTALL)
        state["binary"] = "/opt/agent"
        state["version"] = "agent 1.2.3"
        return {"returncode": 0, "stdout": "", "stderr": ""}

    monkeypatch.setattr("essay_writer.setup.cursor_cli_binary", binary)
    monkeypatch.setattr("essay_writer.setup.cursor_cli_version", version)
    monkeypatch.setattr(
        "essay_writer.first_run.subprocess.run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("grok or curl must not run here")),
    )

    missing = ensure_cursor_agent(installer=fake)
    assert calls == [CURSOR_AGENT_INSTALL]
    assert missing["ran_install"] is True
    assert missing["ok"] is True
    assert missing["version"] == "agent 1.2.3"
    assert "grok" not in CURSOR_AGENT_INSTALL

    calls.clear()
    present = ensure_cursor_agent(installer=fake)
    assert calls == []
    assert present["ran_install"] is False

    state["binary"] = None
    state["version"] = None
    monkeypatch.setattr("essay_writer.first_run._on_mac", lambda: True)
    mac = ensure_cursor_agent(installer=fake)
    assert calls == []
    assert mac["ran_install"] is False
    assert mac["reason"] == "mac-no-install"

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    state["binary"] = "/opt/agent"
    state["version"] = None
    blocked = enable_mcp_server("essay-writer")
    assert blocked["enabled"] is False
    assert blocked["reason"] == "agent-version-missing"

    report = _file_work_report(SHELL_CURSOR, "cloud")
    assert report["cursor_cli"]["ran_install"] is False
    assert report["grokbuild"]["ran_install"] is False
    assert "Do not install the Cursor CLI" not in CURSOR_SETUP_PROMPT
    assert "Do not install grok." in CURSOR_SETUP_PROMPT
    assert "never installs on the Mac" in CURSOR_SETUP_PROMPT
    assert LOGIN_CARD in CURSOR_SETUP_PROMPT
    assert HOST_HANDOFF in CURSOR_SETUP_PROMPT
    assert "Wait for that yes before essay.setup confirm" in CURSOR_SETUP_PROMPT
    assert OLD_LOGIN_WINDOW not in CURSOR_SETUP_PROMPT
    setup = next(door["description"] for door in DOORS if door["tool"] == "essay.setup")
    assert "Do not install the Cursor CLI" not in setup
    assert "does not install grok" in setup
    assert "does not install on the Mac" in setup


def test_ac3_install_uploaded_copy_uses_the_same_installer(tmp_path, monkeypatch):
    """The first-run install path calls the installer only when agent is absent."""
    monkeypatch.setattr("essay_writer.first_run._on_mac", lambda: False)
    calls: list[int] = []
    state = {"binary": None}

    def binary():
        return state["binary"]

    def fake():
        calls.append(1)
        state["binary"] = "/opt/agent"
        return {"returncode": 0}

    monkeypatch.setattr("essay_writer.setup.cursor_cli_binary", binary)
    monkeypatch.setattr("essay_writer.setup.cursor_cli_version", lambda _path: "agent 1.2.3")
    source = tmp_path / "tree"
    source.mkdir()
    (source / "pyproject.toml").write_text('[project]\nname = "essay-writer"\nversion = "0.1.0"\n', encoding="utf-8")

    def runner(_command, _cwd):
        return {"returncode": 0, "stdout": "", "stderr": ""}

    installed = install_uploaded_copy(
        source,
        pip_runner=runner,
        attach=False,
        cursor_installer=fake,
    )
    assert installed["ok"] is True
    assert calls == [1]
    assert installed["cursor_cli"]["ran_install"] is True

    calls.clear()
    again = install_uploaded_copy(
        source,
        pip_runner=runner,
        attach=False,
        cursor_installer=fake,
    )
    assert calls == []
    assert again["cursor_cli"]["ran_install"] is False


def test_ac4_enable_uses_home_agent_off_path(monkeypatch, tmp_path):
    """AC4. mcp enable uses ~/.local/bin/agent when that directory is off PATH."""
    home = tmp_path / "home"
    agent = home / ".local" / "bin" / "agent"
    agent.parent.mkdir(parents=True)
    agent.write_text("#!/bin/sh\necho agent-test-version\n", encoding="utf-8")
    agent.chmod(0o755)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setattr("essay_writer.setup.shutil.which", lambda _name: None)
    monkeypatch.setattr("essay_writer.setup.Path.home", lambda: home)
    monkeypatch.setattr("essay_writer.setup.cursor_cli_version", lambda _path: "agent-test-version")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    ran: list[list[str]] = []

    def fake_run(argv, **_kwargs):
        ran.append(list(argv))

        class Completed:
            returncode = 0
            stdout = ""
            stderr = ""

        return Completed()

    monkeypatch.setattr("essay_writer.first_run.subprocess.run", fake_run)

    writer = enable_mcp_server("essay-writer")
    reviewer = enable_mcp_server("essay-reviewer")
    assert writer["enabled"] is True
    assert writer["returncode"] == 0
    assert reviewer["enabled"] is True
    assert ran == [
        [str(agent), "mcp", "enable", "essay-writer"],
        [str(agent), "mcp", "enable", "essay-reviewer"],
    ]


def test_ac5_share_file_is_written_and_the_host_tool_is_not_called(tmp_path):
    """AC5. FIRST-RUN writes the share file only; host publish stays operator-only."""
    text, _copy = _both("FIRST-RUN.txt")
    assert "The package only writes that file." in text
    assert "host publishing stays operator-only" in text
    assert "Do not narrate MCP attach to the friend." in text
    assert "CreateBotShareJson" not in text

    project = tmp_path / "project"
    project.mkdir()
    share = write_bot_share(project)
    assert share.name == "essay-bot.share.json"
    assert share.parent.name == ".grok"
    body = share.read_text(encoding="utf-8")
    assert "CreateBotShareJson" not in body

    root = package_root() / "src" / "essay_writer"
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
                assert name != "CreateBotShareJson"


def test_ac6_reviewer_mac_four_way_and_secret_skip_stay():
    """AC6. Reviewer stays on, the Mac four-way ask stays, and the secret skip warning stays."""
    assert _parse([])["reviewer"] is True
    text = first_run_prompt()
    assert "essay-reviewer" in text
    assert "--no-reviewer" in text
    for phrase in ("confirm", "another path", "later", "decline"):
        assert phrase in text.casefold()
    assert "ESSAY_WRITER_MAC_DIR" in text
    assert "chat-only" in text.casefold()
    assert "Ordinary setup collects the Consensus key" in text
    assert "setup secret card" in text
    assert "show the warning before the skip is accepted" in text
    assert "acknowledge_skipped_searches" in text


def test_login_consensus_and_mac_cards_are_in_both_prompts():
    """Takeover login card, host handoff, skip, Grok Build skip, Consensus, Mac."""
    first, _packaged = _both("FIRST-RUN.txt")
    friend, _friend_copy = _both("FRIEND-PROMPT.txt")
    for text in (first, friend):
        assert LOGIN_CARD in text
        assert HOST_HANDOFF in text
        assert OLD_LOGIN_WINDOW not in text
        assert "Wait for that yes before" in text
        assert "setup confirm" in text
        assert "agent status" in text
        assert "CURSOR_API_KEY is already on the machine" in text
        assert "Do not put a key in chat." in text
        assert "Do not put a login URL in chat." in text
        assert GROK_BUILD_SKIP in text
        assert MAC_CARD in text
        assert CONSENSUS_CARD in text
    assert "before essay.setup confirm" in first
    assert "run agent login while the person holds that desktop" in first
    assert "run agent status before essay.setup confirm" in first
    assert "use the same cursor account as essay bot" in first.casefold()
    assert "CreateBotShareJson" not in friend
    assert "mcp" not in friend.casefold()
