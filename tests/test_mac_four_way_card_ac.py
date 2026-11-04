"""Mac four-way first-run card polish. Stable ids: AC1–AC6."""

import inspect
import json

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.first_run import (
    MAC_FOUR_WAY_CARD,
    MAC_FOUR_WAY_FRIEND_SPEECH,
    choose_mac_handoff,
    copy_deliverable_to_mac,
    first_run_prompt,
    main,
    package_root,
    visible_canonical_mac_handoff_dir,
)
from essay_writer.setup import CURSOR_SETUP_PROMPT, FIRST_RUN_MAC_SPEECH, SETUP_PROMPT


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


def _prompt_copies(name: str) -> tuple[str, str]:
    root = package_root()
    disk = (root / name).read_text(encoding="utf-8")
    packaged = (root / "src" / "essay_writer" / name).read_text(encoding="utf-8")
    return disk, packaged


def test_ac1_first_run_and_friend_show_four_way_card():
    """AC1. FIRST-RUN and FRIEND-PROMPT show OK / another / later / skip."""
    root_run, packaged_run = _prompt_copies("FIRST-RUN.txt")
    friend, friend_packaged = _prompt_copies("FRIEND-PROMPT.txt")
    assert root_run == packaged_run == first_run_prompt()
    assert friend == friend_packaged
    for text in (root_run, friend, SETUP_PROMPT, CURSOR_SETUP_PROMPT, FIRST_RUN_MAC_SPEECH):
        assert MAC_FOUR_WAY_CARD in text
    assert MAC_FOUR_WAY_FRIEND_SPEECH in friend
    assert "do not say the mac folder is ready" in root_run.casefold()


def test_ac2_ok_creates_essay_bot_consistent_with_canonical_handoff(tmp_path, monkeypatch, capsys):
    """AC2. OK creates Documents/Essay Bot and matches the copy handoff."""
    _linux, mac, cloud = _bot_and_mac(tmp_path, monkeypatch)
    code = main(["--remember-mac-dir", "ok"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    folder = mac / "Documents" / "Essay Bot"
    assert folder.is_dir()
    assert payload["mac_folder_ready"] is True
    assert payload["remembered"] is True
    source = tmp_path / "handoff.docx"
    source.write_bytes(b"copy-me")
    monkeypatch.delenv("ESSAY_WRITER_MAC_DIR", raising=False)
    assert visible_canonical_mac_handoff_dir() == folder
    copied = copy_deliverable_to_mac(source)
    assert copied["copied"] is True
    assert (folder / "handoff.docx").read_bytes() == b"copy-me"
    secret = cloud / "Essay-writer" / "setup.secrets.json"
    assert json.loads(secret.read_text(encoding="utf-8"))["ESSAY_WRITER_MAC_DIR"] == str(folder.resolve())


def test_ac3_later_and_skip_chat_only_honest(tmp_path, monkeypatch, capsys):
    """AC3. later/skip stay chat-only; no mac_folder_ready."""
    _linux, mac, _cloud = _bot_and_mac(tmp_path, monkeypatch)
    for choice in ("later", "skip"):
        code = main(["--remember-mac-dir", choice])
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["chat_only"] is True
        assert payload["mac_folder_ready"] is False
        assert payload["remembered"] is False
        assert "path" not in payload
    assert not (mac / "Documents").exists()
    for prompt in (first_run_prompt(), FIRST_RUN_MAC_SPEECH):
        assert "do not say the mac folder is ready" in prompt.casefold()


def test_ac4_another_without_path_does_not_break_setup(tmp_path, monkeypatch):
    """AC4. another without a folder asks for the path and leaves setup unchanged."""
    _linux, mac, cloud = _bot_and_mac(tmp_path, monkeypatch)
    blocked = choose_mac_handoff("another")
    assert blocked["ok"] is False
    assert blocked["choice"] == "another"
    assert blocked["mac_folder_ready"] is False
    assert blocked["reason"] == "Name the Mac folder."
    assert not (mac / "Documents").exists()
    assert not (cloud / "Essay-writer" / "setup.secrets.json").exists()
    named = choose_mac_handoff("another", folder="Documents/Course Copies")
    assert named["ok"] is True
    assert named["mac_folder_ready"] is True
    assert (mac / "Documents" / "Course Copies").is_dir()


def test_ac5_mid_office_does_not_auto_pick_mac_handoff():
    """AC5. stage launch paths do not bypass the four-way card."""
    for fn in (stage_launch, cursor_stage_launch):
        source = inspect.getsource(fn)
        assert "choose_mac_handoff" not in source
        assert "remember_mac" not in source


def test_ac6_card_constant_is_single_source():
    """AC6. MAC_FOUR_WAY_CARD matches the shipped FIRST-RUN card line."""
    assert f'Show this card: "{MAC_FOUR_WAY_CARD}"' in first_run_prompt()
    assert MAC_FOUR_WAY_CARD == (
        "Word copies go to Documents/Essay Bot — OK, another folder, later, or skip."
    )
