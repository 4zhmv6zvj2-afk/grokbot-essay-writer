"""Install hardening: consent only authorises the download, not execution.

The reviewed behavior piped the downloaded Cursor install script straight into
bash from setup with no consent. These tests pin the replacement: no consent
changes nothing, consent downloads and reports SHA-256 without running, and
execution needs a matching expected SHA-256 with a fixed argv. The same file
pins that secret files are created 0600 before any content exists.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

import pytest

from essay_writer import first_run
from essay_writer.first_run import (
    CURSOR_AGENT_INSTALL_URL,
    CURSOR_AGENT_MANUAL_INSTALL,
    CURSOR_INSTALL_HASH_MISMATCH,
    CURSOR_INSTALL_NEEDS_CONSENT,
    CURSOR_INSTALL_NEEDS_HASH,
    CURSOR_INSTALL_SHA256_ENV,
    cursor_install_consent,
    ensure_cursor_agent,
    package_root,
)
from essay_writer.server import first_run_request

INSTALLER_PAYLOAD = b"#!/bin/sh\necho fake-cursor-install\n"
INSTALLER_SHA = hashlib.sha256(INSTALLER_PAYLOAD).hexdigest()

CURL = "/usr/bin/curl"
BASH = "/usr/bin/bash"


def _missing_agent(monkeypatch) -> None:
    """No agent on disk and not the Mac, so the consent branch is reachable."""
    monkeypatch.setattr("essay_writer.first_run._on_mac", lambda: False)
    monkeypatch.setattr("essay_writer.setup.cursor_cli_binary", lambda: None)
    monkeypatch.delenv("ESSAY_WRITER_ALLOW_CURSOR_INSTALL", raising=False)
    monkeypatch.delenv(CURSOR_INSTALL_SHA256_ENV, raising=False)


def _fixed_which(monkeypatch) -> None:
    """Deterministic curl and bash paths, so these tests do not depend on the host."""
    monkeypatch.setattr("essay_writer.first_run.shutil.which", lambda name: f"/usr/bin/{name}")


def _downloader(monkeypatch, state: dict, ran: list[dict]) -> None:
    """Fake subprocess.run: curl writes the payload; bash records and installs."""

    def fake_run(argv, **kwargs):
        ran.append({"argv": list(argv), "kwargs": kwargs})
        if Path(str(argv[0])).name == "curl":
            Path(str(argv[argv.index("-o") + 1])).write_bytes(INSTALLER_PAYLOAD)
        else:
            state["binary"] = "/opt/cursor-agent"

        class Completed:
            returncode = 0
            stdout = "installed"
            stderr = ""

        return Completed()

    monkeypatch.setattr("essay_writer.first_run.subprocess.run", fake_run)


def _working_agent(monkeypatch, state: dict) -> None:
    monkeypatch.setattr("essay_writer.setup.cursor_cli_binary", lambda: state["binary"])
    monkeypatch.setattr("essay_writer.setup.cursor_cli_version", lambda _path: "agent 1.2.3")


def test_no_consent_downloads_nothing_and_changes_nothing(monkeypatch, tmp_path):
    """No consent: no download, no exec, no temp file, and manual install guidance."""
    _missing_agent(monkeypatch)
    monkeypatch.setattr(
        "essay_writer.first_run.subprocess.run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no exec without consent")),
    )
    monkeypatch.setattr(
        "essay_writer.first_run.tempfile.mkdtemp",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no temp file without consent")),
    )
    monkeypatch.setenv("TMPDIR", str(tmp_path))

    result = ensure_cursor_agent()

    assert result["reason"] == CURSOR_INSTALL_NEEDS_CONSENT
    assert result["consent_required"] is True
    assert result["ran_install"] is False
    assert result["downloaded"] is False
    assert result["manual_install"] == CURSOR_AGENT_MANUAL_INSTALL
    assert "curl -fsS " in result["manual_install"]
    assert "| bash" not in result["manual_install"]
    assert "--cursor-sha256" in result["residual"]
    assert list(tmp_path.iterdir()) == []


def test_consent_flag_env_and_hash_flag_are_parsed(monkeypatch):
    """--install-cursor, the env consent, and --cursor-sha256 are the documented switches."""
    monkeypatch.delenv("ESSAY_WRITER_ALLOW_CURSOR_INSTALL", raising=False)
    assert cursor_install_consent() is False
    assert first_run._parse(["--install-cursor"])["allow_cursor_install"] is True
    assert first_run._parse(["--no-install-cursor"])["allow_cursor_install"] is False
    assert first_run_request(["--install-cursor"]) is True
    assert first_run_request(["--cursor-sha256", "a" * 64]) is True

    parsed = first_run._parse(["--install-cursor", "--cursor-sha256", "A" * 64])
    assert parsed["cursor_sha256"] == "a" * 64
    assert parsed["allow_cursor_install"] is True

    for bad in ("not-a-hash", "a" * 63, "g" * 64):
        with pytest.raises(ValueError):
            first_run._parse(["--cursor-sha256", bad])
    with pytest.raises(ValueError):
        first_run._parse(["--cursor-sha256"])

    for value in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("ESSAY_WRITER_ALLOW_CURSOR_INSTALL", value)
        assert cursor_install_consent() is True
    for value in ("", "0", "false", "no"):
        monkeypatch.setenv("ESSAY_WRITER_ALLOW_CURSOR_INSTALL", value)
        assert cursor_install_consent() is False


def test_env_consent_runs_the_injected_installer_without_shell(monkeypatch):
    """Env consent is enough for the test seam; the fake installer records that it ran."""
    _missing_agent(monkeypatch)
    monkeypatch.setenv("ESSAY_WRITER_ALLOW_CURSOR_INSTALL", "1")
    monkeypatch.setattr("essay_writer.first_run._run_cursor_installer", _forbidden("no real download"))
    ran: list[str] = []
    state = {"binary": None}

    def fake():
        ran.append("installer")
        state["binary"] = "/opt/agent"
        return {"returncode": 0}

    _working_agent(monkeypatch, state)

    result = ensure_cursor_agent(installer=fake)
    assert ran == ["installer"]
    assert result["ok"] is True
    assert result["ran_install"] is True


def test_consent_without_expected_hash_downloads_but_never_executes(monkeypatch):
    """Consent downloads and reports the hash; without a pin it stops needs-hash."""
    _missing_agent(monkeypatch)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    _fixed_which(monkeypatch)
    state = {"binary": None}
    ran: list[dict] = []
    _downloader(monkeypatch, state, ran)
    monkeypatch.setattr("essay_writer.setup.cursor_cli_binary", lambda: None)

    result = ensure_cursor_agent(allow_install=True)

    assert result["ok"] is False
    assert result["reason"] == CURSOR_INSTALL_NEEDS_HASH
    installer = result["installer"]
    assert installer["reason"] == CURSOR_INSTALL_NEEDS_HASH
    assert installer["executed"] is False
    assert installer["sha256"] == INSTALLER_SHA
    assert installer["bytes"] == len(INSTALLER_PAYLOAD)
    assert INSTALLER_SHA in installer["instruction"]
    assert "--cursor-sha256" in installer["instruction"]
    script = Path(str(installer["path"]))
    assert script.is_file()
    assert script.read_bytes() == INSTALLER_PAYLOAD
    assert [run["argv"][0] for run in ran] == [CURL]
    assert all(run["kwargs"]["shell"] is False for run in ran)


def test_matching_expected_hash_runs_the_downloaded_file_with_fixed_argv(monkeypatch):
    """A matching --cursor-sha256 runs the downloaded file with no shell."""
    _missing_agent(monkeypatch)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    _fixed_which(monkeypatch)
    state = {"binary": None}
    ran: list[dict] = []
    _downloader(monkeypatch, state, ran)
    _working_agent(monkeypatch, state)

    result = ensure_cursor_agent(allow_install=True, expected_sha256=INSTALLER_SHA)

    assert result["ok"] is True
    assert result["ran_install"] is True
    assert result["version"] == "agent 1.2.3"
    installer = result["installer"]
    assert installer["sha256"] == INSTALLER_SHA
    assert installer["expected_sha256"] == INSTALLER_SHA
    assert installer["executed"] is True
    assert installer["url"] == CURSOR_AGENT_INSTALL_URL
    assert installer["returncode"] == 0
    script = Path(str(installer["path"]))
    assert script.name == "cursor-agent-install.sh"
    assert script.read_bytes() == INSTALLER_PAYLOAD

    assert [run["argv"][0] for run in ran] == [CURL, BASH]
    download_argv = ran[0]["argv"]
    assert download_argv == [
        CURL,
        "-fsS",
        "--proto",
        "=https",
        "--max-time",
        "60",
        CURSOR_AGENT_INSTALL_URL,
        "-o",
        str(script),
    ]
    exec_argv = ran[1]["argv"]
    assert exec_argv == [BASH, str(script)]
    for run in ran:
        assert run["kwargs"]["shell"] is False
        assert not any("|" in str(part) for part in run["argv"])
    assert "-lc" not in exec_argv


def test_env_hash_pin_also_authorises_execution(monkeypatch):
    """ESSAY_WRITER_CURSOR_INSTALL_SHA256 is the documented env form of the pin."""
    _missing_agent(monkeypatch)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv(CURSOR_INSTALL_SHA256_ENV, INSTALLER_SHA)
    _fixed_which(monkeypatch)
    state = {"binary": None}
    ran: list[dict] = []
    _downloader(monkeypatch, state, ran)
    _working_agent(monkeypatch, state)

    result = ensure_cursor_agent(allow_install=True)

    assert result["ok"] is True
    assert result["installer"]["executed"] is True
    assert [run["argv"][0] for run in ran] == [CURL, BASH]


def test_mismatched_expected_hash_does_not_execute(monkeypatch):
    """A wrong expected SHA-256 reports the mismatch and runs nothing."""
    _missing_agent(monkeypatch)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    _fixed_which(monkeypatch)

    def fake_run(argv, **_kwargs):
        if Path(str(argv[0])).name == "curl":
            Path(str(argv[argv.index("-o") + 1])).write_bytes(INSTALLER_PAYLOAD)

            class Downloaded:
                returncode = 0
                stdout = ""
                stderr = ""

            return Downloaded()
        raise AssertionError("a hash mismatch must not run")

    monkeypatch.setattr("essay_writer.first_run.subprocess.run", fake_run)
    monkeypatch.setattr("essay_writer.setup.cursor_cli_binary", lambda: None)

    result = ensure_cursor_agent(allow_install=True, expected_sha256="0" * 64)

    assert result["ok"] is False
    assert result["reason"] == CURSOR_INSTALL_HASH_MISMATCH
    assert result["installer"]["reason"] == CURSOR_INSTALL_HASH_MISMATCH
    assert result["installer"]["executed"] is False
    assert result["installer"]["expected_sha256"] == "0" * 64
    assert result["installer"]["sha256"] == INSTALLER_SHA
    assert result["installer"]["bytes"] == len(INSTALLER_PAYLOAD)


def test_an_invalid_expected_hash_is_not_a_pin(monkeypatch):
    """A malformed pin is ignored, so execution still waits for a real hash."""
    _missing_agent(monkeypatch)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    _fixed_which(monkeypatch)
    state = {"binary": None}
    ran: list[dict] = []
    _downloader(monkeypatch, state, ran)
    monkeypatch.setattr("essay_writer.setup.cursor_cli_binary", lambda: None)

    result = ensure_cursor_agent(allow_install=True, expected_sha256="not-a-sha")

    assert result["reason"] == CURSOR_INSTALL_NEEDS_HASH
    assert [run["argv"][0] for run in ran] == [CURL]


def test_missing_curl_refuses_without_running_anything(monkeypatch):
    """No curl means no download, no exec, and a named reason."""
    _missing_agent(monkeypatch)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr("essay_writer.first_run.shutil.which", lambda _name: None)
    monkeypatch.setattr(
        "essay_writer.first_run.subprocess.run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    result = ensure_cursor_agent(allow_install=True)
    assert result["ok"] is False
    assert result["installer"]["reason"] == "cursor-install-curl-missing"
    assert result["ran_install"] is True


def test_mac_is_refused_even_with_consent_and_hash(monkeypatch):
    """Consent and a hash never install the Cursor CLI on the Mac."""
    _missing_agent(monkeypatch)
    monkeypatch.setenv("ESSAY_WRITER_ALLOW_CURSOR_INSTALL", "1")
    monkeypatch.setattr("essay_writer.first_run._on_mac", lambda: True)
    monkeypatch.setattr(
        "essay_writer.first_run._run_cursor_installer",
        _forbidden("never install on the Mac"),
    )
    result = ensure_cursor_agent(expected_sha256=INSTALLER_SHA)
    assert result["reason"] == "mac-no-install"
    assert result["ran_install"] is False


def test_install_uploaded_copy_plumbs_the_expected_hash(monkeypatch, tmp_path):
    """The first-run install path hands --cursor-sha256 to the installer."""
    seen: dict[str, object] = {}

    def fake_ensure(installer=None, *, allow_install=None, expected_sha256=None):
        seen["allow_install"] = allow_install
        seen["expected_sha256"] = expected_sha256
        return {"ok": False, "reason": CURSOR_INSTALL_NEEDS_HASH}

    monkeypatch.setattr("essay_writer.first_run.ensure_cursor_agent", fake_ensure)
    monkeypatch.setattr("essay_writer.first_run.expose_writer_on_path", lambda: None)
    monkeypatch.setattr(
        "essay_writer.first_run.install_self_check",
        lambda: {"ok": True, "tool": "essay.health"},
    )
    monkeypatch.setattr(
        "essay_writer.first_run.attach_friend_upgrade_fo_card",
        lambda payload, **_kwargs: payload,
    )
    source = tmp_path / "tree"
    source.mkdir()
    (source / "pyproject.toml").write_text(
        '[project]\nname = "essay-writer"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (source / "FIRST-RUN.txt").write_text("prompt", encoding="utf-8")

    result = first_run.install_uploaded_copy(
        source,
        pip_runner=lambda _command, _cwd: {"returncode": 0, "stdout": "", "stderr": ""},
        attach=False,
        cursor_installer=lambda: {"returncode": 0},
        allow_cursor_install=True,
        cursor_sha256=INSTALLER_SHA,
    )

    assert result["ok"] is True
    assert seen == {"allow_install": True, "expected_sha256": INSTALLER_SHA}


def test_pip_install_report_keeps_the_needs_consent_reason(monkeypatch, tmp_path):
    """The install report carries the structured reason instead of installing silently."""
    _missing_agent(monkeypatch)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr("essay_writer.first_run._run_pip", lambda _cmd, _cwd: {"returncode": 0})
    monkeypatch.setattr("essay_writer.first_run.expose_writer_on_path", lambda: None)
    monkeypatch.setattr("essay_writer.first_run.attach_custom_mcp", lambda *a, **k: None)
    monkeypatch.setattr("essay_writer.first_run.attach_build_mcp", lambda *a, **k: None)
    monkeypatch.setattr(
        "essay_writer.first_run.install_self_check",
        lambda: {"ok": True, "tool": "essay.health"},
    )
    monkeypatch.setattr(
        "essay_writer.first_run.attach_friend_upgrade_fo_card",
        lambda payload, **_kwargs: payload,
    )
    source = tmp_path / "tree"
    source.mkdir()
    (source / "pyproject.toml").write_text(
        '[project]\nname = "essay-writer"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (source / "FIRST-RUN.txt").write_text("prompt", encoding="utf-8")

    result = first_run.install_uploaded_copy(
        source,
        pip_runner=lambda _command, _cwd: {"returncode": 0, "stdout": "", "stderr": ""},
        attach=False,
    )

    assert result["ok"] is True
    assert result["cursor_cli"]["reason"] == CURSOR_INSTALL_NEEDS_CONSENT
    assert result["cursor_cli"]["ran_install"] is False
    assert result["cursor_cli"]["manual_install"] == CURSOR_AGENT_MANUAL_INSTALL


def test_secret_file_helper_creates_0600_before_writing(tmp_path, monkeypatch):
    """The secret helper passes 0600 at creation and tightens an existing file."""
    from essay_writer.setup import _write_secret_text

    target = tmp_path / "setup.secrets.json"
    modes: list[int] = []
    real_open = os.open

    def spy_open(path, flags, mode=0o777):
        modes.append(mode)
        return real_open(path, flags, mode)

    monkeypatch.setattr("essay_writer.setup.os.open", spy_open)

    _write_secret_text(target, '{"a": "b"}\n')

    assert modes == [0o600]
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert target.read_text(encoding="utf-8") == '{"a": "b"}\n'

    target.chmod(0o644)
    _write_secret_text(target, '{"c": "d"}\n')

    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert target.read_text(encoding="utf-8") == '{"c": "d"}\n'


def test_optional_secrets_are_created_0600(tmp_path, monkeypatch):
    """essay.setup writes setup.secrets.json at 0600 through the helper."""
    from essay_writer.setup import essay_setup

    monkeypatch.setenv("ESSAY_WRITER_ROOT", str(tmp_path / "ledger"))
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", tmp_path / "missing-cloud")
    arguments = {
        "app_path": str(tmp_path / "app"),
        "kb1_path": str(tmp_path / "KB1"),
        "consensus_api_key": "consensus-value",
        "unpaywall_email": "reader@example.com",
        "consensus_plan": "pro",
    }
    draft = essay_setup(confirmPhase="draft", **arguments)
    assert draft["ok"] is True
    result = essay_setup(confirmPhase="confirm", **arguments)

    assert result["wrote"] is True
    secret = tmp_path / "setup.secrets.json"
    assert stat.S_IMODE(secret.stat().st_mode) == 0o600
    assert json.loads(secret.read_text(encoding="utf-8"))["CONSENSUS_API_KEY"] == "consensus-value"


def test_mac_handoff_store_is_created_0600(tmp_path, monkeypatch):
    """The remembered Mac folder store is a secret file at 0600."""
    cloud = tmp_path / "workspace"
    cloud.mkdir()
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", cloud)
    monkeypatch.delenv("ESSAY_WRITER_MAC_DIR", raising=False)
    folder = tmp_path / "Documents" / "Essay Bot"

    remembered = first_run.remember_mac_handoff_dir(folder)

    assert remembered["ok"] is True
    secret = cloud / "Essay-writer" / "setup.secrets.json"
    assert secret.is_file()
    assert stat.S_IMODE(secret.stat().st_mode) == 0o600
    assert json.loads(secret.read_text(encoding="utf-8"))["ESSAY_WRITER_MAC_DIR"] == str(
        folder.resolve()
    )


def test_no_pipe_to_shell_anywhere_in_shipped_source():
    """No shipped src file pipes a remote script into a shell, and the prompt is not an exception."""
    offenders = []
    for path in (package_root() / "src").rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.suffix not in {".py", ".txt", ".md", ".toml", ".json"}:
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        if "| bash" in body or "| sh" in body:
            offenders.append(str(path))
    assert offenders == []


def _forbidden(message: str):
    def refused(*_args, **_kwargs):
        raise AssertionError(message)

    return refused
