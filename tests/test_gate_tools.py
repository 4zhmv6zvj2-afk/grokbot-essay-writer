"""Stamp and tag refusals, with git and the suite faked.

These tests do not run pytest, ruff, mypy, or the network. ``tag_release``
reads a stamp file and the git commands the fake records.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, filename: str):
    path = ROOT / "tools" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


tag_release = _load("_essay_writer_tag_release", "tag_release.py")
run_gates = tag_release.run_gates

HEAD = "e21f6ed9053afc9cafbd5fd792732dcc1984b2db"
OTHER = "0000000000000000000000000000000000000001"
NOW = datetime(2026, 11, 24, 4, 10, tzinfo=timezone(timedelta(hours=8)))
VERSIONS = {"python": "3.15.2", "ruff": "0.17.4", "mypy": "2.4.1"}


@pytest.fixture
def git_box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    git_dir = tmp_path / "gitdir"
    repo = tmp_path / "repo"
    git_dir.mkdir()
    repo.mkdir()
    recorded: list[list[str]] = []
    state = {
        "git_dir": git_dir,
        "repo": repo,
        "recorded": recorded,
        "dirty": False,
        "head": HEAD,
        "docs_code": 0,
        "docs_output": "ok\n",
        "tag_exists": False,
        "remote_tag": "",
        "fail_unknown": True,
    }

    def fake(
        args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None
    ) -> tuple[int, str]:
        recorded.append(list(args))
        if args == ["git", "rev-parse", "--show-toplevel"]:
            return 0, f"{repo}\n"
        if args == ["git", "rev-parse", "--git-dir"]:
            return 0, f"{git_dir}\n"
        if args == ["git", "status", "--porcelain"]:
            return 0, " M src/essay_writer/dig.py\n" if state["dirty"] else ""
        if args == ["git", "rev-parse", "HEAD"]:
            return 0, f"{state['head']}\n"
        if args == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return 0, "p05-local-gate\n"
        if args[:3] == ["git", "rev-parse", "--verify"]:
            return (0, f"{HEAD}\n") if state["tag_exists"] else (1, "")
        if args[:3] == ["git", "ls-remote", "--tags"]:
            return 0, str(state["remote_tag"])
        if args[:3] == ["git", "tag", "-a"]:
            return 0, ""
        if any(token.endswith("generate_docs.py") for token in args):
            return int(state["docs_code"]), str(state["docs_output"])
        if args and args[0] != "git":
            if state["fail_unknown"]:
                raise AssertionError(args)
            return 0, "ok\n"
        raise AssertionError(args)

    monkeypatch.setattr(run_gates, "command", fake)
    monkeypatch.setattr(run_gates, "now", lambda: NOW)
    monkeypatch.setattr(run_gates, "current_versions", lambda: dict(VERSIONS))
    monkeypatch.setattr(tag_release, "version_check", lambda tag, root: (0, ""))
    return state


def _write_stamp(git_dir: Path, **overrides: object) -> None:
    steps = {name: "pass" for name in run_gates.FULL_STEPS}
    body: dict[str, object] = {
        "head_sha": HEAD,
        "branch": "p05-local-gate",
        "mode": "full",
        "clean": True,
        "when": NOW.isoformat(),
        "python": VERSIONS["python"],
        "ruff": VERSIONS["ruff"],
        "mypy": VERSIONS["mypy"],
        "steps": steps,
    }
    extra_steps = overrides.pop("steps", None)
    body.update(overrides)
    if isinstance(extra_steps, dict):
        body["steps"] = extra_steps
    (git_dir / run_gates.STAMP_NAME).write_text(json.dumps(body), encoding="utf-8")


def _stamp_path(git_box: dict[str, object]) -> Path:
    return Path(str(git_box["git_dir"])) / run_gates.STAMP_NAME


def test_no_stamp_refuses(git_box: dict[str, object], capsys: pytest.CaptureFixture[str]) -> None:
    assert tag_release.main(["v0.9.19", "--dry-run"]) == 1
    assert "no gate stamp" in capsys.readouterr().err
    assert not _pushed(git_box)


def test_stamp_for_another_sha_refuses(
    git_box: dict[str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    _write_stamp(Path(str(git_box["git_dir"])), head_sha=OTHER)
    assert tag_release.main(["v0.9.19"]) == 1
    assert "different commit" in capsys.readouterr().err
    assert not _tagged(git_box)


def test_dirty_tree_refuses(git_box: dict[str, object], capsys: pytest.CaptureFixture[str]) -> None:
    git_box["dirty"] = True
    _write_stamp(Path(str(git_box["git_dir"])))
    assert tag_release.main(["v0.9.19"]) == 1
    assert "the tree is dirty" in capsys.readouterr().err
    assert not _tagged(git_box)


def test_stale_stamp_refuses(
    git_box: dict[str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    when = (NOW - timedelta(minutes=61)).isoformat()
    _write_stamp(Path(str(git_box["git_dir"])), when=when)
    assert tag_release.main(["v0.9.19"]) == 1
    assert "older than 60 minutes" in capsys.readouterr().err
    assert not _tagged(git_box)


def test_fast_mode_refuses(git_box: dict[str, object], capsys: pytest.CaptureFixture[str]) -> None:
    _write_stamp(Path(str(git_box["git_dir"])), mode="fast")
    assert tag_release.main(["v0.9.19"]) == 1
    assert "mode is not full" in capsys.readouterr().err
    assert not _tagged(git_box)


def test_failed_step_refuses(
    git_box: dict[str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    steps = {name: "pass" for name in run_gates.FULL_STEPS}
    steps["pytest"] = "fail"
    _write_stamp(Path(str(git_box["git_dir"])), steps=steps)
    assert tag_release.main(["v0.9.19"]) == 1
    assert "step pytest is not pass" in capsys.readouterr().err
    assert not _tagged(git_box)


def test_version_check_failure_refuses(
    git_box: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_stamp(Path(str(git_box["git_dir"])))
    monkeypatch.setattr(
        tag_release,
        "version_check",
        lambda tag, root: (1, "Tag v0.9.19 does not match pyproject.toml version 0.9.18.\n"),
    )
    assert tag_release.main(["v0.9.19", "--dry-run"]) == 1
    assert "check_release_version" in capsys.readouterr().err
    assert not _tagged(git_box)


def test_valid_stamp_dry_run_creates_no_tag(
    git_box: dict[str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    _write_stamp(Path(str(git_box["git_dir"])))
    assert tag_release.main(["v0.9.19", "--dry-run"]) == 0
    assert "dry-run: no tag created" in capsys.readouterr().out
    assert not _tagged(git_box)
    assert not _pushed(git_box)


def test_valid_stamp_creates_a_tag_and_does_not_push(
    git_box: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_stamp(Path(str(git_box["git_dir"])))
    assert tag_release.main(["v0.9.19"]) == 0
    out = capsys.readouterr().out
    assert "created annotated tag v0.9.19" in out
    assert "Dispatch the Release workflow" in out
    assert _tagged(git_box)
    assert not _pushed(git_box)
    message = next(args for args in _recorded(git_box) if args[:3] == ["git", "tag", "-a"])
    assert message[-1] == f"full gate stamp at {NOW.isoformat()}"


def test_run_gates_records_a_failed_step_and_writes_no_stamp(
    git_box: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_stamp(Path(str(git_box["git_dir"])))
    git_box["docs_code"] = 1
    git_box["docs_output"] = "\n".join(f"line {index}" for index in range(50))
    assert run_gates.main([]) == 1
    assert not _stamp_path(git_box).exists()
    out = capsys.readouterr().out
    assert "docs fail" in out
    assert "line 49" in out
    assert "line 0\n" not in out
    assert "gate failed at docs" in out


def test_run_gates_keeps_a_stamp_for_a_different_commit(git_box: dict[str, object]) -> None:
    _write_stamp(Path(str(git_box["git_dir"])), head_sha=OTHER)
    git_box["docs_code"] = 1
    git_box["docs_output"] = "docs broke\n"
    assert run_gates.main([]) == 1
    assert _stamp_path(git_box).is_file()


def test_allow_dirty_does_not_write_a_stamp(git_box: dict[str, object]) -> None:
    git_box["dirty"] = True
    git_box["fail_unknown"] = False
    assert run_gates.main(["--allow-dirty"]) == 0
    assert not _stamp_path(git_box).exists()


def test_run_gates_exits_2_outside_a_git_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(
        args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None
    ) -> tuple[int, str]:
        if args == ["git", "rev-parse", "--show-toplevel"]:
            return 128, "fatal: not a git repository\n"
        raise AssertionError(args)

    monkeypatch.setattr(run_gates, "command", fake)
    assert run_gates.main([]) == 2


def _recorded(git_box: dict[str, object]) -> list[list[str]]:
    recorded = git_box["recorded"]
    assert isinstance(recorded, list)
    return recorded


def _tagged(git_box: dict[str, object]) -> bool:
    return any(args[:3] == ["git", "tag", "-a"] for args in _recorded(git_box))


def _pushed(git_box: dict[str, object]) -> bool:
    return any(args[:2] == ["git", "push"] for args in _recorded(git_box))
