"""The package author line, matching python-mcp-bootstrap.

``pyproject.toml`` names one author and one maintainer, with the same GitHub
noreply address the upstream bootstrap package uses. The check below only
reads the file: a tree whose ``pyproject.toml`` is missing or unreadable
reports the failure and writes nothing back.

Ids: essay-author-a1, essay-author-a2, essay-author-b1.
"""

from __future__ import annotations

import os
import re
import subprocess
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PYPROJECT = REPO / "pyproject.toml"
LICENCE = REPO / "LICENSE"

NOREPLY = "4zhmv6zvj2-afk@users.noreply.github.com"
AUTHOR_RECORD = {"name": "Ron", "email": NOREPLY}
AUTHORS_LINE = f'authors = [{{ name = "Ron", email = "{NOREPLY}" }}]'
MAINTAINERS_LINE = f'maintainers = [{{ name = "Ron", email = "{NOREPLY}" }}]'

# Addresses the suite may carry: the one author address, and the domains the
# RFC reserves for documentation and tests, which belong to nobody.
ALLOWED_DOMAINS = frozenset(
    {
        "users.noreply.github.com",
        "example.com",
        "example.net",
        "example.org",
        "example.test",
        "example.invalid",
    }
)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)")


def author_metadata(root: Path) -> tuple[dict | None, list[str]]:
    """The ``[project]`` table and every author problem, read-only.

    The file is only ever opened for reading, so a tree that cannot supply a
    ``pyproject.toml`` gets a problem instead of a rewritten one.
    """
    try:
        text = (root / "pyproject.toml").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, [f"pyproject.toml was not read: {exc}"]
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        return None, [f"pyproject.toml was not read: {exc}"]
    project = data.get("project")
    if not isinstance(project, dict):
        return None, ["pyproject.toml has no [project] table"]
    problems = [
        f"pyproject.toml {field} is {project.get(field)!r}, not the author record"
        for field in ("authors", "maintainers")
        if project.get(field) != [AUTHOR_RECORD]
    ]
    return project, problems


def tracked_text() -> list[tuple[str, str]]:
    """Every tracked file that decodes as text, as (path, contents)."""
    out = subprocess.check_output(["git", "-C", str(REPO), "ls-files", "-z"])
    found: list[tuple[str, str]] = []
    for name in out.decode().split("\0"):
        if not name:
            continue
        try:
            raw = (REPO / name).read_bytes()
        except OSError:
            continue
        if b"\0" in raw:
            continue
        found.append((name, raw.decode("utf-8", "replace")))
    return found


@pytest.mark.parametrize("case_id", [pytest.param("essay-author-a1", id="essay-author-a1")])
def test_essay_author_a1_author_and_maintainer_match_the_bootstrap(case_id):
    """a1: authors and maintainers are both the one Ron noreply record."""
    assert case_id == "essay-author-a1"
    project, problems = author_metadata(REPO)
    assert problems == []
    assert project is not None
    assert project["authors"] == [AUTHOR_RECORD]
    assert project["maintainers"] == [AUTHOR_RECORD]
    assert project["authors"] == project["maintainers"]

    lines = PYPROJECT.read_text(encoding="utf-8").splitlines()
    assert lines.count(AUTHORS_LINE) == 1
    assert lines.count(MAINTAINERS_LINE) == 1
    email = project["authors"][0]["email"]
    assert email == NOREPLY
    assert not email.split("@")[0].endswith("+289450915")
    assert "+" not in email.split("@")[0]


@pytest.mark.parametrize("case_id", [pytest.param("essay-author-a2", id="essay-author-a2")])
def test_essay_author_a2_version_licence_and_no_real_address(case_id):
    """a2: version 0.9.2, MIT licence, and no real address in the tracked tree."""
    assert case_id == "essay-author-a2"
    project, problems = author_metadata(REPO)
    assert problems == []
    assert project is not None
    assert project["version"] == "0.9.2"
    assert project["license"] == "MIT"

    licence = LICENCE.read_text(encoding="utf-8")
    assert licence.splitlines()[0] == "MIT License"
    assert "Permission is hereby granted, free of charge" in licence

    strangers = []
    for name, text in tracked_text():
        for match in EMAIL.finditer(text):
            if match.group(1).lower() not in ALLOWED_DOMAINS:
                strangers.append(f"{name}: {match.group(0)}")
    assert strangers == []


@pytest.mark.parametrize("case_id", [pytest.param("essay-author-b1", id="essay-author-b1")])
def test_essay_author_b1_a_tree_without_a_readable_file_is_not_rewritten(case_id, tmp_path):
    """b1: A missing or unreadable pyproject.toml reports, and writes nothing."""
    assert case_id == "essay-author-b1"
    missing = tmp_path / "missing"
    missing.mkdir()
    project, problems = author_metadata(missing)
    assert project is None
    assert len(problems) == 1
    assert "pyproject.toml was not read" in problems[0]
    assert str(missing / "pyproject.toml") in problems[0]
    assert not (missing / "pyproject.toml").exists()
    assert os.listdir(missing) == []

    damaged = tmp_path / "damaged"
    damaged.mkdir()
    damaged_file = damaged / "pyproject.toml"
    damaged_file.write_bytes(b'[project]\nauthors = [{ name = "Ron", \xff\xfe\n')
    before = damaged_file.read_bytes()
    project, problems = author_metadata(damaged)
    assert project is None
    assert problems and "was not read" in problems[0]
    assert damaged_file.read_bytes() == before

    unreadable = tmp_path / "unreadable"
    (unreadable / "pyproject.toml").mkdir(parents=True)
    project, problems = author_metadata(unreadable)
    assert project is None
    assert len(problems) == 1
    assert "pyproject.toml was not read" in problems[0]
    assert (unreadable / "pyproject.toml").is_dir()
    assert not (unreadable / "pyproject.toml").is_file()

    for root in (missing, damaged, unreadable):
        project, problems = author_metadata(root)
        assert project is None
        assert problems
        assert "authors = [" not in "\n".join(problems)
        assert "maintainers = [" not in "\n".join(problems)
