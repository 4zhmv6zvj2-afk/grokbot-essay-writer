"""Stage-3.5 hygiene: platform guard, state lock, legacy setup, intake parity."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"


def _env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(part for part in (str(SRC), existing) if part)
    return env


def _run(code: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code, *args],
        cwd=REPO,
        env=_env(),
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_stage_state_imports_without_fcntl_and_names_the_platform():
    """Windows can import the package; only taking a lock refuses, by name."""
    code = """
import sys
sys.modules["fcntl"] = None
from essay_writer import stage_state

assert stage_state.fcntl is None
try:
    stage_state.require_fcntl()
except RuntimeError as exc:
    text = str(exc)
    assert "fcntl" in text
    assert sys.platform in text
else:
    raise AssertionError("the missing fcntl guard did not raise")

try:
    with stage_state.stage_lock("MOD1004AA"):
        pass
except RuntimeError as exc:
    assert "fcntl" in str(exc)
else:
    raise AssertionError("the stage lock did not name the platform")
print("ok")
"""
    result = _run(code)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


def test_stage_lock_guard_when_fcntl_is_absent(workspace, monkeypatch):
    from essay_writer import stage_state

    monkeypatch.setattr(stage_state, "fcntl", None)
    # A fresh sequence has no pointer or journal, so reading it takes no lock.
    assert stage_state.load_pointer("MOD1004AA")["current"] == "1"
    with pytest.raises(RuntimeError, match="fcntl"):
        stage_state.require_fcntl()
    with pytest.raises(RuntimeError, match="fcntl"):
        with stage_state.stage_lock("MOD1004AA"):
            pass


def test_state_lock_is_exclusive_across_processes(workspace):
    pytest.importorskip("fcntl")
    from essay_writer.state import state_lock

    lock_path = workspace / "Essay-writer" / "MOD1004AA" / "state.json.lock"
    child = """
import fcntl
import sys

handle = open(sys.argv[1], "a+")
try:
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    sys.exit(0)
else:
    sys.exit(2)
"""
    with state_lock("MOD1004AA"):
        assert lock_path.is_file()
        blocked = _run(child, str(lock_path))
        assert blocked.returncode == 0, blocked.stderr
    released = _run(child, str(lock_path))
    assert released.returncode == 2, released.stderr


class _RecordingFcntl:
    LOCK_EX = 2
    LOCK_UN = 8

    def __init__(self) -> None:
        self.calls: list[int] = []

    def flock(self, descriptor: int, operation: int) -> None:
        self.calls.append(operation)


def test_save_state_takes_the_lock_and_writes_one_atomic_record(workspace, monkeypatch):
    from essay_writer import stage_state
    from essay_writer.state import load_state, save_state, state_lock

    recorder = _RecordingFcntl()
    monkeypatch.setattr(stage_state, "fcntl", recorder)
    state = {"essay_id": "MOD1004AA", "shelf": {"kept": True}}
    save_state("MOD1004AA", state)

    assert recorder.calls == [recorder.LOCK_EX, recorder.LOCK_UN]
    path = workspace / "Essay-writer" / "MOD1004AA" / "state.json"
    assert json.loads(path.read_text(encoding="utf-8")) == state
    assert (path.parent / "state.json.lock").is_file()
    assert list(path.parent.glob(".*state.json.*.tmp")) == []
    assert load_state("MOD1004AA")["shelf"] == {"kept": True}

    # The documented load-modify-save pattern holds the same lock, and the
    # write inside it re-enters rather than deadlocking.
    with state_lock("MOD1004AA"):
        nested = load_state("MOD1004AA")
        nested["shelf"]["nested"] = True
        save_state("MOD1004AA", nested)
    assert load_state("MOD1004AA")["shelf"]["nested"] is True


def _local_home(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ESSAY_WRITER_ROOT", raising=False)
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", tmp_path / "no-cloud")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))


def _legacy_record(app: Path, *, api_key: str | None = None) -> Path:
    app.mkdir(parents=True)
    record = app.parent / "setup.json"
    record.write_text(
        json.dumps({"app_path": str(app.resolve()), "app": str(app.resolve())}),
        encoding="utf-8",
    )
    if api_key is not None:
        (app.parent / "setup.secrets.json").write_text(
            json.dumps({"CONSENSUS_API_KEY": api_key}),
            encoding="utf-8",
        )
    return record


def test_legacy_setup_is_adopted_for_a_named_product_folder(tmp_path, monkeypatch):
    _local_home(tmp_path, monkeypatch)
    app = tmp_path / "Documents" / "Essay-writer" / "app"
    _legacy_record(app, api_key="old-key")

    from essay_writer.paths import load_saved_setup, resolve_setup_record, workspace_root

    home_record = tmp_path / ".essay-writer" / "setup.json"
    assert resolve_setup_record() == home_record
    assert json.loads(home_record.read_text(encoding="utf-8"))["app_path"] == str(app.resolve())
    secret = home_record.parent / "setup.secrets.json"
    assert json.loads(secret.read_text(encoding="utf-8"))["CONSENSUS_API_KEY"] == "old-key"
    assert load_saved_setup() is not None
    assert load_saved_setup()["app_path"] == str(app.resolve())
    assert workspace_root() == app.resolve()


def test_legacy_setup_is_adopted_beside_a_product_checkout(tmp_path, monkeypatch):
    _local_home(tmp_path, monkeypatch)
    checkout = tmp_path / "code" / "checkout"
    app = checkout / "app"
    _legacy_record(app)
    (checkout / "pyproject.toml").write_text('[project]\nname = "essay-writer"\n', encoding="utf-8")
    (checkout / "src" / "essay_writer").mkdir(parents=True)

    from essay_writer.paths import load_saved_setup

    loaded = load_saved_setup()
    assert loaded is not None
    assert loaded["app_path"] == str(app.resolve())


def test_legacy_setup_for_an_unrelated_home_folder_is_refused(tmp_path, monkeypatch):
    _local_home(tmp_path, monkeypatch)
    app = tmp_path / "Documents" / "local-writer" / "app"
    _legacy_record(app, api_key="attacker-key")

    from essay_writer.paths import load_saved_setup, resolve_setup_record

    assert resolve_setup_record() is None
    assert not (tmp_path / ".essay-writer" / "setup.json").exists()
    assert load_saved_setup() is None


def test_essay_intake_mount_and_front_office_share_the_no_photo_shape(workspace):
    from essay_writer.server import intake_with_image
    from essay_writer.shells import front_office_call, mount_handler

    holding = workspace / "unassigned"
    holding.mkdir(exist_ok=True)
    (holding / "brief.md").write_text(
        "# Brief\n\nWrite a report on household recycling.\n",
        encoding="utf-8",
    )
    arguments = {"name": "brief.md", "confirmPhase": "draft", "module": "MOD1004AA"}

    mounted = mount_handler("essay.intake")
    assert mounted is intake_with_image
    assert "essay_intake" in intake_with_image.__code__.co_names
    reply = mounted(**arguments)
    spoken = front_office_call("essay.intake", dict(arguments))

    assert isinstance(reply, dict)
    assert isinstance(spoken, dict)
    assert set(reply) == set(spoken)
    for key in ("ok", "essay_id", "kind", "confirmPhase", "wrote", "stored", "digest", "sha256"):
        assert reply[key] == spoken[key]
    # Intended exception: the mount returns the door body verbatim, while the
    # front office cleans learner-facing speech. Only the `next` wording moves.
    assert isinstance(reply["next"], str) and reply["next"]
    assert isinstance(spoken["next"], str) and spoken["next"]


def test_pyproject_declares_posix_and_keeps_the_existing_classifiers():
    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    classifiers = data["project"]["classifiers"]
    assert "Operating System :: POSIX" in classifiers
    assert "Development Status :: 4 - Beta" in classifiers
    assert "Programming Language :: Python :: 3.12" in classifiers
