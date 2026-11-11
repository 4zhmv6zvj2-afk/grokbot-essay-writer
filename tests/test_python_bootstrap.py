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
        current=(3, 11, 13),
        probe=lambda _exe: None,
    )
    report = json.loads(capsys.readouterr().out)
    assert code == 3
    assert report["reason"] == "python_too_old"
    assert report["found"] == "3.11.13"
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
        current=(3, 11, 13),
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
    (tmp_path / "requirements-runtime.txt").write_text(
        "mcp==2.3.0 --hash=sha256:" + "0" * 64 + "\n", encoding="utf-8"
    )
    calls = []
    commands = []
    code = boot.bootstrap(
        ["--install-python", "--no-reviewer"],
        tmp_path,
        exec_fn=_exec_calls(calls),
        run=_ok_runner(commands),
        uv="/fake/uv",
        current=(3, 11, 13),
        probe=lambda _exe: (3, 15, 2),
    )
    assert code == 0
    python = str(boot.venv_python(tmp_path))
    joined = [" ".join(command) for command in commands]
    assert any("python install 3.15.2" in line for line in joined)
    assert any("venv .venv --python 3.15.2 --seed" in line for line in joined)
    # The vendored core installs the hash-pinned requirements first, then the
    # project with --no-deps. There is no single unpinned install.
    requirements = [line for line in joined if "--require-hashes" in line]
    assert len(requirements) == 1
    assert "requirements-runtime.txt" in requirements[0]
    assert any(f"pip install --python {python} --no-deps -e ." in line for line in joined)
    assert not any(f"pip install --python {python} -e ." in line for line in joined)
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
        run=_ok_runner([]),
        current=(3, 12, 13),
        probe=lambda _exe: (3, 16, 0),
    )
    assert code == 0
    assert calls[0][0] == "/fake/python3.16"


def test_python_override_with_a_broken_import_is_refused(tmp_path, capsys):
    """An explicit interpreter is verified: a broken import is exit 5, not a re-exec."""
    calls = []

    def _failed_runner(command, cwd, env, timeout):
        return {"returncode": 1, "stdout": "", "stderr": "ModuleNotFoundError"}

    code = boot.bootstrap(
        ["--python", "/fake/python3.16"],
        tmp_path,
        exec_fn=_exec_calls(calls),
        run=_failed_runner,
        current=(3, 12, 13),
        probe=lambda _exe: (3, 16, 0),
    )
    report = json.loads(capsys.readouterr().out)
    assert code == 5
    assert report["reason"] == "verify_import_failed"
    assert report["override"] is True
    assert calls == []


def test_a_good_running_python_goes_straight_to_the_installer(tmp_path):
    seen = []

    def _main(args):
        seen.append(args)
        return 0

    code = boot.bootstrap(["--no-reviewer"], tmp_path, current=(3, 14, 10), main_fn=_main)
    assert code == 0
    assert seen == [["--no-reviewer"]]


def test_running_python_3_12_13_meets_the_floor(tmp_path):
    """The floor is 3.12.0: a running 3.12.13 is accepted without consent."""
    seen = []

    def _main(args):
        seen.append(args)
        return 0

    code = boot.bootstrap(["--no-reviewer"], tmp_path, current=(3, 12, 13), main_fn=_main)
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

    cursor = attach_custom_mcp(project, enable=enable, include_user=False)
    assert cursor["ok"] is True
    written = json.loads((project / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
    writer = written["mcpServers"]["essay-writer"]
    reviewer = written["mcpServers"]["essay-reviewer"]
    assert writer == {"command": str(python), "args": ["-m", "essay_writer"]}
    assert reviewer == {"command": str(python), "args": ["-m", "essay_writer", "--reviewer"]}

    build = attach_build_mcp(project, reviewer=True, enable=enable, include_user=False)
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
    assert manifest["version"] == "0.2.0"
    assert manifest["tag"] == "v0.2.0"
    assert manifest["commit"].startswith("fd8e0b9")
    assert manifest["sha256"] == digest
    assert "local_patch" not in manifest


def test_hash_pinned_requirements_install_runs_before_the_project(tmp_path):
    """A copy with requirements-runtime.txt installs hashes first, then --no-deps."""
    (tmp_path / "requirements-runtime.txt").write_text(
        "mcp==2.3.0 --hash=sha256:" + "0" * 64 + "\n", encoding="utf-8"
    )
    calls = []
    commands = []
    code = boot.bootstrap(
        ["--install-python", "--no-reviewer"],
        tmp_path,
        exec_fn=_exec_calls(calls),
        run=_ok_runner(commands),
        uv="/fake/uv",
        current=(3, 11, 13),
        probe=lambda _exe: (3, 15, 2),
    )
    assert code == 0
    python = str(boot.venv_python(tmp_path))
    joined = [" ".join(command) for command in commands]
    requirements = [line for line in joined if "--require-hashes" in line]
    project = [line for line in joined if f"pip install --python {python} --no-deps -e ." in line]
    assert len(requirements) == 1
    assert "requirements-runtime.txt" in requirements[0]
    assert requirements[0].endswith(f"--python {python}")
    assert len(project) == 1
    assert joined.index(requirements[0]) < joined.index(project[0])


def test_missing_requirements_file_fails_closed_without_an_unpinned_install(tmp_path, capsys):
    """A copy without requirements-runtime.txt is refused; no unpinned install runs."""
    commands = []
    code = boot.bootstrap(
        ["--install-python", "--no-reviewer"],
        tmp_path,
        exec_fn=_exec_calls([]),
        run=_ok_runner(commands),
        uv="/fake/uv",
        current=(3, 11, 13),
        probe=lambda _exe: (3, 15, 2),
    )
    report = json.loads(capsys.readouterr().out)
    assert code == 5
    assert report["reason"] == "runtime_requirements_failed"
    assert report["steps"][-1]["returncode"] == 1
    assert "requirements-runtime.txt is missing" in report["steps"][-1]["stderr"]
    joined = [" ".join(command) for command in commands]
    python = str(boot.venv_python(tmp_path))
    assert not any(f"pip install --python {python} --no-deps -e ." in line for line in joined)
    assert not any(f"pip install --python {python} -e ." in line for line in joined)


def test_failed_requirement_hash_install_stops_before_the_project(tmp_path, capsys):
    """A failed hash check is a named failure; the project install does not run."""
    (tmp_path / "requirements-runtime.txt").write_text("mcp==2.3.0\n", encoding="utf-8")
    commands = []

    def _runner(command, cwd, env, timeout):
        commands.append(list(command))
        if "--require-hashes" in command:
            return {"returncode": 1, "stdout": "", "stderr": "hash mismatch"}
        return {"returncode": 0, "stdout": "", "stderr": ""}

    code = boot.bootstrap(
        ["--install-python", "--no-reviewer"],
        tmp_path,
        exec_fn=_exec_calls([]),
        run=_runner,
        uv="/fake/uv",
        current=(3, 11, 13),
        probe=lambda _exe: (3, 15, 2),
    )
    report = json.loads(capsys.readouterr().out)
    assert code != 0
    assert report["reason"] == "runtime_requirements_failed"
    python = str(boot.venv_python(tmp_path))
    assert not any(f"--python {python} --no-deps -e ." in " ".join(command) for command in commands)


def test_bootstrap_spec_rejects_requirements_outside_the_project():
    """The new field uses the same project-path guard as the other paths."""
    from essay_writer._vendor import python_mcp_bootstrap as core

    with pytest.raises(ValueError, match="requirements must stay inside the project"):
        core.BootstrapSpec(app="essay-writer", requirements=("/etc/passwd",))


def test_provision_refuses_a_missing_requirements_file(tmp_path):
    """The adapter refuses before touching uv; the reason is named."""
    report = boot.provision(tmp_path, run=lambda *_a, **_k: {"returncode": 0})
    assert report["ok"] is False
    assert report["reason"] == "requirements_missing"
    assert boot._SPEC.requirements == (boot.REQUIREMENTS_FILE,)
