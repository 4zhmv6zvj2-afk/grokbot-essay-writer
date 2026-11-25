"""tests/ and tools/ may name a 0.9 release only on the allowlist.

The scanned form is built from pieces in this file. A literal of that form here
would fail the scan of this file.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = re.compile(r"v?0\.9\.\d+")
FIXTURE_PREFIX = "tests/fixtures/state/"
ANY_PATHS = frozenset(
    {
        "tests/test_essay_author.py",
        "tests/test_license_metadata.py",
    }
)


def _release(patch: str) -> str:
    """One 0.9 patch. Split so this file does not contain the scanned form."""
    return "0" + ".9." + patch


VERSIONS = {
    "tests/test_state_fixtures.py": frozenset({_release("14"), _release("18"), _release("19")}),
    "tools/release_acceptance.py": frozenset({_release("19")}),
    "tools/tag_release.py": frozenset({_release("19")}),
}


def forbidden_release_pins(root: Path) -> list[str]:
    """Every ``v?0.9.x`` under tests/ and tools/ that the allowlist does not name."""
    found: list[str] = []
    for base in ("tests", "tools"):
        folder = root / base
        if not folder.is_dir():
            continue
        paths = sorted(path for path in folder.rglob("*") if path.is_file())
        for path in paths:
            if "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            rel = path.relative_to(root).as_posix()
            if rel.startswith(FIXTURE_PREFIX) or rel in ANY_PATHS:
                continue
            allowed = VERSIONS.get(rel)
            for lineno, line in enumerate(text.splitlines(), 1):
                for match in PIN.finditer(line):
                    token = match.group(0)
                    version = token[1:] if token.startswith("v") else token
                    if allowed is not None and version in allowed:
                        continue
                    found.append(f"{rel}:{lineno}: {token}")
    return found


def test_tests_and_tools_keep_only_allowlisted_release_pins() -> None:
    assert forbidden_release_pins(ROOT) == []


def test_a_seeded_tip_pin_fails_the_scan(tmp_path: Path) -> None:
    tip = _release("21")
    scanned = tmp_path / "tests"
    scanned.mkdir()
    (scanned / "test_seed.py").write_text(f"TAG = {tip!r}\n", encoding="utf-8")
    assert forbidden_release_pins(tmp_path) == [f"tests/test_seed.py:1: {tip}"]


def test_release_tools_allow_only_the_fixture_version(tmp_path: Path) -> None:
    fixture = _release("19")
    tip = _release("21")
    for name in ("release_acceptance.py", "tag_release.py"):
        root = tmp_path / name
        path = root / "tools" / name
        path.parent.mkdir(parents=True)
        path.write_text(f"example = {fixture!r}\n", encoding="utf-8")
        assert forbidden_release_pins(root) == []
        path.write_text(
            f"example = {fixture!r}\nTAG = {('v' + tip)!r}\n",
            encoding="utf-8",
        )
        assert forbidden_release_pins(root) == [f"tools/{name}:2: v{tip}"]


def test_state_fixture_loader_rejects_a_tip_pin(tmp_path: Path) -> None:
    tip = _release("21")
    path = tmp_path / "tests" / "test_state_fixtures.py"
    path.parent.mkdir()
    path.write_text(f"plant = {tip!r}\n", encoding="utf-8")
    assert forbidden_release_pins(tmp_path) == [f"tests/test_state_fixtures.py:1: {tip}"]


def test_old_state_fixtures_may_name_their_versions(tmp_path: Path) -> None:
    tip = _release("21")
    path = tmp_path / "tests" / "fixtures" / "state" / "old" / "state.json"
    path.parent.mkdir(parents=True)
    path.write_text(f'{{"shipped_by": {tip!r}}}\n', encoding="utf-8")
    assert forbidden_release_pins(tmp_path) == []
