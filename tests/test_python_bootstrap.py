"""Interpreter choice and consent for the first install.

No test downloads Python: uv is faked, and the exec is captured.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from essay_writer import python_bootstrap as boot
from essay_writer.first_run import attach_build_mcp, attach_custom_mcp
from essay_writer.health import essay_health


@pytest.fixture(autouse=True)
def _restore_interpreter_env():
    """Keep bootstrap's interpreter choice from leaking into other tests."""

    os.environ.pop("ESSAY_WRITER_INTERPRETER", None)
    yield
    os.environ.pop("ESSAY_WRITER_INTERPRETER", None)


def _exec_calls(record):
    def _exec(path, argv, env):
        record.append((path, argv, env))

    return _exec


def _ok_runner(record):
    def _run(command, cwd, env, timeout):
        record.append(list(command))
        return {"returncode": 0, "stdout": "", "stderr": ""}

    return _run


def test_old_python_without_consent_stops_before_any_install(tmp_path, capsys):
    calls = []
    code = boot.bootstrap(
        [],
        tmp_path,
        exec_fn=_exec_calls(calls),
        current=(3, 12, 13),
        probe=lambda _exe: None,
    )
    report = json.loads(capsys.readouterr().out)
    assert code == 3
    assert report["reason"] == "python_too_old"
    assert report["found"] == "3.12.13"
    assert report["needs_consent"] is True
    assert report["card"] == boot.CARD
    assert calls == []


def test_existing_good_venv_is_used_without_a_card(tmp_path):
    python = boot.venv_python(tmp_path)
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\n", encoding="utf-8")
    calls = []
    commands = []
    code = boot.bootstrap(
        ["--no-reviewer"],
        tmp_path,
        exec_fn=_exec_calls(calls),
        run=_ok_runner(commands),
        current=(3, 12, 13),
        probe=lambda _exe: (3, 15, 2),
    )
    assert code == 0
    assert "mcp.server.mcpserver" in " ".join(commands[0])
    assert len(calls) == 1
    path, argv, env = calls[0]
    assert path == str(python)
    assert argv[1].endswith("first_run.py")
    assert "--no-reviewer" in argv
    assert env["ESSAY_WRITER_INTERPRETER"] == str(python)


def test_consent_provisions_project_local_python(tmp_path):
    calls = []
    commands = []
    code = boot.bootstrap(
        ["--install-python", "--no-reviewer"],
        tmp_path,
        exec_fn=_exec_calls(calls),
        run=_ok_runner(commands),
        uv="/fake/uv",
        current=(3, 12, 13),
        probe=lambda _exe: (3, 15, 2),
    )
    assert code == 0
    joined = [" ".join(command) for command in commands]
    assert any("python install 3.15.2" in line for line in joined)
    assert any("venv .venv --python 3.15.2 --seed" in line for line in joined)
    assert any("pip install -e ." in line for line in joined)
    assert any("mcp.server.mcpserver" in line for line in joined)
    assert (tmp_path / ".python-version").read_text(encoding="utf-8") == "3.15.2\n"
    assert calls[0][0] == str(boot.venv_python(tmp_path))


def test_consent_without_uv_returns_the_install_tip(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("essay_writer._vendor.python_mcp_bootstrap.find_uv", lambda: None)
    calls = []
    code = boot.bootstrap(
        ["--install-python"],
        tmp_path,
        exec_fn=_exec_calls(calls),
        current=(3, 9, 6),
        probe=lambda _exe: None,
    )
    report = json.loads(capsys.readouterr().out)
    assert code == 4
    assert report["reason"] == "needs_uv"
    assert report["tip"] == boot.UV_INSTALL
    assert calls == []


def test_python_override_is_checked_before_use(tmp_path, capsys):
    calls = []
    code = boot.bootstrap(
        ["--python", "/fake/python3.9"],
        tmp_path,
        exec_fn=_exec_calls(calls),
        current=(3, 12, 13),
        probe=lambda _exe: (3, 9, 6),
    )
    report = json.loads(capsys.readouterr().out)
    assert code == 3
    assert report["override"] is True
    assert calls == []

    code = boot.bootstrap(
        ["--python", "/fake/python3.16"],
        tmp_path,
        exec_fn=_exec_calls(calls),
        current=(3, 12, 13),
        probe=lambda _exe: (3, 16, 0),
    )
    assert code == 0
    assert calls[0][0] == "/fake/python3.16"


def test_a_good_running_python_goes_straight_to_the_installer(tmp_path):
    seen = []

    def _main(args):
        seen.append(args)
        return 0

    code = boot.bootstrap(["--no-reviewer"], tmp_path, current=(3, 14, 10), main_fn=_main)
    assert code == 0
    assert seen == [["--no-reviewer"]]


def test_attach_uses_the_chosen_interpreter(tmp_path, monkeypatch):
    python = tmp_path / "python"
    python.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("ESSAY_WRITER_INTERPRETER", str(python))

    project = tmp_path / "project"
    project.mkdir()

    def enable(name):
        return {"identifier": name, "enabled": False}

    cursor = attach_custom_mcp(project, enable=enable)
    assert cursor["ok"] is True
    written = json.loads((project / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
    writer = written["mcpServers"]["essay-writer"]
    reviewer = written["mcpServers"]["essay-reviewer"]
    assert writer == {"command": str(python), "args": ["-m", "essay_writer"]}
    assert reviewer == {"command": str(python), "args": ["-m", "essay_writer", "--reviewer"]}

    build = attach_build_mcp(project, reviewer=True, enable=enable)
    text = Path(build["project_config"]).read_text(encoding="utf-8")
    assert f'command = "{python}"' in text
    assert 'command = "essay-writer"' not in text


def test_health_reports_the_interpreter(workspace):
    report = essay_health()
    assert report["python_version"]
    assert report["python_executable"]
    assert isinstance(report["python_ok"], bool)


@pytest.mark.parametrize("text,expected", [("3.15.2", (3, 15, 2)), ("Python 3.14.10", (3, 14, 10))])
def test_version_text_is_parsed(text, expected):
    assert boot.version_tuple(text) == expected


def test_vendored_core_matches_its_manifest() -> None:
    import hashlib

    vendor = Path(boot.__file__).resolve().parent / "_vendor"
    manifest = json.loads((vendor / "VENDOR.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256((vendor / "python_mcp_bootstrap.py").read_bytes()).hexdigest()
    assert manifest["name"] == "python-mcp-bootstrap"
    assert manifest["version"] == "0.1.0"
    assert manifest["tag"] == "v0.1.0"
    assert manifest["sha256"] == digest
