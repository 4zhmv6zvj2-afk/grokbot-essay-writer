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
        openalex_api_key="openalex-secret-value",
        consensus_plan="pro",
    )
    assert draft["wrote"] is False
    assert key not in json.dumps(draft)
    assert email not in json.dumps(draft)
    assert "openalex-secret-value" not in json.dumps(draft)
    assert draft["consensus_key"] is True
    assert draft["unpaywall_email"] is True
    assert draft["openalex_key"] is True
    skipped = essay_setup(app_path=str(app), kb1_path=str(kb1), confirmPhase="draft")
    assert skipped["consensus_key"] is False
    confirmed = essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="confirm",
        consensus_api_key=key,
        unpaywall_email=email,
        openalex_api_key="openalex-secret-value",
        consensus_plan="pro",
    )
    assert confirmed["wrote"] is True
    dumped = json.dumps(confirmed)
    assert key not in dumped
    assert email not in dumped
    assert "openalex-secret-value" not in dumped
    record = json.loads((tmp_path / "setup.json").read_text(encoding="utf-8"))
    assert key not in json.dumps(record)
    assert email not in json.dumps(record)
    assert "openalex-secret-value" not in json.dumps(record)
    assert record["consensus_key"] is True
    assert record["openalex_key"] is True
    secrets = json.loads((tmp_path / "setup.secrets.json").read_text(encoding="utf-8"))
    assert secrets["CONSENSUS_API_KEY"] == key
    assert secrets["ESSAY_WRITER_UNPAYWALL_EMAIL"] == email
    assert secrets["ESSAY_WRITER_CONSENSUS_PAID"] == "1"
    assert secrets["OPENALEX_API_KEY"] == "openalex-secret-value"
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    from essay_writer.resolvers import openalex_api_key as stored_openalex

    assert stored_openalex() == "openalex-secret-value"
    mode = (tmp_path / "setup.secrets.json").stat().st_mode
    assert mode & stat.S_IRWXO == 0


def test_a_later_setup_keeps_the_secrets_it_was_not_given(tmp_path, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_ROOT", str(tmp_path / "ledger"))
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", tmp_path / "missing-cloud")
    app = tmp_path / "app"
    kb1 = tmp_path / "KB1"
    essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="draft",
        consensus_api_key="first-key",
        unpaywall_email="reader@example.com",
        openalex_api_key="first-openalex-key",
        consensus_plan="pro",
    )
    first = essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="confirm",
        consensus_api_key="first-key",
        unpaywall_email="reader@example.com",
        openalex_api_key="first-openalex-key",
        consensus_plan="pro",
    )
    assert first["wrote"] is True
    secret_path = tmp_path / "setup.secrets.json"
    stored = json.loads(secret_path.read_text(encoding="utf-8"))
    stored["ESSAY_WRITER_MAC_DIR"] = "/Users/student/Documents/Essay Bot"
    secret_path.write_text(json.dumps(stored) + "\n", encoding="utf-8")
    changed = essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="draft",
        consensus_api_key="second-key",
        consensus_plan="free",
    )
    # The email and the OpenAlex key are already stored, so nothing is skipped.
    assert "search_warning" not in changed
    assert changed["consensus_key"] is True
    assert changed["unpaywall_email"] is True
    assert changed["openalex_key"] is True
    second = essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="confirm",
        consensus_api_key="second-key",
        consensus_plan="free",
    )
    assert second["wrote"] is True
    stored = json.loads(secret_path.read_text(encoding="utf-8"))
    assert stored["CONSENSUS_API_KEY"] == "second-key"
    assert stored["ESSAY_WRITER_CONSENSUS_PAID"] == "0"
    assert stored["ESSAY_WRITER_UNPAYWALL_EMAIL"] == "reader@example.com"
    assert stored["OPENALEX_API_KEY"] == "first-openalex-key"
    assert stored["ESSAY_WRITER_MAC_DIR"] == "/Users/student/Documents/Essay Bot"
    record = json.loads((tmp_path / "setup.json").read_text(encoding="utf-8"))
    assert record["consensus_key"] is True
    assert record["unpaywall_email"] is True
    assert record["openalex_key"] is True


def test_adding_only_the_openalex_key_does_not_warn(tmp_path, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_ROOT", str(tmp_path / "ledger"))
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", tmp_path / "missing-cloud")
    app = tmp_path / "app"
    kb1 = tmp_path / "KB1"
    essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="draft",
        consensus_api_key="consensus-key",
        unpaywall_email="reader@example.com",
        consensus_plan="pro",
        acknowledge_skipped_searches=True,
    )
    first = essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="confirm",
        consensus_api_key="consensus-key",
        unpaywall_email="reader@example.com",
        consensus_plan="pro",
        acknowledge_skipped_searches=True,
    )
    assert first["wrote"] is True
    draft = essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="draft",
        openalex_api_key="openalex-key",
    )
    assert draft["ok"] is True
    assert "search_warning" not in draft
    assert "skipped_searches" not in draft
    assert draft["consensus_key"] is True
    assert draft["unpaywall_email"] is True
    assert draft["openalex_key"] is True
    confirmed = essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="confirm",
        openalex_api_key="openalex-key",
    )
    assert confirmed["wrote"] is True
    stored = json.loads((tmp_path / "setup.secrets.json").read_text(encoding="utf-8"))
    assert stored["OPENALEX_API_KEY"] == "openalex-key"
    assert stored["CONSENSUS_API_KEY"] == "consensus-key"
    assert stored["ESSAY_WRITER_UNPAYWALL_EMAIL"] == "reader@example.com"
    assert stored["ESSAY_WRITER_CONSENSUS_PAID"] == "1"


def test_a_first_setup_with_only_the_openalex_key_still_warns(tmp_path, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_ROOT", str(tmp_path / "ledger"))
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", tmp_path / "missing-cloud")
    draft = essay_setup(
        app_path=str(tmp_path / "app"),
        kb1_path=str(tmp_path / "KB1"),
        confirmPhase="draft",
        openalex_api_key="openalex-key",
    )
    assert draft["search_warning"]
    assert draft["skipped_searches"] == ["consensus", "unpaywall"]


def test_setup_preview_sees_an_environment_consensus_key(tmp_path, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_ROOT", str(tmp_path / "ledger"))
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", tmp_path / "missing-cloud")
    monkeypatch.setenv("CONSENSUS_API_KEY", "env-only-key")
    monkeypatch.delenv("ESSAY_WRITER_CONSENSUS", raising=False)
    draft = essay_setup(
        app_path=str(tmp_path / "app"),
        kb1_path=str(tmp_path / "KB1"),
        confirmPhase="draft",
        openalex_api_key="openalex-key",
    )
    # essay.dig will use the environment key, so the preview says it is on.
    assert draft["consensus"]["key_present"] is True
    assert draft["consensus"]["enabled"] is True
    # It is not stored or passed, so setup does not report or record it.
    assert draft["consensus_key"] is False
    assert "env-only-key" not in json.dumps(draft)


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
    assert json.loads((tmp_path / "setup.json").read_text(encoding="utf-8"))["app_path"] == str(
        app.resolve()
    )
    loaded = load_saved_setup()
    assert loaded is not None
    assert loaded["app_path"] == str(app.resolve())
    assert read_setup_secret("CONSENSUS_API_KEY") == key


def test_a_beside_app_record_is_read_when_the_home_record_is_missing(tmp_path, monkeypatch):
    """A record left beside the app by an older confirm is copied home and then read."""
    from essay_writer.paths import load_saved_setup, workspace_root
    from essay_writer.setup import read_setup_secret

    monkeypatch.delenv("ESSAY_WRITER_ROOT", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", tmp_path / "missing-cloud")
    app = tmp_path / "Documents" / "Essay-writer" / "app"
    app.mkdir(parents=True)
    legacy = app.parent / "setup.json"
    legacy.write_text(
        json.dumps({"app_path": str(app.resolve()), "app": str(app.resolve())}),
        encoding="utf-8",
    )
    secret = app.parent / "setup.secrets.json"
    secret.write_text(json.dumps({"CONSENSUS_API_KEY": "legacy-key"}), encoding="utf-8")
    loaded = load_saved_setup()
    assert loaded is not None
    assert loaded["app_path"] == str(app.resolve())
    assert workspace_root() == app.resolve()
    home = tmp_path / ".essay-writer" / "setup.json"
    assert json.loads(home.read_text(encoding="utf-8"))["app_path"] == str(app.resolve())
    assert read_setup_secret("CONSENSUS_API_KEY") == "legacy-key"


def test_install_refuses_the_app_folder_named_on_the_setup_record(tmp_path, monkeypatch):
    from essay_writer.first_run_install import _blocked_dest

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


def test_health_reports_whether_a_unpaywall_email_is_stored(monkeypatch):
    from essay_writer.health import essay_health

    monkeypatch.delenv("ESSAY_WRITER_UNPAYWALL_EMAIL", raising=False)
    monkeypatch.setattr("essay_writer.setup.read_setup_secret", lambda name: None)
    assert essay_health()["unpaywall"] == {"email_present": False}
    monkeypatch.setenv("ESSAY_WRITER_UNPAYWALL_EMAIL", "reader@example.com")
    report = essay_health()
    assert report["unpaywall"] == {"email_present": True}
    assert "reader@example.com" not in json.dumps(report)


def test_cloud_constant_is_the_workspace_root():
    assert CLOUD_WORKSPACE == Path("/workspace")
