"""Mac Essay Bot folder on OK. Stable ids: AC1, AC2, AC3, AC4."""

import inspect
import json
import os
from pathlib import Path

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.first_run import (
    MAC_FOUR_WAY_CARD,
    choose_mac_handoff,
    first_run_prompt,
    friend_mac_home,
    main,
)
from essay_writer.setup import CURSOR_SETUP_PROMPT, FIRST_RUN_MAC_SPEECH, SETUP_PROMPT

REAL_ESSAY_BOT = Path.home() / "Documents" / "Essay Bot"


def _bot_and_mac(tmp_path, monkeypatch):
    """Grok Bot Linux home beside a Mac home this computer can already see."""
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
    assert friend_mac_home() == mac
    return linux, mac, cloud


def _secret(cloud: Path) -> Path:
    return cloud / "Essay-writer" / "setup.secrets.json"


def test_ac1_ok_creates_documents_essay_bot_on_the_mac(tmp_path, monkeypatch, capsys):
    """AC1. OK creates Documents/Essay Bot on the Mac and stores the handoff."""
    linux, mac, cloud = _bot_and_mac(tmp_path, monkeypatch)
    real_existed = REAL_ESSAY_BOT.exists()
    code = main(["--remember-mac-dir", "ok"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    folder = mac / "Documents" / "Essay Bot"
    assert folder.is_dir()
    assert payload["ok"] is True
    assert payload["remembered"] is True
    assert payload["created"] is True
    assert payload["choice"] == "ok"
    assert payload["path"] == str(folder.resolve())
    data = json.loads(_secret(cloud).read_text(encoding="utf-8"))
    assert data["ESSAY_WRITER_MAC_DIR"] == str(folder.resolve())
    assert not (linux / "Documents").exists()
    assert not (cloud / "Documents").exists()
    assert os.environ.get("ESSAY_WRITER_MAC_DIR") is None
    monkeypatch.delenv("ESSAY_WRITER_MAC_HOME", raising=False)
    missed = choose_mac_handoff("ok")
    assert missed["ok"] is False
    assert missed["remembered"] is False
    assert missed["created"] is False
    assert missed["reason"] == "mac-not-mounted"
    blocked = choose_mac_handoff(str(linux / "Documents" / "Essay Bot"))
    assert blocked["ok"] is False
    assert blocked["remembered"] is False
    assert not (linux / "Documents").exists()
    kept = json.loads(_secret(cloud).read_text(encoding="utf-8"))
    assert kept["ESSAY_WRITER_MAC_DIR"] == str(folder.resolve())
    if not real_existed:
        assert not REAL_ESSAY_BOT.exists()


def test_ac2_later_and_skip_do_not_set_mac_dir(tmp_path, monkeypatch, capsys):
    """AC2. Later, skip, and decline do not set ESSAY_WRITER_MAC_DIR or invent a folder."""
    linux, mac, cloud = _bot_and_mac(tmp_path, monkeypatch)
    real_existed = REAL_ESSAY_BOT.exists()
    for choice in ("later", "skip", "decline"):
        code = main(["--remember-mac-dir", choice])
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is True
        assert payload["remembered"] is False
        assert payload["created"] is False
        assert payload["choice"] == "skip"
        assert payload["chat_only"] is True
        assert payload["mac_folder_ready"] is False
        assert "path" not in payload
    assert not (mac / "Documents").exists()
    assert not (mac / "Documents" / "Essay Bot").exists()
    assert not (linux / "Documents").exists()
    assert not _secret(cloud).exists()
    assert os.environ.get("ESSAY_WRITER_MAC_DIR") is None
    direct = choose_mac_handoff("skip")
    assert direct["remembered"] is False
    assert not (mac / "Documents" / "Essay Bot").exists()
    if not real_existed:
        assert not REAL_ESSAY_BOT.exists()


def test_ac3_named_other_folder_is_created_on_the_mac(tmp_path, monkeypatch):
    """AC3. A named other folder is created on the Mac and remembered."""
    linux, mac, cloud = _bot_and_mac(tmp_path, monkeypatch)
    named = choose_mac_handoff("another", folder="Documents/Course Copies")
    folder = mac / "Documents" / "Course Copies"
    assert named["ok"] is True
    assert named["remembered"] is True
    assert named["created"] is True
    assert folder.is_dir()
    assert not (mac / "Documents" / "Essay Bot").exists()
    data = json.loads(_secret(cloud).read_text(encoding="utf-8"))
    assert data["ESSAY_WRITER_MAC_DIR"] == str(folder.resolve())
    moved = choose_mac_handoff(str(linux / "Documents" / "Other"))
    other = mac / "Documents" / "Other"
    assert moved["ok"] is True
    assert other.is_dir()
    assert not (linux / "Documents").exists()
    stored = json.loads(_secret(cloud).read_text(encoding="utf-8"))
    assert stored["ESSAY_WRITER_MAC_DIR"] == str(other.resolve())
    assert os.environ.get("ESSAY_WRITER_MAC_DIR") is None


def test_ac4_prompts_still_say_the_four_way_card():
    """AC4. Friend, first-run, and both setup prompts keep the four-way card."""
    root_prompt, packaged = _prompt_copies("FIRST-RUN.txt")
    friend, friend_packaged = _prompt_copies("FRIEND-PROMPT.txt")
    assert root_prompt == packaged == first_run_prompt()
    assert friend == friend_packaged
    for text in (root_prompt, friend, SETUP_PROMPT, CURSOR_SETUP_PROMPT, FIRST_RUN_MAC_SPEECH):
        assert MAC_FOUR_WAY_CARD in text
    assert "choose_mac_handoff" in FIRST_RUN_MAC_SPEECH
    assert FIRST_RUN_MAC_SPEECH in SETUP_PROMPT
    assert FIRST_RUN_MAC_SPEECH in CURSOR_SETUP_PROMPT
    for fn in (stage_launch, cursor_stage_launch):
        source = inspect.getsource(fn)
        assert "choose_mac_handoff" not in source
        assert "remember_mac" not in source


def _prompt_copies(name: str) -> tuple[str, str]:
    root = Path(__file__).resolve().parents[1]
    disk = (root / name).read_text(encoding="utf-8")
    packaged = (root / "src" / "essay_writer" / name).read_text(encoding="utf-8")
    return disk, packaged
