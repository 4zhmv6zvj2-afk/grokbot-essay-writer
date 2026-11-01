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
