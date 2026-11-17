"""The project licence is the Apache License, Version 2.0, and nothing else.

Licence and metadata only: the package version, product code, prompts,
templates, and student fixtures stay as they are on the tip, and no NOTICE file
is added.

Each hyphen id is seated once, in the docstring of the test that proves it.
"""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HOLDER = "Copyright 2026 4zhmv6zvj2-afk"
AUTHOR_RECORD = {"name": "Ron", "email": "4zhmv6zvj2-afk@users.noreply.github.com"}
OLD_HOLDER = "Copyright (c) 2026"
APACHE_CLASSIFIER = "License :: OSI Approved :: Apache Software License"
VERSION = "0.9.9"
MIT_MARKS = ("MIT License", "license-MIT", "[MIT]")
OKAVANGO = REPO / "tests" / "fixtures" / "okavango-strong-v1.md"


def _lines(text: str) -> list[str]:
    return text.splitlines()


def _license_problems(root: Path) -> list[str]:
    """Problems with the licence and metadata under root. Reads only; writes nothing."""
    problems: list[str] = []

    license_path = root / "LICENSE"
    try:
        license_text = license_path.read_text(encoding="utf-8")
    except OSError as exc:
        problems.append(f"LICENSE is missing or unreadable: {exc.__class__.__name__}")
        license_text = None
    if license_text is not None:
        lines = _lines(license_text)
        if lines and lines[0].strip() == "MIT License":
            problems.append("LICENSE still starts with MIT License")
        header = [line.strip() for line in lines[:3]]
        if header[:2] != ["Apache License", "Version 2.0, January 2004"]:
            problems.append("LICENSE does not open with the Apache License 2.0 header")
        if "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION" not in license_text:
            problems.append("LICENSE is not the body of the Apache License 2.0")
        if "END OF TERMS AND CONDITIONS" not in license_text:
            problems.append("LICENSE stops before the end of the terms")
        holds = [line for line in lines if line.strip() == HOLDER]
        if len(holds) != 1:
            problems.append(f"LICENSE does not carry exactly one line reading {HOLDER}")
        if OLD_HOLDER in license_text:
            problems.append("LICENSE still carries the old copyright form")
        if "[yyyy]" in license_text or "[name of copyright owner]" in license_text:
            problems.append("LICENSE still carries the appendix placeholders")

    project: dict = {}
    pyproject_path = root / "pyproject.toml"
    try:
        project = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))["project"]
    except OSError as exc:
        problems.append(f"pyproject.toml is missing or unreadable: {exc.__class__.__name__}")
    except (tomllib.TOMLDecodeError, UnicodeDecodeError, KeyError) as exc:
        problems.append(f"pyproject.toml is malformed: {exc.__class__.__name__}")
    if project:
        if project.get("license") != "Apache-2.0":
            problems.append(f"pyproject license is {project.get('license')!r}, not Apache-2.0")
        if project.get("license-files") != ["LICENSE"]:
            problems.append("pyproject license-files does not name LICENSE")
        if APACHE_CLASSIFIER in project.get("classifiers", []):
            problems.append(
                "pyproject classifiers still carry the licence classifier setuptools 84 rejects"
            )
        if project.get("version") != VERSION:
            problems.append(f"pyproject version is {project.get('version')!r}, not {VERSION}")
        for field in ("authors", "maintainers"):
            if project.get(field) != [AUTHOR_RECORD]:
                problems.append(f"pyproject {field} is not the one author record")

    readme_path = root / "README.md"
    try:
        readme = readme_path.read_text(encoding="utf-8")
    except OSError as exc:
        problems.append(f"README.md is missing or unreadable: {exc.__class__.__name__}")
        readme = None
    if readme is not None:
        badge = next(
            (line for line in _lines(readme) if "shields.io/badge/license-" in line),
            "",
        )
        if not badge:
            problems.append("README.md has no licence badge")
        elif "apache" not in badge.casefold() or "2.0" not in badge:
            problems.append("README licence badge does not name Apache 2.0")
        section = _license_section(readme)
        if section is None:
            problems.append("README.md has no License section")
        elif not (
            "(LICENSE)" in section
            and "Apache License 2.0" in section
            and "© 2026 `4zhmv6zvj2-afk`" in section
        ):
            problems.append("README License section is not the Apache link with the holder")
        for mark in MIT_MARKS:
            if mark in readme:
                problems.append(f"README.md still claims MIT ({mark})")

    if not (root / "MANIFEST.in").is_file():
        problems.append("MANIFEST.in is missing")
    elif "include LICENSE" not in (root / "MANIFEST.in").read_text(encoding="utf-8"):
        problems.append("MANIFEST.in no longer includes LICENSE")
    if (root / "NOTICE").exists():
        problems.append("a NOTICE file was added")
    return problems


def _license_section(readme: str) -> str | None:
    """The body under the README ``## License`` heading, or None when it is absent."""
    match = re.search(r"(?m)^## License\s*$", readme)
    if match is None:
        return None
    rest = readme[match.end() :]
    following = re.search(r"(?m)^## ", rest)
    return rest[: following.start()] if following else rest


def _snapshot(root: Path) -> dict[str, object]:
    """Every file under root and what it holds. An unreadable file is recorded by its stat."""
    snapshot: dict[str, object] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        stat = path.stat()
        try:
            snapshot[str(path.relative_to(root))] = path.read_bytes()
        except OSError:
            snapshot[str(path.relative_to(root))] = ("unreadable", stat.st_size, stat.st_mtime_ns)
    return snapshot


def _valid_tree(root: Path) -> Path:
    """A copy of the three licence files from this checkout, for the failure cases."""
    root.mkdir(parents=True, exist_ok=True)
    for name in ("LICENSE", "pyproject.toml", "README.md", "MANIFEST.in"):
        (root / name).write_bytes((REPO / name).read_bytes())
    return root


@pytest.mark.parametrize("case_id", [pytest.param("essay-license-a1", id="essay-license-a1")])
def test_license_is_the_apache_license_two(case_id):
    """essay-license-a1: LICENSE is the Apache License 2.0 with the holder line."""
    assert case_id == "essay-license-a1"
    text = (REPO / "LICENSE").read_text(encoding="utf-8")
    lines = _lines(text)
    assert not text.startswith("MIT License")
    assert lines[0].strip() == "Apache License"
    assert lines[1].strip() == "Version 2.0, January 2004"
    assert lines[2].strip() == "http://www.apache.org/licenses/"
    assert "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION" in text
    assert "END OF TERMS AND CONDITIONS" in text
    assert "APPENDIX: How to apply the Apache License to your work." in text
    assert [line for line in lines if line.strip() == HOLDER] == [HOLDER]
    assert OLD_HOLDER not in text
    assert "MIT" not in text
    assert _license_problems(REPO) == []


@pytest.mark.parametrize("case_id", [pytest.param("essay-license-a2", id="essay-license-a2")])
def test_metadata_and_docs_name_the_apache_license(case_id):
    """essay-license-a2: pyproject and the README name Apache 2.0, not MIT."""
    assert case_id == "essay-license-a2"
    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["license"] == "Apache-2.0"
    assert project["license-files"] == ["LICENSE"]
    assert APACHE_CLASSIFIER not in project["classifiers"]
    assert project["version"] == VERSION
    assert project["authors"] == [AUTHOR_RECORD]
    assert project["maintainers"] == [AUTHOR_RECORD]

    readme = (REPO / "README.md").read_text(encoding="utf-8")
    badge = next(line for line in _lines(readme) if "shields.io/badge/license-" in line)
    assert "license-MIT" not in badge
    assert "apache" in badge.casefold()
    assert "2.0" in badge
    section = _license_section(readme)
    assert section is not None
    assert "[Apache License 2.0](LICENSE)" in section
    assert "© 2026 `4zhmv6zvj2-afk`" in section
    for mark in MIT_MARKS:
        assert mark not in readme
        assert mark not in (REPO / "pyproject.toml").read_text(encoding="utf-8")
        assert mark not in (REPO / "LICENSE").read_text(encoding="utf-8")
    assert _license_problems(REPO) == []


@pytest.mark.parametrize("case_id", [pytest.param("essay-license-b1", id="essay-license-b1")])
def test_neighbouring_names_stay_put(case_id):
    """essay-license-b1: The licence change leaves the neighbouring names alone."""
    assert case_id == "essay-license-b1"
    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["authors"] == [AUTHOR_RECORD]
    assert project["maintainers"] == [AUTHOR_RECORD]
    assert project["name"] == "essay-writer"
    assert project["version"] == VERSION
    assert "include LICENSE" in (REPO / "MANIFEST.in").read_text(encoding="utf-8")
    assert not (REPO / "NOTICE").exists()
    assert not (REPO / "NOTICE.txt").exists()
    assert "irrigation licence" in OKAVANGO.read_text(encoding="utf-8")

    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    section = changelog.split("## 0.9.1", 1)[0]
    assert "## 0.9.4" in section
    assert "## 0.9.3" in section
    assert "## 0.9.2" in section
    bullets = [line for line in _lines(section) if line.startswith("- ")]
    assert any("Apache License" in bullet for bullet in bullets)
    assert "Setup defaults, damaged-record handling" in section
    assert "The chat sounds like a helpful friend." in section
    assert "The Word cover prints a programme row only when the brief asks for it." in section
    assert "## 0.9.1" in changelog


@pytest.mark.parametrize("case_id", [pytest.param("essay-license-c1", id="essay-license-c1")])
def test_a_broken_licence_input_reports_and_writes_nothing(case_id, tmp_path):
    """essay-license-c1: A missing, malformed, or unreadable input reports and writes nothing."""
    assert case_id == "essay-license-c1"

    missing = _valid_tree(tmp_path / "missing")
    (missing / "LICENSE").unlink()
    before = _snapshot(missing)
    problems = _license_problems(missing)
    assert problems
    assert any("LICENSE" in problem for problem in problems)
    assert _snapshot(missing) == before
    assert not (missing / "LICENSE").exists()

    malformed = _valid_tree(tmp_path / "malformed")
    text = (malformed / "pyproject.toml").read_text(encoding="utf-8")
    (malformed / "pyproject.toml").write_text(
        text.replace("[project]", "[project"), encoding="utf-8"
    )
    before = _snapshot(malformed)
    problems = _license_problems(malformed)
    assert problems
    assert any("pyproject.toml" in problem for problem in problems)
    assert _snapshot(malformed) == before

    mit = _valid_tree(tmp_path / "mit")
    (mit / "LICENSE").write_text("MIT License\n\nCopyright (c) 2026 4zhmv6zvj2-afk\n", "utf-8")
    before = _snapshot(mit)
    problems = _license_problems(mit)
    assert any("MIT License" in problem for problem in problems)
    assert _snapshot(mit) == before

    if os.geteuid() == 0:
        pytest.skip("an unreadable file cannot be planted as root")
    unreadable = _valid_tree(tmp_path / "unreadable")
    license_path = unreadable / "LICENSE"
    project_path = unreadable / "pyproject.toml"
    license_path.chmod(0o000)
    try:
        before = _snapshot(unreadable)
        problems = _license_problems(unreadable)
        assert problems
        assert any("LICENSE" in problem for problem in problems)
        assert _snapshot(unreadable) == before
        assert not (unreadable / "NOTICE").exists()
        assert not (unreadable / "LICENSE.txt").exists()
    finally:
        license_path.chmod(0o644)
    project_path.chmod(0o000)
    try:
        before = _snapshot(unreadable)
        problems = _license_problems(unreadable)
        assert any("pyproject.toml" in problem for problem in problems)
        assert _snapshot(unreadable) == before
        invented = []
        for path in unreadable.rglob("*"):
            if not path.is_file():
                continue
            try:
                text_written = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if HOLDER in text_written:
                invented.append(path.name)
        assert invented == ["LICENSE"]
    finally:
        project_path.chmod(0o644)
