"""Guards that the release fails when the changelog and the package disagree.

The release workflow compared the tag with ``pyproject.toml`` only, so a tag cut
from a tree whose ``CHANGELOG.md`` still described the previous release passed
every check and shipped. These fixtures pin the replacement: one checker that
compares the tag, the package version, and the changelog version, and a release
workflow that runs it before it builds, signs, or uploads anything.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
CHECKER = ROOT / "tools" / "check_release_version.py"

PYPROJECT = """\
[project]
name = "essay-writer"
version = "{version}"
"""

CHANGELOG = """\
# Changelog

{headings}
"""


def _tree(root: Path, *, project: str, changelog_version: str | None) -> Path:
    """A minimal tree with the two version files, and nothing else."""
    headings = (
        "## Unreleased\n\n- Nothing yet.\n"
        if changelog_version is None
        else f"## {changelog_version} — 2026-11-11\n\n- A change.\n"
    )
    (root / "pyproject.toml").write_text(PYPROJECT.format(version=project), encoding="utf-8")
    (root / "CHANGELOG.md").write_text(
        CHANGELOG.format(headings=headings), encoding="utf-8"
    )
    return root


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("project", "changelog_version", "tag"),
    [
        pytest.param("0.8.0", "0.7.0", "v0.8.0", id="case-1"),
        pytest.param("0.8.0", "0.8.1", "v0.8.0", id="case-2"),
        pytest.param("0.8.0", None, "v0.8.0", id="case-3"),
        pytest.param("0.8.0", "0.8.0", "v0.7.0", id="case-4"),
    ],
)
def test_a_disagreement_fails_the_check(
    tmp_path: Path, project: str, changelog_version: str | None, tag: str
) -> None:
    """AC1. Any disagreement between the three sources exits non-zero."""
    root = _tree(tmp_path, project=project, changelog_version=changelog_version)
    result = _run("--tag", tag, "--root", str(root))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "::error::" in result.stderr


@pytest.mark.parametrize(
    ("project", "changelog_version", "tag"),
    [
        pytest.param("0.8.0", "0.8.0", "v0.8.0", id="case-1"),
        pytest.param("0.8.0", "0.8.0", "0.8.0", id="case-2"),
    ],
)
def test_agreement_passes_the_check(
    tmp_path: Path, project: str, changelog_version: str | None, tag: str
) -> None:
    """AC1. Matching versions exit zero, with or without the leading ``v``."""
    root = _tree(tmp_path, project=project, changelog_version=changelog_version)
    result = _run("--tag", tag, "--root", str(root))
    assert result.returncode == 0, result.stdout + result.stderr


def test_an_unreleased_section_does_not_hide_the_release_version(tmp_path: Path) -> None:
    """AC1. A changelog awaiting its release still reports the newest release."""
    root = _tree(tmp_path, project="0.8.0", changelog_version="0.8.0")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    (root / "CHANGELOG.md").write_text(
        changelog.replace("# Changelog\n", "# Changelog\n\n## Unreleased\n\n- Pending.\n"),
        encoding="utf-8",
    )
    result = _run("--tag", "v0.8.0", "--root", str(root))
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_checked_in_tree_agrees_with_its_version() -> None:
    """AC1. The repository's own files pass the check the release runs."""
    result = _run("--root", str(ROOT))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "agree on" in result.stdout


def test_the_release_workflow_runs_the_check_before_building() -> None:
    """AC1. The release job guards the version before it builds or signs."""
    workflow = RELEASE.read_text(encoding="utf-8")
    guard = workflow.find('python tools/check_release_version.py --tag "${TAG}"')
    assert guard >= 0, "the release workflow does not check the changelog version"
    for later in (
        "python tools/reproducible_build.py --outdir dist",
        "Sign the build artifacts with Sigstore",
        "Upload the build artifacts to the release",
    ):
        assert workflow.find(later) > guard, f"{later} runs before the version guard"
