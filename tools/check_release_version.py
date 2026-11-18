"""Check that the release tag, pyproject.toml, uv.lock, and CHANGELOG.md agree.

The release workflow runs this before it builds, signs, or uploads anything:

    python tools/check_release_version.py --tag v0.8.0

Run it from the root of the tree being released. The tag is optional: without
it, the file versions are still compared. The CHANGELOG version is the version
in its newest release heading, so an "## Unreleased" section on top does not
count. Exit status is 0 when the versions agree and 1 when they do not; each
disagreement is printed as a GitHub error annotation.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

RELEASE_HEADING = re.compile(r"^##\s+v?(\d+\.\d+\.\d+)\b")


def pyproject_version(text: str) -> str:
    """The ``[project] version`` in a pyproject.toml document."""
    return str(tomllib.loads(text)["project"]["version"])


def lock_version(text: str) -> str | None:
    """The project version in a uv.lock document, or None when it has no entry."""
    data = tomllib.loads(text)
    for package in data.get("package", []):
        if isinstance(package, dict) and package.get("name") == "essay-writer":
            return str(package.get("version", ""))
    return None


def changelog_version(text: str) -> str | None:
    """The version in the newest release heading, or None if there is none."""
    for line in text.splitlines():
        match = RELEASE_HEADING.match(line)
        if match is not None:
            return match.group(1)
    return None


def compare(project: str, lock: str | None, changelog: str | None, tag: str | None) -> list[str]:
    """Every disagreement between the four sources, in a stable order."""
    problems: list[str] = []
    if lock is None:
        problems.append(
            "uv.lock has no essay-writer package entry, so its version cannot be checked."
        )
    elif lock != project:
        problems.append(
            f"uv.lock project version {lock} does not match pyproject.toml version {project}."
        )
    if changelog is None:
        problems.append("CHANGELOG.md has no release heading, so its version cannot be checked.")
    elif changelog != project:
        problems.append(
            f"CHANGELOG.md version {changelog} does not match pyproject.toml version {project}."
        )
    if tag is not None and tag.removeprefix("v") != project:
        problems.append(f"Tag {tag} does not match pyproject.toml version {project}.")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--tag",
        default=None,
        help="release tag of the tree, for example v0.8.0; omit to skip the tag check",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="root of the tree to check (default: the current directory)",
    )
    args = parser.parse_args(argv)
    root: Path = args.root
    try:
        project = pyproject_version((root / "pyproject.toml").read_text(encoding="utf-8"))
        lock = lock_version((root / "uv.lock").read_text(encoding="utf-8"))
        changelog = changelog_version((root / "CHANGELOG.md").read_text(encoding="utf-8"))
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as exc:
        print(f"::error::the version files were not read: {exc}", file=sys.stderr)
        return 1

    problems = compare(project, lock, changelog, args.tag)
    if problems:
        for problem in problems:
            print(f"::error::{problem}", file=sys.stderr)
        return 1

    if args.tag is None:
        print(f"pyproject.toml, uv.lock, and CHANGELOG.md agree on {project}.")
    else:
        print(
            f"Tag {args.tag} and CHANGELOG.md agree with pyproject.toml and uv.lock on {project}."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
