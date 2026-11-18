"""The package names its author and maintainer, and nothing else moves.

``pyproject.toml`` carries one author record and one maintainer record, both
pointing at the same GitHub noreply address. The version stays the package's
current version and the
licence stays the Apache License, Version 2.0.

The check that reads the record only ever opens the file for reading. A tree
whose ``pyproject.toml`` is missing, malformed, or unreadable is reported, not
repaired: no file appears, no byte changes, and no author line is invented.

Each hyphen id is seated once, in the docstring of the test that proves it.
"""

from __future__ import annotations

import os
import re
import subprocess
import tomllib
from pathlib import Path

import pytest

from essay_writer import __version__ as VERSION

REPO = Path(__file__).resolve().parents[1]
PYPROJECT = REPO / "pyproject.toml"
LICENSE = REPO / "LICENSE"
CHANGELOG = REPO / "CHANGELOG.md"
README = REPO / "README.md"

# This file is tracked and it names the numeric git form it hunts for, so a
# whole-tree scan has to skip its own bytes and scan every other file. The skip
# is asserted below, so it cannot quietly become the whole walk.
SELF_NAME = "tests/test_essay_author.py"

NOREPLY = "4zhmv6zvj2-afk@users.noreply.github.com"
AUTHOR_RECORD = {"name": "Ron", "email": NOREPLY}
AUTHORS_LINE = 'authors = [{ name = "Ron", email = "4zhmv6zvj2-afk@users.noreply.github.com" }]'
MAINTAINERS_LINE = (
    'maintainers = [{ name = "Ron", email = "4zhmv6zvj2-afk@users.noreply.github.com" }]'
)
FIELD_LINES = {"authors": AUTHORS_LINE, "maintainers": MAINTAINERS_LINE}

APACHE_CLASSIFIER = "License :: OSI Approved :: Apache Software License"
HOLDER = "Copyright 2026 4zhmv6zvj2-afk"

# The [project] keys the tip already carries, plus the two this slice adds.
PROJECT_KEYS = frozenset(
    {
        "name",
        "version",
        "description",
        "keywords",
        "authors",
        "maintainers",
        "classifiers",
        "readme",
        "requires-python",
        "license",
        "license-files",
        "dependencies",
        "optional-dependencies",
        "scripts",
        "urls",
    }
)

# Addresses the committed tree may carry: this author's noreply address and the
# domains the RFC reserves for documentation and tests, which belong to nobody.
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
NUMERIC_GIT_FORM = re.compile(r"^\d{5,}\+")

OKAVANGO = REPO / "tests" / "fixtures" / "okavango-strong-v1.md"

# The nineteen bullets the 0.9.3 section carries on this release tip, by their
# opening words. A new bullet may be added; none may go.
KEPT_BULLETS = (
    "- The chat sounds like a helpful friend.",
    "- After a save, the next stage's card appears only when",
    "- Student chat keeps ordinary English",
    "- Research summary and full research drafts carry no card",
    "- The host sheet and the `essay.pack.validate` description",
    '- The leftover free-alternative reply keeps "Nothing was fetched."',
    "- The spoken Basics pass stops calling a brief silent",
    "- An obvious cue fills a format or a question the brief left empty.",
    "- A format or question the brief leaves empty can be answered once",
    "- The Word cover prints a programme row only when the brief asks for it.",
    "- Until the genre is known, stages 2 and 3 use Establish the focus",
    "- A mid-office reader that is still finishing after the run folder moves",
    "- The licence is the Apache License, Version 2.0.",
    "- `pyproject.toml` names the package author and maintainer:",
    "- A stage 7 draft still asks its questions when a mid step starts",
    "- An unmapped brief still prints the title-page rows it asks for.",
    "- A format or question answer is stored on a draft.",
    "- The answer file beside the brief is read and written only when",
    "- Ruff format is clean across the test files the format check reads.",
)


def _lines(text: str) -> list[str]:
    return text.splitlines()


def _read_project(path: Path) -> tuple[dict | None, list[str]]:
    """The ``[project]`` table and every read problem, open for reading only."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, [f"pyproject.toml is missing or unreadable: {exc.__class__.__name__}"]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, [f"pyproject.toml is not valid UTF-8: {exc.__class__.__name__}"]
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        return None, [f"pyproject.toml is malformed: {exc.__class__.__name__}"]
    project = data.get("project")
    if not isinstance(project, dict):
        return None, ["pyproject.toml has no [project] table"]
    return project, []


def author_problems(root: Path) -> list[str]:
    """Problems with the author and maintainer record under root. Reads only."""
    project, problems = _read_project(root / "pyproject.toml")
    if project is None:
        return problems
    for field in ("authors", "maintainers"):
        if project.get(field) != [AUTHOR_RECORD]:
            problems.append(
                f"pyproject {field} is {project.get(field)!r}, not the one author record"
            )
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    present = _lines(text)
    for field, line in FIELD_LINES.items():
        if present.count(line) != 1:
            problems.append(f"pyproject {field} line is missing, repeated, or spelled differently")
    return problems


_SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        "htmlcov",
        ".eggs",
        "build",
        "dist",
        "node_modules",
    }
)


def _skipped(relative: Path) -> bool:
    """Build output, tool caches, and virtualenvs are not the package."""
    return any(part in _SKIP_DIRS or part.endswith(".egg-info") for part in relative.parts)


def _product_files(root: Path) -> list[Path]:
    """Source, fixtures, and docs under root. Generated egg-info is not a product file."""
    found: list[Path] = []
    for folder in ("src", "tests/fixtures", "tools/doc_templates", "docs"):
        base = root / folder
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            if _skipped(path.relative_to(root)):
                continue
            found.append(path)
    return found


def _listed_names(root: Path | None = None) -> list[str]:
    """Tracked paths when this tree is a git checkout, otherwise the files on disk.

    An unpacked sdist has no ``git`` metadata. The walk leaves out build output,
    tool caches, and virtualenvs so a local junk file is not treated as the package.
    """
    root = REPO if root is None else root
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "ls-files", "-z"],
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        names: list[str] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(root)
            if _skipped(relative):
                continue
            names.append(relative.as_posix())
        return names
    return [name for name in out.decode().split("\0") if name]


def tracked_text(
    skip: frozenset[str] = frozenset(),
    root: Path | None = None,
) -> list[tuple[str, str]]:
    """Every tracked file that decodes as text, as (path, contents).

    A path in ``skip`` is left out. The caller that skips this test file asserts
    the name is really tracked first, so the walk cannot shrink by a typo.
    Without git, the same scan reads the files in the tree and leaves out build
    and cache directories.
    """
    root = REPO if root is None else root
    found: list[tuple[str, str]] = []
    for name in _listed_names(root):
        if name in skip:
            continue
        try:
            raw = (root / name).read_bytes()
        except OSError:
            continue
        if b"\0" in raw:
            continue
        found.append((name, raw.decode("utf-8", "replace")))
    return found


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


def _changelog_bullets() -> list[str]:
    """The bullets under the 0.9.3 heading, up to the next release heading."""
    text = CHANGELOG.read_text(encoding="utf-8")
    section = text.split("## 0.9.3", 1)[1].split("## 0.9.2", 1)[0]
    return [line for line in _lines(section) if line.startswith("- ")]


@pytest.mark.parametrize("case_id", [pytest.param("essay-author-a1", id="essay-author-a1")])
def test_author_and_maintainer_are_the_one_noreply_record(case_id):
    """essay-author-a1: authors and maintainers are both the Ron noreply record."""
    assert case_id == "essay-author-a1"
    project, problems = _read_project(PYPROJECT)
    assert problems == []
    assert project is not None
    assert project["authors"] == [AUTHOR_RECORD]
    assert project["maintainers"] == [AUTHOR_RECORD]
    assert project["authors"] == project["maintainers"]

    lines = _lines(PYPROJECT.read_text(encoding="utf-8"))
    assert lines.count(AUTHORS_LINE) == 1
    assert lines.count(MAINTAINERS_LINE) == 1
    assert author_problems(REPO) == []

    email = project["authors"][0]["email"]
    assert email == NOREPLY
    assert not NUMERIC_GIT_FORM.match(email.split("@")[0])
    assert "+" not in email.split("@")[0]


@pytest.mark.parametrize("case_id", [pytest.param("essay-author-a2", id="essay-author-a2")])
def test_version_and_apache_licence_stay_and_no_real_address_ships(case_id):
    """essay-author-a2: the current package version, Apache 2.0, and no real address."""
    assert case_id == "essay-author-a2"
    project, problems = _read_project(PYPROJECT)
    assert problems == []
    assert project is not None
    assert project["version"] == VERSION
    assert project["license"] == "Apache-2.0"
    assert project["license-files"] == ["LICENSE"]
    assert APACHE_CLASSIFIER not in project["classifiers"]

    licence = LICENSE.read_text(encoding="utf-8")
    lines = _lines(licence)
    assert lines[0].strip() == "Apache License"
    assert lines[1].strip() == "Version 2.0, January 2004"
    assert "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION" in licence
    assert "END OF TERMS AND CONDITIONS" in licence
    assert [line for line in lines if line.strip() == HOLDER] == [HOLDER]
    assert "289450915" not in licence

    strangers = []
    every = {name for name, _text in tracked_text()}
    scanned = tracked_text(skip=frozenset({SELF_NAME}))
    names = {name for name, _text in scanned}
    # This file is tracked, so it names the numeric git form it hunts for. The
    # walk leaves out exactly this file and every other tracked text file stays
    # in, so the exclusion cannot quietly become the whole scan.
    assert SELF_NAME in every
    assert names == every - {SELF_NAME}
    assert {"pyproject.toml", "LICENSE", "README.md", "CHANGELOG.md"} <= names
    for name, text in scanned:
        if "289450915" in text:
            strangers.append(f"{name}: numeric git form")
        for match in EMAIL.finditer(text):
            if match.group(1).casefold() not in ALLOWED_DOMAINS:
                strangers.append(f"{name}: {match.group(0)}")
    assert strangers == []


@pytest.mark.parametrize("case_id", [pytest.param("essay-author-a3", id="essay-author-a3")])
def test_the_address_scan_reads_the_tree_without_git(case_id, monkeypatch, tmp_path):
    """essay-author-a3: Without git, the address scan reads the files on disk."""
    assert case_id == "essay-author-a3"

    def unavailable(*_args, **_kwargs):
        raise subprocess.CalledProcessError(128, ["git", "ls-files"])

    monkeypatch.setattr(subprocess, "check_output", unavailable)
    names = {name for name, _text in tracked_text()}
    assert {"pyproject.toml", "LICENSE", "README.md", SELF_NAME} <= names
    skipped = {name for name, _text in tracked_text(skip=frozenset({SELF_NAME}))}
    assert SELF_NAME not in skipped
    assert names - skipped == {SELF_NAME}

    junk = tmp_path / "unpacked"
    (junk / "notes").mkdir(parents=True)
    (junk / "notes" / "readme.txt").write_text("kept\n", encoding="utf-8")
    for folder in ("build/lib", ".mypy_cache", ".ruff_cache", "src/essay_writer.egg-info"):
        path = junk / folder
        path.mkdir(parents=True)
        (path / "secret.txt").write_text("secret@real.example\n", encoding="utf-8")
    walked = {name for name, _text in tracked_text(root=junk)}
    assert walked == {"notes/readme.txt"}


@pytest.mark.parametrize("case_id", [pytest.param("essay-author-b1", id="essay-author-b1")])
def test_neighbouring_names_stay_put(case_id, tmp_path):
    """essay-author-b1: only the author records move; the Apache licence stays."""
    assert case_id == "essay-author-b1"
    project, problems = _read_project(PYPROJECT)
    assert problems == []
    assert project is not None
    assert set(project) == PROJECT_KEYS
    assert project["name"] == "essay-writer"
    assert project["version"] == VERSION
    assert project["license"] == "Apache-2.0"
    assert project["license-files"] == ["LICENSE"]
    assert APACHE_CLASSIFIER not in project["classifiers"]

    readme = README.read_text(encoding="utf-8")
    badge = next(line for line in _lines(readme) if "shields.io/badge/license-" in line)
    assert "apache" in badge.casefold()
    assert "2.0" in badge
    assert "MIT" not in badge
    assert "[Apache License 2.0](LICENSE)" in readme
    assert "© 2026 `4zhmv6zvj2-afk`" in readme

    assert "include LICENSE" in (REPO / "MANIFEST.in").read_text(encoding="utf-8")
    assert not (REPO / "NOTICE").exists()
    assert not (REPO / "NOTICE.txt").exists()

    assert "irrigation licence" in OKAVANGO.read_text(encoding="utf-8")

    # The records belong to package metadata: no product code, prompt, template,
    # or student fixture carries them. A generated egg-info beside the source
    # is build output, so the sdist's PKG-INFO is not a product file.
    for path in _product_files(REPO):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        assert NOREPLY not in text, path

    planted = tmp_path / "with-egg-info"
    note = planted / "src" / "note.py"
    note.parent.mkdir(parents=True)
    note.write_text("print('kept')\n", encoding="utf-8")
    egg = planted / "src" / "essay_writer.egg-info" / "PKG-INFO"
    egg.parent.mkdir(parents=True)
    egg.write_text(f"Author-email: {NOREPLY}\n", encoding="utf-8")
    assert _product_files(planted) == [note]
    assert NOREPLY not in note.read_text(encoding="utf-8")
    assert egg.is_file()

    bullets = _changelog_bullets()
    # The 0.9.3 section may gain a bullet for a later fix; it may not lose one.
    assert len(bullets) >= 19
    assert any("names the package author and maintainer" in bullet for bullet in bullets)
    # Every bullet already on the tip is still there, including the Apache one.
    for opening in KEPT_BULLETS:
        assert any(bullet.startswith(opening) for bullet in bullets), opening
    assert any(
        "A stage 7 draft still asks its questions when a mid step starts" in bullet
        for bullet in bullets
    )
    released = CHANGELOG.read_text(encoding="utf-8")
    intro_093 = released.split("## 0.9.3", 1)[1].split("## 0.9.2", 1)[0]
    assert "Brief gap lines, stored answers, cover rules" in intro_093
    intro_092 = released.split("## 0.9.2", 1)[1].split("## 0.9.1", 1)[0]
    assert "Setup defaults, damaged-record handling" in intro_092


@pytest.mark.parametrize("case_id", [pytest.param("essay-author-c1", id="essay-author-c1")])
def test_a_broken_author_input_reports_and_writes_nothing(case_id, tmp_path):
    """essay-author-c1: A missing, malformed, or unreadable file reports and writes nothing."""
    assert case_id == "essay-author-c1"

    missing = tmp_path / "missing"
    missing.mkdir()
    before = _snapshot(missing)
    problems = author_problems(missing)
    assert problems
    assert any("pyproject.toml" in problem for problem in problems)
    assert _snapshot(missing) == before
    assert os.listdir(missing) == []

    malformed = tmp_path / "malformed"
    malformed.mkdir()
    (malformed / "pyproject.toml").write_text("[project\nauthors = [{]\n", encoding="utf-8")
    before = _snapshot(malformed)
    problems = author_problems(malformed)
    assert problems
    assert any("malformed" in problem for problem in problems)
    assert _snapshot(malformed) == before

    not_utf8 = tmp_path / "not-utf8"
    not_utf8.mkdir()
    (not_utf8 / "pyproject.toml").write_bytes(b'[project]\nname = "essay-writer"\n\xff\xfe\n')
    before = _snapshot(not_utf8)
    problems = author_problems(not_utf8)
    assert problems
    assert any("UTF-8" in problem for problem in problems)
    assert _snapshot(not_utf8) == before

    no_table = tmp_path / "no-table"
    no_table.mkdir()
    (no_table / "pyproject.toml").write_text("[build-system]\nrequires = []\n", encoding="utf-8")
    before = _snapshot(no_table)
    problems = author_problems(no_table)
    assert problems
    assert any("[project]" in problem for problem in problems)
    assert _snapshot(no_table) == before

    a_directory = tmp_path / "a-directory"
    (a_directory / "pyproject.toml").mkdir(parents=True)
    before = _snapshot(a_directory)
    problems = author_problems(a_directory)
    assert problems
    assert any("pyproject.toml" in problem for problem in problems)
    assert _snapshot(a_directory) == before
    assert (a_directory / "pyproject.toml").is_dir()

    if os.geteuid() == 0:
        pytest.skip("an unreadable file cannot be planted as root")
    unreadable = tmp_path / "unreadable"
    unreadable.mkdir()
    project_path = unreadable / "pyproject.toml"
    project_path.write_bytes(PYPROJECT.read_bytes())
    project_path.chmod(0o000)
    try:
        before = _snapshot(unreadable)
        problems = author_problems(unreadable)
        assert problems
        assert any("pyproject.toml" in problem for problem in problems)
        assert _snapshot(unreadable) == before
    finally:
        project_path.chmod(0o644)

    for root in (missing, malformed, not_utf8, no_table, a_directory):
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            assert NOREPLY not in text
            assert HOLDER not in text
