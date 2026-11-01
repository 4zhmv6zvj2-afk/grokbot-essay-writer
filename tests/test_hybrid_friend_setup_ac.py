"""Hybrid friend setup. Stable ids: AC1, AC2, AC3."""

import json

from essay_writer.first_run import (
    _parse,
    attach_custom_mcp,
    first_run_prompt,
    install_uploaded_copy,
    package_root,
    recommended_mac_handoff_dir,
    remember_mac_handoff_dir,
)
from essay_writer.setup import CURSOR_SETUP_PROMPT, FIRST_RUN_MAC_SPEECH, SETUP_PROMPT


def test_ac1_default_install_attach_includes_essay_reviewer(tmp_path, monkeypatch):
    """AC1. Plain first_run attach merges essay-writer and essay-reviewer."""
    assert _parse([])["reviewer"] is True
    assert _parse(["--no-reviewer"])["reviewer"] is False

    project = tmp_path / "project"
    project.mkdir()
    enabled: list[str] = []

    def enable(name: str) -> dict:
        enabled.append(name)
        return {"identifier": name, "enabled": True}

    result = attach_custom_mcp(project, enable=enable)
    assert result["ok"] is True
    assert result["servers"] == ["essay-writer", "essay-reviewer"]
    assert enabled == ["essay-writer", "essay-reviewer"]
    config = json.loads((project / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
    assert "essay-reviewer" in config["mcpServers"]

    calls: list = []

    def runner(command, cwd):
        calls.append((command, cwd))
        return {"returncode": 0, "stdout": "", "stderr": ""}

    source = tmp_path / "tree"
    source.mkdir()
    (source / "pyproject.toml").write_text('[project]\nname = "essay-writer"\nversion = "0.1.0"\n', encoding="utf-8")
    installed = install_uploaded_copy(source, pip_runner=runner, enable=enable)
    assert installed["ok"] is True
    assert installed["mcp"]["servers"] == ["essay-writer", "essay-reviewer"]


def test_ac2_first_run_documents_mac_four_way_ask():
    """AC2. FIRST-RUN documents confirm, other path, later, and decline."""
    text = first_run_prompt()
    assert "Documents/Essay Bot" in text
    for phrase in ("confirm", "another path", "later", "decline"):
        assert phrase in text.casefold()
    assert "ESSAY_WRITER_MAC_DIR" in text
    assert "chat-only" in text.casefold() or "chat-only" in text
    assert FIRST_RUN_MAC_SPEECH in SETUP_PROMPT
    assert FIRST_RUN_MAC_SPEECH in CURSOR_SETUP_PROMPT


def test_ac3_friend_prompt_ships_and_readme_points_hybrid():
    """AC3. FRIEND-PROMPT ships. The README tells Grok Bot to read FIRST-RUN.txt."""
    root = package_root()
    packaged = root / "src" / "essay_writer" / "FRIEND-PROMPT.txt"
    assert (root / "FRIEND-PROMPT.txt").is_file()
    assert packaged.is_file()
    prompt = (root / "FRIEND-PROMPT.txt").read_text(encoding="utf-8")
    assert prompt == packaged.read_text(encoding="utf-8")
    assert "FIRST-RUN" in prompt
    assert "essay-reviewer" not in prompt.casefold()
    assert "mcp.json" not in prompt
    assert "python first_run" not in prompt
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "grokbot-essay-writer" in readme
    assert "FIRST-RUN.txt" in readme


def test_remember_mac_handoff_dir_uses_setup_secrets(tmp_path, monkeypatch):
    cloud = tmp_path / "workspace"
    cloud.mkdir()
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", cloud)
    monkeypatch.delenv("ESSAY_WRITER_MAC_DIR", raising=False)
    folder = tmp_path / "Documents" / "Essay Bot"
    remembered = remember_mac_handoff_dir(folder)
    assert remembered["ok"] is True
    assert recommended_mac_handoff_dir() is None or recommended_mac_handoff_dir().name == "Essay Bot"
    secret = cloud / "Essay-writer" / "setup.secrets.json"
    assert secret.is_file()
    data = json.loads(secret.read_text(encoding="utf-8"))
    assert data["ESSAY_WRITER_MAC_DIR"] == str(folder.resolve())
    monkeypatch.delenv("ESSAY_WRITER_MAC_DIR", raising=False)
