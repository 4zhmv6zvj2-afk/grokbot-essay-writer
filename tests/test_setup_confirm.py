"""Setup is draft-then-confirm, save targets, and Consensus at setup."""

import json
import stat
from pathlib import Path

from essay_writer.health import essay_health
from essay_writer.paths import CLOUD_WORKSPACE
from essay_writer.setup import essay_setup


def test_setup_draft_writes_nothing_and_confirm_builds_the_door_tree(tmp_path, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_ROOT", str(tmp_path / "ledger"))
    cloud = tmp_path / "cloud"
    cloud.mkdir()
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", cloud)
    app = cloud / "Essay-writer" / "app"
    kb1 = cloud / "Essay-writer" / "KB1"
    draft = essay_setup(confirmPhase="draft", acknowledge_skipped_searches=True)
    assert draft["wrote"] is False
    assert draft["where"] == "grokbot-cloud-computer"
    assert not app.exists()
    confirmed = essay_setup(confirmPhase="confirm", acknowledge_skipped_searches=True)
    assert confirmed["wrote"] is True
    assert confirmed["where"] == "grokbot-cloud-computer"
    assert (app / "Essay-writer").is_dir()
    assert (app / "uploads").is_dir()
    assert (app / "unassigned").is_dir()
    assert kb1.is_dir()
    assert confirmed["wrote_notes"] is False
    record = json.loads((cloud / "Essay-writer" / "setup.json").read_text(encoding="utf-8"))
    assert record["where"] == "grokbot-cloud-computer"
    assert record["app"] == str(app.resolve())


def test_no_documents_fallback_and_internal_volume_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_ROOT", str(tmp_path / "ledger"))
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", tmp_path / "missing")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    missing = essay_setup(confirmPhase="draft")
    assert missing["ok"] is False
    assert not (tmp_path / "Documents").exists()
    volume = tmp_path / "ResearchDrive" / "app"
    kb1 = tmp_path / "local" / "KB1"
    refused = essay_setup(app_path=str(volume), kb1_path=str(kb1), confirmPhase="draft")
    assert refused["ok"] is False
    assert refused["refused"] == "setup"
    assert not volume.exists()
    documents = tmp_path / "Documents" / "Essay-writer" / "app"
    vault = tmp_path / "Documents" / "Essay-writer" / "KB1"
    draft = essay_setup(app_path=str(documents), kb1_path=str(vault), confirmPhase="draft")
    assert draft["ok"] is True
    assert draft["where"] == "user-local"
    assert draft["where"] != "grokbot-cloud-computer"


def test_setup_fail_closed_when_the_path_is_a_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_ROOT", str(tmp_path / "ledger"))
    blocker = tmp_path / "app"
    blocker.write_text("not a folder\n", encoding="utf-8")
    kb1 = tmp_path / "KB1"
    refused = essay_setup(app_path=str(blocker), kb1_path=str(kb1), confirmPhase="confirm")
    assert refused["ok"] is False
    assert refused["wrote"] is False
    assert blocker.is_file()
    assert not (tmp_path / "setup.json").exists()


def test_optional_secrets_are_stored_and_not_echoed(tmp_path, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_ROOT", str(tmp_path / "ledger"))
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", tmp_path / "missing-cloud")
    app = tmp_path / "app"
    kb1 = tmp_path / "KB1"
    key = "consensus-secret-value"
    email = "reader@example.com"
    draft = essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="draft",
        consensus_api_key=key,
        unpaywall_email=email,
        consensus_plan="pro",
    )
    assert draft["wrote"] is False
    assert key not in json.dumps(draft)
    assert email not in json.dumps(draft)
    assert draft["consensus_key"] is True
    assert draft["unpaywall_email"] is True
    skipped = essay_setup(app_path=str(app), kb1_path=str(kb1), confirmPhase="draft")
    assert skipped["consensus_key"] is False
    confirmed = essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="confirm",
        consensus_api_key=key,
        unpaywall_email=email,
        consensus_plan="pro",
    )
    assert confirmed["wrote"] is True
    dumped = json.dumps(confirmed)
    assert key not in dumped
    assert email not in dumped
    record = json.loads((tmp_path / "setup.json").read_text(encoding="utf-8"))
    assert key not in json.dumps(record)
    assert email not in json.dumps(record)
    assert record["consensus_key"] is True
    secrets = json.loads((tmp_path / "setup.secrets.json").read_text(encoding="utf-8"))
    assert secrets["CONSENSUS_API_KEY"] == key
    assert secrets["ESSAY_WRITER_UNPAYWALL_EMAIL"] == email
    assert secrets["ESSAY_WRITER_CONSENSUS_PAID"] == "1"
    mode = (tmp_path / "setup.secrets.json").stat().st_mode
    assert mode & stat.S_IRWXO == 0


def test_named_save_on_the_cloud_computer_is_the_record_later_tools_read(tmp_path, monkeypatch):
    """A named folder still writes the record where later tools read it."""
    from essay_writer.paths import load_saved_setup
    from essay_writer.setup import read_setup_secret

    monkeypatch.setenv("ESSAY_WRITER_ROOT", str(tmp_path / "ledger"))
    cloud = tmp_path / "cloud"
    cloud.mkdir()
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", cloud)
    app = tmp_path / "named-app"
    kb1 = tmp_path / "named-kb1"
    key = "named-consensus-key"
    draft = essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="draft",
        consensus_api_key=key,
        consensus_plan="pro",
        acknowledge_skipped_searches=True,
    )
    assert draft["ok"] is True, draft
    assert draft["wrote"] is False
    confirmed = essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="confirm",
        consensus_api_key=key,
        consensus_plan="pro",
        acknowledge_skipped_searches=True,
    )
    assert confirmed["ok"] is True, confirmed
    assert confirmed["where"] == "user-local"
    assert key not in json.dumps(confirmed)
    assert not (tmp_path / "setup.json").exists()
    assert not (tmp_path / "setup.secrets.json").exists()
    record_path = cloud / "Essay-writer" / "setup.json"
    secret_path = cloud / "Essay-writer" / "setup.secrets.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["app_path"] == str(app.resolve())
    assert record["kb1"] == str(kb1.resolve())
    assert json.loads(secret_path.read_text(encoding="utf-8"))["CONSENSUS_API_KEY"] == key
    assert confirmed["setup"].endswith("Essay-writer/setup.json")
    record["debug"] = True
    record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="draft",
        acknowledge_skipped_searches=True,
    )
    again = essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="confirm",
        acknowledge_skipped_searches=True,
    )
    assert again["ok"] is True, again
    kept = json.loads(record_path.read_text(encoding="utf-8"))
    assert kept["debug"] is True
    assert kept["app_path"] == str(app.resolve())
    monkeypatch.delenv("ESSAY_WRITER_ROOT", raising=False)
    loaded = load_saved_setup()
    assert loaded is not None
    assert loaded["app_path"] == str(app.resolve())
    assert read_setup_secret("CONSENSUS_API_KEY") == key


def test_a_test_root_does_not_write_the_host_cloud_setup(tmp_path, monkeypatch):
    """ESSAY_WRITER_ROOT must not clobber the host /workspace setup record."""
    monkeypatch.setenv("ESSAY_WRITER_ROOT", str(tmp_path / "ledger"))
    host = Path("/workspace/Essay-writer/setup.json")
    before = host.read_bytes() if host.is_file() else None
    app = tmp_path / "app"
    kb1 = tmp_path / "KB1"
    essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="draft",
        acknowledge_skipped_searches=True,
    )
    saved = essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="confirm",
        acknowledge_skipped_searches=True,
    )
    assert saved["ok"] is True, saved
    assert (tmp_path / "setup.json").is_file()
    after = host.read_bytes() if host.is_file() else None
    assert after == before


def test_a_named_save_without_a_cloud_workspace_is_read_later(tmp_path, monkeypatch):
    """With no cloud computer, later tools read the home copy of a named save."""
    from essay_writer.paths import load_saved_setup
    from essay_writer.setup import read_setup_secret

    monkeypatch.delenv("ESSAY_WRITER_ROOT", raising=False)
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", tmp_path / "missing-cloud")
    record = tmp_path / "home" / ".essay-writer" / "setup.json"
    monkeypatch.setattr("essay_writer.paths.local_setup_record", lambda: record)
    app = tmp_path / "named-app"
    kb1 = tmp_path / "named-kb1"
    key = "local-consensus-key"
    essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="draft",
        consensus_api_key=key,
        consensus_plan="pro",
        acknowledge_skipped_searches=True,
    )
    saved = essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="confirm",
        consensus_api_key=key,
        consensus_plan="pro",
        acknowledge_skipped_searches=True,
    )
    assert saved["ok"] is True, saved
    assert json.loads(record.read_text(encoding="utf-8"))["app_path"] == str(app.resolve())
    assert json.loads((tmp_path / "setup.json").read_text(encoding="utf-8"))["app_path"] == str(app.resolve())
    loaded = load_saved_setup()
    assert loaded is not None
    assert loaded["app_path"] == str(app.resolve())
    assert read_setup_secret("CONSENSUS_API_KEY") == key


def test_install_refuses_the_app_folder_named_on_the_setup_record(tmp_path, monkeypatch):
    from essay_writer.first_run import _blocked_dest

    monkeypatch.delenv("ESSAY_WRITER_ROOT", raising=False)
    cloud = tmp_path / "cloud"
    cloud.mkdir()
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", cloud)
    app = tmp_path / "named-app"
    record_dir = cloud / "Essay-writer"
    record_dir.mkdir()
    (record_dir / "setup.json").write_text(
        json.dumps({"app_path": str(app), "app": str(app)}),
        encoding="utf-8",
    )
    reason = _blocked_dest(app)
    assert reason is not None
    assert "save tree" in reason
    assert _blocked_dest(tmp_path / "other") is None


def test_consensus_switch_is_on_the_health_reminder(workspace, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_CONSENSUS", "0")
    monkeypatch.setenv("CONSENSUS_API_KEY", "present-but-off")
    report = essay_health()
    assert report["consensus"]["enabled"] is False
    assert report["consensus"]["switch"] == "0"
    assert "ESSAY_WRITER_CONSENSUS=0" in report["consensus"]["remind"]
    assert "present-but-off" not in json.dumps(report)
    monkeypatch.setenv("ESSAY_WRITER_CONSENSUS", "1")
    on = essay_health()
    assert on["consensus"]["enabled"] is True
    assert on["consensus"]["key_present"] is True
    assert "present-but-off" not in json.dumps(on)


def test_cloud_constant_is_the_workspace_root():
    assert CLOUD_WORKSPACE == Path("/workspace")
