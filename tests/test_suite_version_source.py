"""The suite reads the package version instead of repeating a literal.

A release bumps the version in a few product files. A test that pins the version
string in its own assert keeps the old number, so the suite fails on the next
tree even though nothing in the product changed. These checks read the test files
as text and as syntax trees, so the rule covers the whole suite rather than one
file at a time.

Ids are seated once, in the docstring of the test that proves them. The phrases a
deny list hunts for are not stored here; the deny lists themselves stay opaque.
"""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1] / "tests"
# An assert that pins a version assignment, such as the pyproject line or the
# package line. A bare version comparison, such as an update check between two
# older numbers, is not this shape.
PINNED_VERSION = re.compile(r"\bversion\s*=\s*[\"']\d+\.\d+\.\d+[\"']")
VERSION_NUMBER = re.compile(r"\b\d+\.\d+\.\d+\b")
OPAQUE_ID = re.compile(r"[a-z]-\d+")
DIGEST = re.compile(r"[0-9a-f]{64}")
DOCSTRING_OWNERS = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
# The files whose version check now reads the package value.
VERSION_FILES = (
    "test_citation_list.py",
    "test_cite_id_and_quote.py",
    "test_cite_keep.py",
    "test_final_cover_opening.py",
    "test_stage10_close_and_findings.py",
    "test_word_title_limit.py",
)
# The tests that already read the package value, kept here so a later sweep
# cannot drop the import from one of them.
ALREADY_READING = (
    "test_essay_cover.py",
    "test_essay_traps.py",
    "test_essay_voice.py",
    "test_essay_promise.py",
    "test_license_metadata.py",
    "test_docs_truth.py",
    "test_build_commit.py",
)


def _tree(name: str) -> ast.Module:
    return ast.parse((TESTS / name).read_text(encoding="utf-8"))


def _asserted_strings(tree: ast.Module) -> list[str]:
    """Every string constant inside an assert, wherever it sits in the file."""
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        for part in ast.walk(node.test):
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                found.append(part.value)
    return found


def _docstrings(tree: ast.Module) -> list[str]:
    return [
        ast.get_docstring(node, clean=False) or ""
        for node in ast.walk(tree)
        if isinstance(node, DOCSTRING_OWNERS)
    ]


def test_no_test_pins_the_version_as_a_literal():
    """AC-ver-1: A test that checks the version asserts the package value, never a literal number."""
    pinned: list[str] = []
    for path in sorted(TESTS.glob("test_*.py")):
        for text in _asserted_strings(ast.parse(path.read_text(encoding="utf-8"))):
            if PINNED_VERSION.search(text):
                pinned.append(f"{path.name}: {text}")
    assert pinned == []
    for name in VERSION_FILES:
        source = (TESTS / name).read_text(encoding="utf-8")
        assert "from essay_writer import __version__" in source, name
        # The assert interpolates the imported value rather than repeating one.
        assert "f'version = \"{__version__}\"'" in source, name


def test_the_source_id_note_pins_no_version():
    """AC-ver-2: The note in the source id file names no version number, so it cannot go stale."""
    numbers = [
        number
        for note in _docstrings(_tree("test_cite_id_and_quote.py"))
        for number in VERSION_NUMBER.findall(note)
    ]
    assert numbers == []


def test_the_tests_that_already_read_the_package_version_keep_doing_so():
    """AC-ver-3: Every file that already read the package value still imports it and pins no literal."""
    for name in ALREADY_READING:
        tree = _tree(name)
        source = (TESTS / name).read_text(encoding="utf-8")
        assert "__version__" in source, name
        pinned = [text for text in _asserted_strings(tree) if PINNED_VERSION.search(text)]
        assert pinned == [], name


def test_the_package_version_string_matches_pyproject() -> None:
    init_path = TESTS.parent / "src" / "essay_writer" / "__init__.py"
    project_path = TESTS.parent / "pyproject.toml"
    literals: list[str] = []
    for node in ast.parse(init_path.read_text(encoding="utf-8")).body:
        if not isinstance(node, ast.Assign):
            continue
        named = any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets
        )
        if not named:
            continue
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            literals.append(value.value)
    project = tomllib.loads(project_path.read_text(encoding="utf-8"))
    assert literals == [str(project["project"]["version"])]


def test_the_changed_tests_keep_public_wording_and_opaque_deny_ids():
    """AC-ver-4: The wording this update touches carries no deny-list phrase, and every deny list stays on opaque ids."""
    from test_stage10_close_and_findings import _DENY, _leaked

    tree = _tree("test_cite_id_and_quote.py")
    touched = [
        ast.get_docstring(node, clean=False) or ""
        for node in ast.walk(tree)
        if isinstance(node, DOCSTRING_OWNERS)
        and (ast.get_docstring(node, clean=False) or "").startswith("AC-public-1:")
    ]
    assert touched, "the public wording note is missing from the source id file"
    for note in touched:
        assert _leaked(note) == [], note
        assert "0.9." not in note, note
    assert _DENY
    for key, digest in _DENY.items():
        assert OPAQUE_ID.fullmatch(key), key
        assert DIGEST.fullmatch(digest), key
