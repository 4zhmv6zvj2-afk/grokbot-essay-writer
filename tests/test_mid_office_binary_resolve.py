"""Mid-office spawn resolves CLI binaries via setup helpers, not PATH-only which."""

import subprocess
from pathlib import Path

from essay_writer.build_office import spawn_grok
from essay_writer.cursor_office import REMOTE_CLOUD_BANNED, spawn_agent
from essay_writer.setup import cursor_cli_binary, grokbuild_binary


class _Proc:
    pid = 4242

    def __init__(self):
        self.stdout = None


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


def test_spawn_agent_uses_resolved_home_binary(requires_pty, monkeypatch, tmp_path):
    _thin_path(monkeypatch)
    agent = _home_with_binary(monkeypatch, tmp_path, ".local/bin/agent")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    popen_calls: list[list[str]] = []

    def fake_popen(argv, **kwargs):
        popen_calls.append(list(argv))
        return _Proc()

    monkeypatch.setattr("essay_writer.mid_spawn.subprocess.Popen", fake_popen)
    started = spawn_agent(["agent", "--model", "grok-4.7-high"])
    assert started["started"] is True
    assert popen_calls == [[str(agent), "--model", "grok-4.7-high"]]


def test_spawn_grok_uses_resolved_home_binary(requires_pty, monkeypatch, tmp_path):
    _thin_path(monkeypatch)
    grok = _home_with_binary(monkeypatch, tmp_path, ".grok/bin/grok")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    popen_calls: list[list[str]] = []

    def fake_popen(argv, **kwargs):
        popen_calls.append(list(argv))
        return _Proc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    started = spawn_grok(["grok", "--model", "grok-4.7", "--effort", "high"])
    assert started["started"] is True
    assert popen_calls == [[str(grok), "--model", "grok-4.7", "--effort", "high"]]


def test_spawn_missing_only_when_no_candidate(monkeypatch, tmp_path):
    _thin_path(monkeypatch)
    home = tmp_path / "empty-home"
    home.mkdir()
    monkeypatch.setattr("essay_writer.setup.Path.home", lambda: home)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    missing_agent = spawn_agent(["agent", "--model", "grok-4.7-high"])
    assert missing_agent["started"] is False
    assert missing_agent["reason"] == "agent-cli-missing"
    missing_grok = spawn_grok(["grok", "--model", "grok-4.7", "--effort", "high"])
    assert missing_grok["started"] is False
    assert missing_grok["reason"] == "grok-cli-missing"


def test_spawn_still_refuses_remote_cloud_and_pytest(monkeypatch):
    refused = spawn_agent(["agent", "--cloud", "https://cursor.com/agents/x"])
    assert refused["started"] is False
    assert refused["reason"] == REMOTE_CLOUD_BANNED
    skipped = spawn_agent(["agent", "--model", "grok-4.7-high"])
    assert skipped["started"] is False
    assert skipped["reason"] == "skipped-under-test"
    skipped_grok = spawn_grok(["grok", "--model", "grok-4.7", "--effort", "high"])
    assert skipped_grok["started"] is False
    assert skipped_grok["reason"] == "skipped-under-test"


def test_spawn_helpers_use_setup_resolvers():
    import inspect

    agent_src = inspect.getsource(spawn_agent)
    grok_src = inspect.getsource(spawn_grok)
    assert "cursor_cli_binary" in agent_src
    assert "shutil.which" not in agent_src
    assert "grokbuild_binary" in grok_src
    assert "shutil.which" not in grok_src
