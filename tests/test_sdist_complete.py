"""The published sdist must carry every tracked file its docs point at.

The sdist is the build source of record: ``pip install <sdist>`` builds from
it, and the README/CONTRIBUTING inside it are the only docs a source user gets.
These checks pin the six tracked files the v0.6.2 sdist dropped (HISTORY.md and
requirements-runtime.in among them) and the document references that need them.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.in"

# The six tracked files the v0.6.2 sdist omitted. Keep the list literal so a
# dropped include is a visible test failure, not a silently smaller sdist.
PREVIOUSLY_MISSING = (
    "HISTORY.md",
    "requirements-runtime.in",
    ".pre-commit-config.yaml",
    ".github/dependabot.yml",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/workflows/scorecard.yml",
)


def _manifest_lines() -> list[str]:
    return [
        line.strip()
        for line in MANIFEST.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _manifest_ships(path: str) -> bool:
    """Whether MANIFEST.in's include rules pick up a repo-relative path.

    This mirrors the positive setuptools directives used here (include,
    global-include, recursive-include, graft) instead of running setuptools:
    patterns without a slash match the basename, patterns with one match the
    full path. None of the paths checked below is deliberately excluded.
    """
    for line in _manifest_lines():
        directive, _, arguments = line.partition(" ")
        if directive == "graft":
            directory = arguments.strip()
            if path == directory or path.startswith(f"{directory}/"):
                return True
            patterns: list[str] = []
        elif directive in {"include", "global-include"}:
            patterns = arguments.split()
        elif directive == "recursive-include":
            directory, _, pattern_text = arguments.partition(" ")
            patterns = [f"{directory}/{pattern}" for pattern in pattern_text.split()]
        else:
            # exclude, prune and global-exclude only remove paths.
            continue
        for pattern in patterns:
            target = path if "/" in pattern else path.rsplit("/", 1)[-1]
            if fnmatch.fnmatchcase(target, pattern):
                return True
    return False


def test_the_previously_missing_files_are_present_in_the_tree() -> None:
    for path in PREVIOUSLY_MISSING:
        assert (ROOT / path).is_file(), f"{path} is missing from the repository"


def test_manifest_includes_every_previously_missing_file() -> None:
    missing = [path for path in PREVIOUSLY_MISSING if not _manifest_ships(path)]
    assert not missing, f"MANIFEST.in does not ship: {missing}"


def test_readme_history_link_target_is_shipped() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert re.search(r"\[[^\]]*\]\(HISTORY\.md\)", readme), "README.md no longer links HISTORY.md"
    assert _manifest_ships("HISTORY.md")


def test_contributing_runtime_requirements_references_are_shipped() -> None:
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    # CONTRIBUTING documents the runtime requirements set. Whatever files it
    # names (the compiled requirements-runtime.txt and/or the
    # requirements-runtime.in source) must exist in the source distribution the
    # reader is told to read.
    references = set(re.findall(r"requirements-runtime\.(?:in|txt)", contributing))
    assert references, "CONTRIBUTING.md no longer documents the runtime requirements"
    for name in sorted(references):
        assert _manifest_ships(name), f"CONTRIBUTING.md names {name} but the sdist omits it"


def test_runtime_lockfile_names_its_shipped_source() -> None:
    # The shipped lockfile records the compile command, so the .in source it
    # cites must ship too or a source user cannot recompile the runtime set.
    lockfile = (ROOT / "requirements-runtime.txt").read_text(encoding="utf-8")
    assert "requirements-runtime.in" in lockfile
    assert _manifest_ships("requirements-runtime.in")
