"""Mid-office spawn resolves CLI binaries via setup helpers, not PATH-only which.

The opener is injected through `launch`, so these tests run the real spawn
branch with a fake binary and a fake launcher. No Cursor or Grok CLI starts.
"""

from pathlib import Path

from essay_writer.build_office import spawn_grok
from essay_writer.cursor_office import REMOTE_CLOUD_BANNED, spawn_agent
from essay_writer.setup import cursor_cli_binary, grokbuild_binary


class _Proc:
    pid = 4242

    def __init__(self):
        self.stdout = None


class _Launcher:
    """Record the argv the real spawn branch hands to the opener."""

    def __init__(self):
        self.calls: list[list[str]] = []

    def __call__(self, argv):
        self.calls.append(list(argv))
        return _Proc(), None


def _thin_path(monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setattr(
        "essay_writer.setup.shutil.which",
        lambda _name: None,
    )


def _home_with_binary(monkeypatch, tmp_path: Path, rel: str) -> Path:
    home = tmp_path / "home"
    binary = home.joinpath(*rel.split("/"))
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)
    monkeypatch.setattr("essay_writer.setup.Path.home", lambda: home)
    return binary


def test_cursor_cli_binary_finds_home_when_path_thin(monkeypatch, tmp_path):
    _thin_path(monkeypatch)
    agent = _home_with_binary(monkeypatch, tmp_path, ".local/bin/agent")
    assert cursor_cli_binary() == str(agent)


def test_grokbuild_binary_finds_home_when_path_thin(monkeypatch, tmp_path):
    _thin_path(monkeypatch)
    grok = _home_with_binary(monkeypatch, tmp_path, ".local/bin/grok")
    assert grokbuild_binary() == str(grok)


def test_spawn_agent_uses_resolved_home_binary(monkeypatch, tmp_path):
    _thin_path(monkeypatch)
    agent = _home_with_binary(monkeypatch, tmp_path, ".local/bin/agent")
    launch = _Launcher()
    started = spawn_agent(["agent", "--model", "grok-4.7-high"], launch=launch)
    assert started["started"] is True
    assert started["pid"] == 4242
    assert started["stdout"] is None
    assert launch.calls == [[str(agent), "--model", "grok-4.7-high"]]


def test_spawn_grok_uses_resolved_home_binary(monkeypatch, tmp_path):
    _thin_path(monkeypatch)
    grok = _home_with_binary(monkeypatch, tmp_path, ".grok/bin/grok")
    launch = _Launcher()
    started = spawn_grok(["grok", "--model", "grok-4.7", "--effort", "high"], launch=launch)
    assert started["started"] is True
    assert started["pid"] == 4242
    assert launch.calls == [[str(grok), "--model", "grok-4.7", "--effort", "high"]]


def test_spawn_missing_only_when_no_candidate(monkeypatch, tmp_path):
    _thin_path(monkeypatch)
    home = tmp_path / "empty-home"
    home.mkdir()
    monkeypatch.setattr("essay_writer.setup.Path.home", lambda: home)
    launch = _Launcher()
    missing_agent = spawn_agent(["agent", "--model", "grok-4.7-high"], launch=launch)
    assert missing_agent["started"] is False
    assert missing_agent["reason"] == "agent-cli-missing"
    missing_grok = spawn_grok(["grok", "--model", "grok-4.7", "--effort", "high"], launch=launch)
    assert missing_grok["started"] is False
    assert missing_grok["reason"] == "grok-cli-missing"
    assert launch.calls == []


def test_spawn_runs_in_pytest_without_an_env_branch(monkeypatch):
    """The real branch runs here. No PYTEST_CURRENT_TEST short-circuit exists."""
    monkeypatch.setattr("essay_writer.setup.cursor_cli_binary", lambda: "/bin/agent")
    monkeypatch.setattr("essay_writer.setup.grokbuild_binary", lambda: "/bin/grok")
    agent_launch = _Launcher()
    grok_launch = _Launcher()
    agent = spawn_agent(["agent", "--model", "grok-4.7-high"], launch=agent_launch)
    grok = spawn_grok(["grok", "--model", "grok-4.7"], launch=grok_launch)
    assert agent["started"] is True
    assert grok["started"] is True
    assert agent_launch.calls == [["/bin/agent", "--model", "grok-4.7-high"]]
    assert grok_launch.calls == [["/bin/grok", "--model", "grok-4.7"]]


def test_spawn_refuses_remote_cloud_before_binary_or_launch(monkeypatch):
    launch = _Launcher()
    for command in (
        ["agent", "--cloud", "https://cursor.com/agents/x"],
        ["agent", "--remote"],
        ["agent", "https://cursor.com/agents/bc-1"],
    ):
        refused = spawn_agent(command, launch=launch)
        assert refused["started"] is False
        assert refused["reason"] == REMOTE_CLOUD_BANNED
        assert refused["command"] == command
    for command in (["grok", "--cloud"], ["grok", "--remote"]):
        refused_grok = spawn_grok(command, launch=launch)
        assert refused_grok["started"] is False
        assert refused_grok["reason"] == "not-grok-build"
    assert launch.calls == []


def test_spawn_launch_oserror_is_a_missing_tool(monkeypatch):
    monkeypatch.setattr("essay_writer.setup.cursor_cli_binary", lambda: "/bin/agent")
    monkeypatch.setattr("essay_writer.setup.grokbuild_binary", lambda: "/bin/grok")

    def no_terminal(_argv):
        raise OSError("openpty: out of pty devices")

    missing_agent = spawn_agent(["agent", "--model", "grok-4.7-high"], launch=no_terminal)
    missing_grok = spawn_grok(["grok", "--model", "grok-4.7"], launch=no_terminal)
    assert missing_agent["reason"] == "agent-cli-missing"
    assert missing_grok["reason"] == "grok-cli-missing"


def test_spawn_helpers_use_setup_resolvers_and_real_opener():
    import inspect

    agent_src = inspect.getsource(spawn_agent)
    grok_src = inspect.getsource(spawn_grok)
    assert "cursor_cli_binary" in agent_src
    assert "shutil.which" not in agent_src
    assert "open_mid_child" in agent_src
    assert "grokbuild_binary" in grok_src
    assert "shutil.which" not in grok_src
    assert "open_mid_child" in grok_src
