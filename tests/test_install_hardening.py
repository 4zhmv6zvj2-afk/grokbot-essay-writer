"""Install hardening: the Cursor CLI installer needs consent and never pipes to a shell.

The reviewed behavior piped the downloaded Cursor install script straight into
bash from setup with no consent. These tests pin the replacement: a refusal that
changes nothing, an explicit opt-in, a download to a file whose SHA-256 is
reported, and execution of that file with a fixed argv.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from essay_writer import first_run
from essay_writer.first_run import (
    CURSOR_AGENT_INSTALL_URL,
    CURSOR_AGENT_MANUAL_INSTALL,
    CURSOR_INSTALL_NEEDS_CONSENT,
    CURSOR_INSTALL_SHA256_ENV,
    cursor_install_consent,
    ensure_cursor_agent,
    package_root,
)
from essay_writer.server import first_run_request

INSTALLER_PAYLOAD = b"#!/bin/sh\necho fake-cursor-install\n"

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
    assert list(tmp_path.iterdir()) == []


def test_consent_flag_and_env_both_opt_in(monkeypatch):
    """--install-cursor, --no-install-cursor, and the env var are the documented consent."""
    monkeypatch.delenv("ESSAY_WRITER_ALLOW_CURSOR_INSTALL", raising=False)
    assert cursor_install_consent() is False
    assert first_run._parse(["--install-cursor"])["allow_cursor_install"] is True
    assert first_run._parse(["--no-install-cursor"])["allow_cursor_install"] is False
    assert first_run_request(["--install-cursor"]) is True

    for value in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("ESSAY_WRITER_ALLOW_CURSOR_INSTALL", value)
        assert cursor_install_consent() is True
    for value in ("", "0", "false", "no"):
        monkeypatch.setenv("ESSAY_WRITER_ALLOW_CURSOR_INSTALL", value)
        assert cursor_install_consent() is False


def test_env_consent_runs_the_injected_installer_without_shell(monkeypatch):
    """Env consent is enough; the fake installer records that it ran."""
    _missing_agent(monkeypatch)
    monkeypatch.setenv("ESSAY_WRITER_ALLOW_CURSOR_INSTALL", "1")
    monkeypatch.setattr("essay_writer.first_run._run_cursor_installer", _forbidden("no real download"))
    ran: list[str] = []
    state = {"binary": None}

    def fake():
        ran.append("installer")
        state["binary"] = "/opt/agent"
        return {"returncode": 0}

    monkeypatch.setattr("essay_writer.setup.cursor_cli_binary", lambda: state["binary"])
    monkeypatch.setattr("essay_writer.setup.cursor_cli_version", lambda _path: "agent 1.2.3")

    result = ensure_cursor_agent(installer=fake)
    assert ran == ["installer"]
    assert result["ok"] is True
    assert result["ran_install"] is True


def test_consent_downloads_to_a_file_reports_sha256_and_runs_fixed_argv(monkeypatch):
    """Consent: curl downloads to a file, SHA-256 is recorded, then bash runs that file."""
    _missing_agent(monkeypatch)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    _fixed_which(monkeypatch)
    state = {"binary": None}
    ran: list[dict[str, object]] = []

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
    monkeypatch.setattr("essay_writer.setup.cursor_cli_binary", lambda: state["binary"])
    monkeypatch.setattr("essay_writer.setup.cursor_cli_version", lambda _path: "agent 1.2.3")

    result = ensure_cursor_agent(allow_install=True)

    expected_hash = hashlib.sha256(INSTALLER_PAYLOAD).hexdigest()
    assert result["ran_install"] is True
    assert result["ok"] is True
    assert result["version"] == "agent 1.2.3"
    installer = result["installer"]
    assert installer["sha256"] == expected_hash
    assert installer["url"] == CURSOR_AGENT_INSTALL_URL
    assert installer["returncode"] == 0
    script = Path(str(installer["path"]))
    assert script.is_file()
    assert script.read_bytes() == INSTALLER_PAYLOAD
    assert script.name == "cursor-agent-install.sh"

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


def test_pinned_sha256_refuses_a_mismatched_download(monkeypatch):
    """ESSAY_WRITER_CURSOR_INSTALL_SHA256 turns the recorded hash into an enforced pin."""
    _missing_agent(monkeypatch)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv(CURSOR_INSTALL_SHA256_ENV, "0" * 64)
    _fixed_which(monkeypatch)

    def fake_run(argv, **_kwargs):
        if Path(str(argv[0])).name == "curl":
            Path(str(argv[argv.index("-o") + 1])).write_bytes(INSTALLER_PAYLOAD)

            class Downloaded:
                returncode = 0
                stdout = ""
                stderr = ""

            return Downloaded()
        raise AssertionError("pinned mismatch must not run")

    monkeypatch.setattr("essay_writer.first_run.subprocess.run", fake_run)
    monkeypatch.setattr("essay_writer.setup.cursor_cli_binary", lambda: None)

    result = ensure_cursor_agent(allow_install=True)

    assert result["ok"] is False
    assert result["installer"]["reason"] == "cursor-install-hash-mismatch"
    assert result["installer"]["expected_sha256"] == "0" * 64
    assert result["installer"]["sha256"] == hashlib.sha256(INSTALLER_PAYLOAD).hexdigest()


def test_mac_is_refused_even_with_consent(monkeypatch):
    """Consent never installs the Cursor CLI on the Mac."""
    _missing_agent(monkeypatch)
    monkeypatch.setenv("ESSAY_WRITER_ALLOW_CURSOR_INSTALL", "1")
    monkeypatch.setattr("essay_writer.first_run._on_mac", lambda: True)
    monkeypatch.setattr(
        "essay_writer.first_run._run_cursor_installer",
        _forbidden("never install on the Mac"),
    )
    result = ensure_cursor_agent()
    assert result["reason"] == "mac-no-install"
    assert result["ran_install"] is False


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
