"""Ruff and mypy dev gate."""

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _dev_dependency_names() -> set[str]:
    """Lowercased project names from the dev extra, independent of version floors."""
    m = re.search(
        r"^dev = \[(.*?)\]", (REPO / "pyproject.toml").read_text(encoding="utf-8"), re.M | re.S
    )
    assert m is not None, "dev extra missing from pyproject.toml"
    names = set()
    for item in m.group(1).split(","):
        name = re.split(r"[<>=!~\[]", item.strip().strip('"').strip("'"), maxsplit=1)[0]
        if name:
            names.add(name.strip().lower())
    return names


def test_ac1_ruff_and_mypy_in_dev_extra_and_pyproject_configs():
    """AC1. dev optional-dependencies and tool configs live in pyproject.toml."""
    assert {"pytest", "ruff", "mypy"} <= _dev_dependency_names()
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.ruff]" in text
    assert "[tool.mypy]" in text
    assert 'packages = ["essay_writer"]' in text


def test_ac2_ruff_check_exits_zero():
    """AC2. ruff check src tests passes on tip."""
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "src", "tests"],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_ac3_mypy_src_exits_zero():
    """AC3. mypy src passes on tip."""
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "src"],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
