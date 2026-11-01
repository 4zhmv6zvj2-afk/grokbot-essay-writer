"""Mac canonical path and install self-check. Stable ids: AC1–AC7."""

import inspect
import json

from essay_writer.build_office import build_deliverable_handoff
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.first_run import (
    UPGRADE_REREAD_MARKER,
    UPGRADE_REREAD_SPEECH,
    attach_friend_upgrade_fo_card,
    choose_mac_handoff,
    copy_deliverable_to_mac,
    first_run_prompt,
    install_self_check,
    install_uploaded_copy,
    main,
    package_root,
    visible_canonical_mac_handoff_dir,
)
from essay_writer.setup import CURSOR_SETUP_PROMPT, FIRST_RUN_MAC_SPEECH, SETUP_PROMPT

MAC_CARD = "Word copies go to Documents/Essay Bot — OK, another folder, later, or skip."


def _bot_and_mac(tmp_path, monkeypatch):
    linux = tmp_path / "grok-bot-home"
    linux.mkdir()
    mac = tmp_path / "Users" / "friend"
    mac.mkdir(parents=True)
    cloud = tmp_path / "workspace"
    cloud.mkdir()
    monkeypatch.setattr("essay_writer.first_run._on_mac", lambda: False)
    monkeypatch.setattr("essay_writer.first_run._process_home", lambda: linux)
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", cloud)
    monkeypatch.setenv("ESSAY_WRITER_MAC_HOME", str(mac))
    monkeypatch.delenv("ESSAY_WRITER_MAC_DIR", raising=False)
    return linux, mac, cloud


def test_ac1_canonical_essay_bot_handoff_without_remember(tmp_path, monkeypatch):
    """AC1. Visible Documents/Essay Bot is used for copy without --remember-mac-dir."""
    linux, mac, cloud = _bot_and_mac(tmp_path, monkeypatch)
    folder = mac / "Documents" / "Essay Bot"
    folder.mkdir(parents=True)
    source = tmp_path / "essay.docx"
    source.write_bytes(b"word-bytes")
    assert visible_canonical_mac_handoff_dir() == folder
    copied = copy_deliverable_to_mac(source)
    assert copied["ok"] is True
    assert copied["copied"] is True
    assert (folder / "essay.docx").read_bytes() == b"word-bytes"
    assert source.read_bytes() == b"word-bytes"
    assert not (linux / "Documents").exists()
    secret = cloud / "Essay-writer" / "setup.secrets.json"
    assert not secret.exists()


def test_ac2_unmounted_leaves_mac_file_and_returns_mac_not_mounted(tmp_path, monkeypatch):
    """AC2. Unmounted copy returns mac-not-mounted and leaves the source file alone."""
    linux, mac, _cloud = _bot_and_mac(tmp_path, monkeypatch)
    monkeypatch.delenv("ESSAY_WRITER_MAC_HOME", raising=False)
    source = tmp_path / "essay.docx"
    source.write_bytes(b"keep-me")
    missing = copy_deliverable_to_mac(source)
    assert missing["copied"] is False
    assert missing["reason"] == "mac-not-mounted"
    assert "residual" in missing
    assert "mac-not-mounted" in missing["reason"]
    assert source.read_bytes() == b"keep-me"
    assert not (mac / "Documents").exists()
    assert not (linux / "Documents").exists()


def test_ac3_four_way_card_still_required_for_setup():
    """AC3. Four-way Mac card stays on first-run and setup prompts (card still required)."""
    text = first_run_prompt()
    assert MAC_CARD in text or "OK, another folder, later, or skip" in text
    for prompt in (text, SETUP_PROMPT, CURSOR_SETUP_PROMPT, FIRST_RUN_MAC_SPEECH):
        assert "OK, another folder, later, or skip" in prompt
    assert "choose_mac_handoff" in FIRST_RUN_MAC_SPEECH
    for fn in (cursor_stage_launch,):
        source = inspect.getsource(fn)
        assert "choose_mac_handoff" not in source


def test_ac4_build_office_shares_canonical_mac_handoff(tmp_path, monkeypatch):
    """AC4. Grok Build handoff uses the same copy_deliverable_to_mac canonical path."""
    _linux, mac, _cloud = _bot_and_mac(tmp_path, monkeypatch)
    folder = mac / "Documents" / "Essay Bot"
    folder.mkdir(parents=True)
    source = tmp_path / "papers.zip"
    source.write_bytes(b"zip-bytes")
    result = build_deliverable_handoff(source)
    assert result.get("copied") is True
    assert (folder / "papers.zip").read_bytes() == b"zip-bytes"


def test_ac5_install_self_checks_essay_health(tmp_path):
    """AC5. Friend zip install self-checks essay.health after pip and attach."""
    source = tmp_path / "tree"
    source.mkdir()
    (source / "pyproject.toml").write_text(
        '[project]\nname = "essay-writer"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )

    def pip_ok(command, cwd):
        return {"returncode": 0, "stdout": "", "stderr": ""}

    installed = install_uploaded_copy(source, pip_runner=pip_ok, attach=False)
    assert installed["ok"] is True
    check = installed["health_check"]
    assert check["ok"] is True
    assert check["tool"] == "essay.health"
    assert check["tool_count"] > 0
    assert installed["fo_card"] == UPGRADE_REREAD_SPEECH
    assert install_self_check()["tool"] == "essay.health"


def test_ac6_one_shot_fo_card_without_student_install_speech(tmp_path):
    """AC6. One-shot FO card re-reads FIRST-RUN and bot.md; no student chat install steps."""
    root = tmp_path / "project"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "essay-writer"\n', encoding="utf-8")
    body = attach_friend_upgrade_fo_card({"ok": True}, root=root)
    assert body["fo_card"] == UPGRADE_REREAD_SPEECH
    assert "FIRST-RUN.txt" in body["fo_card"]
    assert "bot.md" in body["fo_card"]
    assert "chat" not in body
    assert "next" not in body
    again = attach_friend_upgrade_fo_card({"ok": True}, root=root)
    assert "fo_card" not in again


def test_ac7_attach_mcp_upgrade_path_self_checks_and_fo_card(monkeypatch, capsys):
    """AC7. Custom MCP upgrade shares install_self_check and the one-shot FO card."""
    marker = package_root() / UPGRADE_REREAD_MARKER
    if marker.is_file():
        marker.unlink()
    monkeypatch.setattr(
        "essay_writer.first_run.ensure_cursor_agent",
        lambda **kwargs: {"ok": True, "installed": False},
    )
    monkeypatch.setattr(
        "essay_writer.first_run.attach_custom_mcp",
        lambda root, **kwargs: {"ok": True, "servers": ["essay-writer"], "reviewer": kwargs.get("reviewer")},
    )
    monkeypatch.setattr(
        "essay_writer.first_run.attach_build_mcp",
        lambda *args, **kwargs: {"ok": True, "servers": ["essay-writer"]},
    )
    code = main(["--attach-mcp", "--no-reviewer"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["health_check"]["tool"] == "essay.health"
    assert payload["fo_card"] == UPGRADE_REREAD_SPEECH
    assert "chat" not in payload


def test_remember_mac_still_wins_over_canonical(tmp_path, monkeypatch):
    """Named remember path overrides canonical Essay Bot for copies."""
    _linux, mac, _cloud = _bot_and_mac(tmp_path, monkeypatch)
    canonical = mac / "Documents" / "Essay Bot"
    canonical.mkdir(parents=True)
    other = mac / "Documents" / "Course Copies"
    other.mkdir(parents=True)
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(other))
    source = tmp_path / "essay.docx"
    source.write_bytes(b"x")
    copied = copy_deliverable_to_mac(source)
    assert copied["copied"] is True
    assert (other / "essay.docx").is_file()
    assert not (canonical / "essay.docx").exists()


def test_cli_remember_mac_still_four_way(tmp_path, monkeypatch, capsys):
    """choose_mac_handoff skip still does not set a folder when canonical exists."""
    _linux, mac, _cloud = _bot_and_mac(tmp_path, monkeypatch)
    (mac / "Documents" / "Essay Bot").mkdir(parents=True)
    code = main(["--remember-mac-dir", "skip"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["remembered"] is False
    direct = choose_mac_handoff("skip")
    assert direct["remembered"] is False
