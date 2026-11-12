"""Saved setup, file-work choice, and save-folder drives.

Confirm writes setup.json and setup.secrets.json beside the chosen app folder.
A later dig and research load reads those files. A missing file-work choice
stays Cursor. An unknown stored choice fails. ResearchDrive, BackupDrive, and
ArchiveDrive are refused as save folders. An ordinary folder still saves.
Student chat does not show those drive names.
"""

import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from helpers import open_sequence

from essay_writer.cursor_office import stage_host_launch
from essay_writer.dig import consensus_api_key, essay_dig
from essay_writer.first_run_install import install_uploaded_copy
from essay_writer.first_run_mac import choose_mac_handoff, copy_deliverable_to_mac
from essay_writer.late_chain import completed_draft_chat
from essay_writer.paths import student_chat_path
from essay_writer.resolvers import enrich_sources, unpaywall_email
from essay_writer.setup import UnknownMidOfficeShell, essay_setup, mid_office, persisted_shell
from essay_writer.student_voice import say, speak
from essay_writer.user_place import chat_place

KEY = "dummy-consensus-key"
EMAIL = "dummy-reader@example.com"
LOADED_KEY = "dummy-consensus-key-loaded"
LOADED_EMAIL = "dummy-loaded@example.com"
DECOY_KEY = "dummy-decoy-consensus-key"


def _host(url: object) -> str:
    return (urlparse(str(url)).hostname or "").casefold()


def _quiet_lookup_env(monkeypatch) -> None:
    for name in (
        "CONSENSUS_API_KEY",
        "ESSAY_WRITER_UNPAYWALL_EMAIL",
        "ESSAY_WRITER_CONSENSUS",
        "ESSAY_WRITER_CONSENSUS_PAID",
        "ESSAY_WRITER_RESOLVERS",
        "ESSAY_WRITER_MAC_DIR",
    ):
        monkeypatch.delenv(name, raising=False)


def _missing_workspace(monkeypatch, tmp_path: Path) -> Path:
    missing = tmp_path / "no-workspace"
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", missing)
    _quiet_lookup_env(monkeypatch)
    return missing


def _confirm_local(app: Path, kb1: Path, **extra: object) -> dict[str, object]:
    draft = essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="draft",
        **extra,
    )
    assert draft["ok"] is True, draft
    saved = essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="confirm",
        **extra,
    )
    assert saved["ok"] is True, saved
    assert saved["wrote"] is True
    return saved


def _write_beside(app: Path, *, key: str, email: str) -> tuple[Path, Path]:
    app.mkdir(parents=True, exist_ok=True)
    record = app.parent / "setup.json"
    secret = app.parent / "setup.secrets.json"
    record.write_text(
        json.dumps({"app_path": str(app.resolve()), "app": str(app.resolve())}) + "\n",
        encoding="utf-8",
    )
    secret.write_text(
        json.dumps(
            {
                "CONSENSUS_API_KEY": key,
                "ESSAY_WRITER_UNPAYWALL_EMAIL": email,
                "ESSAY_WRITER_CONSENSUS_PAID": "0",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return record, secret


@pytest.mark.parametrize("case_id", ["ew-hunt-s1-ac1"])
def test_ew_hunt_s1_ac1(case_id, tmp_path, monkeypatch):
    """Confirm writes beside the app. Dig and research then use that key and email."""
    assert case_id == "ew-hunt-s1-ac1"
    missing = _missing_workspace(monkeypatch, tmp_path)
    app = tmp_path / "chosen-app"
    kb1 = tmp_path / "KB1"
    monkeypatch.setenv("ESSAY_WRITER_ROOT", str(app))
    _confirm_local(
        app,
        kb1,
        consensus_api_key=KEY,
        unpaywall_email=EMAIL,
        consensus_plan="free",
    )
    record = app.parent / "setup.json"
    secret = app.parent / "setup.secrets.json"
    assert record.is_file()
    assert secret.is_file()
    assert not missing.is_dir()
    stored = json.loads(secret.read_text(encoding="utf-8"))
    stored["CONSENSUS_API_KEY"] = LOADED_KEY
    stored["ESSAY_WRITER_UNPAYWALL_EMAIL"] = LOADED_EMAIL
    secret.write_text(json.dumps(stored) + "\n", encoding="utf-8")

    captured: list[dict[str, object]] = []

    def fake_get(url: str, headers: dict[str, str] | None = None) -> dict[str, object]:
        captured.append({"url": url, "headers": dict(headers or {})})
        host = _host(url)
        if host == "api.consensus.app":
            return {
                "plan": "free",
                "results": [
                    {
                        "title": "Consensus paper",
                        "year": 2020,
                        "doi": "10.1000/cons",
                        "authors": ["Ada"],
                    }
                ],
            }
        if host == "api.openalex.org":
            return {
                "results": [
                    {
                        "title": "OpenAlex paper",
                        "publication_year": 2021,
                        "doi": "10.1000/open",
                        "authorships": [{"author": {"display_name": "Bea"}}],
                    }
                ]
            }
        if host == "api.unpaywall.org":
            return {"best_oa_location": {"url_for_pdf": "https://example.test/paper.pdf"}}
        return {}

    research_urls: list[str] = []

    def fake_lookup(url: str) -> None:
        research_urls.append(url)
        return None

    monkeypatch.setattr("essay_writer.dig._get_json", fake_get)
    monkeypatch.setattr("essay_writer.resolvers._lookup_json", fake_lookup)
    seq = open_sequence()
    draft = essay_dig(seq, "chokepoints", "draft")
    assert draft["ok"] is True, draft
    assert draft["consensus"]["key_present"] is True
    assert draft["consensus"]["enabled"] is True
    dumped = json.dumps(draft)
    assert LOADED_KEY not in dumped
    assert LOADED_EMAIL not in dumped
    consensus_calls = [item for item in captured if _host(item["url"]) == "api.consensus.app"]
    assert consensus_calls
    assert consensus_calls[0]["headers"]["x-api-key"] == LOADED_KEY
    unpaywall_calls = [item for item in captured if _host(item["url"]) == "api.unpaywall.org"]
    assert unpaywall_calls
    dig_email = parse_qs(urlparse(str(unpaywall_calls[0]["url"])).query).get("email")
    assert dig_email == [LOADED_EMAIL]

    source = {"id": "s1", "locator": "uploads/MOD1004AA/note.txt", "doi": "10.1000/dummy"}
    enrich_sources([source], {source["locator"]: "See 10.1000/dummy for the paper.\n"})
    research_unpaywall = [url for url in research_urls if _host(url) == "api.unpaywall.org"]
    assert research_unpaywall
    research_email = parse_qs(urlparse(research_unpaywall[0]).query).get("email")
    assert research_email == [LOADED_EMAIL]


@pytest.mark.parametrize("case_id", ["ew-hunt-s1-ac2"])
def test_ew_hunt_s1_ac2(case_id, tmp_path, monkeypatch):
    """A key beside the app still loads when the cloud workspace does not exist."""
    assert case_id == "ew-hunt-s1-ac2"
    missing = _missing_workspace(monkeypatch, tmp_path)
    app = tmp_path / "chosen-app"
    monkeypatch.setenv("ESSAY_WRITER_ROOT", str(app))
    decoy_workspace = tmp_path / "workspace" / "Essay-writer"
    decoy_workspace.mkdir(parents=True)
    (decoy_workspace / "setup.secrets.json").write_text(
        json.dumps({"CONSENSUS_API_KEY": DECOY_KEY}) + "\n",
        encoding="utf-8",
    )
    _write_beside(app, key=KEY, email=EMAIL)
    assert not missing.exists()
    assert consensus_api_key() == KEY
    assert unpaywall_email() == EMAIL


@pytest.mark.parametrize("case_id", ["ew-hunt-s1-ac3"])
def test_ew_hunt_s1_ac3(case_id, tmp_path, monkeypatch):
    """ESSAY_WRITER_ROOT does not skip the setup files confirm wrote."""
    assert case_id == "ew-hunt-s1-ac3"
    _missing_workspace(monkeypatch, tmp_path)
    app = tmp_path / "chosen-app"
    kb1 = tmp_path / "KB1"
    ledger = tmp_path / "ledger"
    monkeypatch.setenv("ESSAY_WRITER_ROOT", str(ledger))
    home = tmp_path / "home-decoy"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    home_secret = home / ".essay-writer"
    home_secret.mkdir(parents=True)
    (home_secret / "setup.json").write_text(
        json.dumps({"app_path": str(app)}) + "\n",
        encoding="utf-8",
    )
    (home_secret / "setup.secrets.json").write_text(
        json.dumps(
            {"CONSENSUS_API_KEY": DECOY_KEY, "ESSAY_WRITER_UNPAYWALL_EMAIL": "decoy@example.com"}
        )
        + "\n",
        encoding="utf-8",
    )
    _confirm_local(
        app,
        kb1,
        consensus_api_key=KEY,
        unpaywall_email=EMAIL,
        consensus_plan="free",
    )
    assert os.environ.get("ESSAY_WRITER_ROOT")
    assert consensus_api_key() == KEY
    assert unpaywall_email() == EMAIL
    beside = json.loads((app.parent / "setup.secrets.json").read_text(encoding="utf-8"))
    assert beside["CONSENSUS_API_KEY"] == KEY
    assert beside["ESSAY_WRITER_UNPAYWALL_EMAIL"] == EMAIL


def _shell_record(tmp_path: Path, monkeypatch, body: dict[str, object]) -> None:
    monkeypatch.delenv("ESSAY_WRITER_ROOT", raising=False)
    cloud = tmp_path / "workspace"
    cloud.mkdir(exist_ok=True)
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", cloud)
    record_dir = cloud / "Essay-writer"
    record_dir.mkdir(exist_ok=True)
    (record_dir / "setup.json").write_text(json.dumps(body) + "\n", encoding="utf-8")


@pytest.mark.parametrize("case_id", ["ew-hunt-s1-ac4"])
def test_ew_hunt_s1_ac4(case_id, tmp_path, monkeypatch):
    """A setup record with no mid_office_shell still selects Cursor."""
    assert case_id == "ew-hunt-s1-ac4"
    _shell_record(tmp_path, monkeypatch, {"app_path": str(tmp_path / "app")})
    assert persisted_shell() == "cursor"
    assert mid_office() == "Cursor"
    launch = stage_host_launch("1")
    assert launch["command"][0] == "agent"
    assert launch["shell"] == "cursor"


@pytest.mark.parametrize("case_id", ["ew-hunt-s1-ac5"])
def test_ew_hunt_s1_ac5(case_id, tmp_path, monkeypatch):
    """Known Cursor and Grok Build values still select those shells."""
    assert case_id == "ew-hunt-s1-ac5"
    _shell_record(
        tmp_path,
        monkeypatch,
        {"app_path": str(tmp_path / "app"), "mid_office_shell": "cursor"},
    )
    assert persisted_shell() == "cursor"
    assert mid_office() == "Cursor"
    cursor = stage_host_launch("1")
    assert cursor["command"][0] == "agent"
    assert cursor["shell"] == "cursor"

    _shell_record(
        tmp_path,
        monkeypatch,
        {"app_path": str(tmp_path / "app"), "mid_office_shell": "grok_build"},
    )
    assert persisted_shell() == "grok_build"
    assert mid_office() == "Grok Build"
    grok = stage_host_launch("1")
    assert grok["command"][0] == "grok"


@pytest.mark.parametrize("case_id", ["ew-hunt-s1-ac6"])
def test_ew_hunt_s1_ac6(case_id, tmp_path, monkeypatch):
    """An unknown or mistyped stored choice fails and does not select Grok Build."""
    assert case_id == "ew-hunt-s1-ac6"
    calls: list[str] = []

    def cursor_launch(*_args, **_kwargs):
        calls.append("cursor")
        return {"shell": "cursor"}

    def grok_launch(*_args, **_kwargs):
        calls.append("grok")
        return {"command": ["grok"]}

    monkeypatch.setattr("essay_writer.cursor_office.cursor_stage_launch", cursor_launch)
    monkeypatch.setattr("essay_writer.build_office.stage_launch", grok_launch)
    for raw in ("not-a-shell", "cursr", "Grok Buld"):
        calls.clear()
        _shell_record(
            tmp_path,
            monkeypatch,
            {"app_path": str(tmp_path / "app"), "mid_office_shell": raw},
        )
        with pytest.raises(UnknownMidOfficeShell) as caught:
            persisted_shell()
        assert "Cursor" in str(caught.value)
        assert "Grok Build" in str(caught.value)
        with pytest.raises(UnknownMidOfficeShell):
            mid_office()
        with pytest.raises(UnknownMidOfficeShell):
            stage_host_launch("1")
        assert calls == []


def _beside_app_shell(tmp_path: Path, monkeypatch, body: dict[str, object]) -> None:
    """Setup record beside the app, with the override root set and no cloud workspace."""
    missing = tmp_path / "no-workspace"
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", missing)
    app = tmp_path / "chosen-app"
    record = dict(body)
    record["app_path"] = str(app)
    (tmp_path / "setup.json").write_text(json.dumps(record) + "\n", encoding="utf-8")
    monkeypatch.setenv("ESSAY_WRITER_ROOT", str(app))
    assert not missing.exists()


def test_beside_app_grok_build_is_read_with_the_override_root(tmp_path, monkeypatch):
    """A Grok Build choice beside the app is read when the override root is set."""
    _beside_app_shell(
        tmp_path,
        monkeypatch,
        {"mid_office_shell": "grok_build"},
    )
    assert persisted_shell() == "grok_build"
    assert mid_office() == "Grok Build"
    launch = stage_host_launch("1")
    assert launch["command"][0] == "grok"


def test_beside_app_unknown_shell_fails_with_the_override_root(tmp_path, monkeypatch):
    """An unknown choice beside the app fails and does not select Cursor."""
    calls: list[str] = []

    def cursor_launch(*_args, **_kwargs):
        calls.append("cursor")
        return {"shell": "cursor", "command": ["agent"]}

    def grok_launch(*_args, **_kwargs):
        calls.append("grok")
        return {"command": ["grok"]}

    monkeypatch.setattr("essay_writer.cursor_office.cursor_stage_launch", cursor_launch)
    monkeypatch.setattr("essay_writer.build_office.stage_launch", grok_launch)
    for raw in ("not-a-shell", "cursr"):
        calls.clear()
        _beside_app_shell(
            tmp_path,
            monkeypatch,
            {"mid_office_shell": raw},
        )
        with pytest.raises(UnknownMidOfficeShell):
            persisted_shell()
        with pytest.raises(UnknownMidOfficeShell):
            mid_office()
        with pytest.raises(UnknownMidOfficeShell):
            stage_host_launch("1")
        assert calls == []


def test_beside_app_missing_shell_stays_cursor_with_the_override_root(tmp_path, monkeypatch):
    """A missing file-work choice beside the app still selects Cursor."""
    _beside_app_shell(tmp_path, monkeypatch, {})
    assert persisted_shell() == "cursor"
    assert mid_office() == "Cursor"
    launch = stage_host_launch("1")
    assert launch["command"][0] == "agent"
    assert launch["shell"] == "cursor"


def _refuse_save(monkeypatch, tmp_path: Path, folder: Path) -> None:
    monkeypatch.setattr("essay_writer.paths.saved_setup_path", lambda: None)
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", tmp_path / "no-workspace")
    monkeypatch.delenv("ESSAY_WRITER_MAC_DIR", raising=False)
    monkeypatch.setenv("ESSAY_WRITER_ROOT", str(tmp_path / "ledger"))
    kb1 = tmp_path / "ordinary-kb1"
    refused = essay_setup(app_path=str(folder), kb1_path=str(kb1), confirmPhase="draft")
    assert refused["ok"] is False
    assert refused["refused"] == "setup"
    assert not folder.exists()

    upload = tmp_path / f"copy-{folder.name}.zip"
    upload.write_bytes(b"not-unpacked")

    def pip_runner(*_args, **_kwargs):
        raise AssertionError("install ran")

    installed = install_uploaded_copy(
        upload,
        dest=folder / "install",
        attach=False,
        pip_runner=pip_runner,
        include_user=False,
        path_exposer=lambda: None,
    )
    assert installed["ok"] is False
    assert "not an install path" in installed["reason"]
    assert not (folder / "install").exists()

    chosen = choose_mac_handoff("another", folder=str(folder / "copies"))
    assert chosen["ok"] is False
    assert chosen.get("created") is not True
    assert not (folder / "copies").exists()

    source = tmp_path / "essay.docx"
    source.write_bytes(b"word-bytes")
    copied = copy_deliverable_to_mac(source, mac_dir=folder / "out")
    assert copied["ok"] is False
    assert copied["copied"] is False
    assert "not a copy path" in copied["reason"]
    assert not (folder / "out").exists()


@pytest.mark.parametrize("case_id", ["ew-hunt-s1-ac7"])
def test_ew_hunt_s1_ac7(case_id, tmp_path, monkeypatch):
    """ResearchDrive stays refused for setup, first run, and a save-folder choice."""
    assert case_id == "ew-hunt-s1-ac7"
    _refuse_save(monkeypatch, tmp_path, tmp_path / "ResearchDrive")


@pytest.mark.parametrize("case_id", ["ew-hunt-s1-ac8"])
def test_ew_hunt_s1_ac8(case_id, tmp_path, monkeypatch):
    """Backup and archive drives are refused in those same save places."""
    assert case_id == "ew-hunt-s1-ac8"
    for name in ("BackupDrive", "ArchiveDrive", "Backup-Drive", "Archive-Drive"):
        _refuse_save(monkeypatch, tmp_path, tmp_path / name)


@pytest.mark.parametrize("case_id", ["ew-hunt-s1-ac9"])
def test_ew_hunt_s1_ac9(case_id, tmp_path, monkeypatch):
    """An ordinary folder still saves from setup, first run, and a folder choice."""
    assert case_id == "ew-hunt-s1-ac9"
    missing = _missing_workspace(monkeypatch, tmp_path)
    app = tmp_path / "Documents" / "Coursework" / "app"
    kb1 = tmp_path / "Documents" / "Coursework" / "KB1"
    monkeypatch.setenv("ESSAY_WRITER_ROOT", str(tmp_path / "ledger"))
    saved = _confirm_local(app, kb1, acknowledge_skipped_searches=True)
    assert saved["where"] == "user-local"
    assert (app / "Essay-writer").is_dir()
    assert (app / "uploads").is_dir()
    assert kb1.is_dir()
    assert not missing.exists()

    monkeypatch.setattr("essay_writer.paths.saved_setup_path", lambda: None)
    source = tmp_path / "essay.docx"
    source.write_bytes(b"word-bytes")
    mac = tmp_path / "Documents" / "Course Copies"
    copied = copy_deliverable_to_mac(source, mac_dir=mac)
    assert copied["ok"] is True, copied
    assert copied["copied"] is True
    assert (mac / "essay.docx").read_bytes() == b"word-bytes"

    chosen = choose_mac_handoff("another", folder=str(tmp_path / "Documents" / "Essay Copies"))
    assert chosen["ok"] is True, chosen
    assert (tmp_path / "Documents" / "Essay Copies").is_dir()


@pytest.mark.parametrize("case_id", ["ew-hunt-s1-ac10"])
def test_ew_hunt_s1_ac10(case_id, monkeypatch):
    """Student chat does not display ResearchDrive, BackupDrive, or ArchiveDrive."""
    assert case_id == "ew-hunt-s1-ac10"
    monkeypatch.setenv("HOME", "/Users/student")
    monkeypatch.setattr(Path, "home", lambda: Path("/Users/student"))
    for name in (
        "ResearchDrive",
        "BackupDrive",
        "ArchiveDrive",
        "Backup-Drive",
        "Archive-Drive",
    ):
        raw = f"/Volumes/{name}/out/essay.docx"
        assert name not in student_chat_path(raw)
        assert name not in say(f"Save the file under {raw}")
        assert name not in chat_place(raw)
        body = speak({"ok": True, "reason": f"Saved {raw}", "path": raw, "next": f"Open {raw}"})
        assert name not in json.dumps(body)
        assert name not in completed_draft_chat(f"The draft mentions {raw} and {name}.")
    lower_backup = "backupdrive"
    hyphen_archive = "archive-drive"
    assert (
        lower_backup
        not in student_chat_path(f"/Volumes/{lower_backup}/notes/essay.docx").casefold()
    )
    assert "archivedrive" not in say(f"Copies live on /Volumes/{hyphen_archive}/out").casefold()
