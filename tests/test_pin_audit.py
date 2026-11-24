"""The pin audit reports brittle tests and does not write the tree."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "pin_audit.py"
KINDS = ("getsource", "docstring", "source-string", "test-of-test", "filename-pin")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_a_missing_tree_still_exits_zero(tmp_path: Path) -> None:
    """A path that is not a test tree prints an empty count and writes nothing."""
    missing = tmp_path / "absent"
    before = sorted(tmp_path.rglob("*"))
    result = _run(str(missing))
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.startswith("pins: 0 (")
    for kind in KINDS:
        assert f"{kind} 0" in result.stdout
    assert sorted(tmp_path.rglob("*")) == before


def test_each_kind_is_one_line_and_the_tree_stays_put(tmp_path: Path) -> None:
    """Synthetic tests are classified, then the directory bytes are unchanged."""
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_pins.py").write_text(
        "\n".join(
            (
                "import inspect",
                "import test_other",
                "from pathlib import Path",
                "",
                "def test_source():",
                "    assert 'return' in inspect.getsource(len)",
                "",
                "def test_doc():",
                "    assert 'doc' in (test_doc.__doc__ or '')",
                "",
                "def test_text():",
                "    source = Path('src/essay_writer/word.py').read_text(encoding='utf-8')",
                "    assert 'def write_docx' in source",
                "",
                "def test_other_file():",
                "    other = Path('tests/test_other.py').read_text(encoding='utf-8')",
                "    assert 'def test_kept' in other",
                "",
                "def test_name():",
                "    note = 'see tests/test_pin_audit.py'",
                "    assert 'tests/test_pin_audit.py' in note",
                "",
            )
        ),
        encoding="utf-8",
    )
    (tests / "broken.py").write_text("def (\n", encoding="utf-8")
    before = {path: path.read_bytes() for path in tests.rglob("*") if path.is_file()}
    result = _run(str(tests))
    assert result.returncode == 0
    assert result.stderr == ""
    after = {path: path.read_bytes() for path in tests.rglob("*") if path.is_file()}
    assert after == before
    rows = [line for line in result.stdout.splitlines() if not line.startswith("pins:")]
    assert rows
    seen: set[str] = set()
    for line in rows:
        path, kind, target = (part.strip() for part in line.split("|", 2))
        assert path.startswith("tests/test_pins.py:")
        assert kind in KINDS
        assert target
        seen.add(kind)
    assert seen == set(KINDS)
    summary = result.stdout.splitlines()[-1]
    assert summary.startswith("pins: ")
    for kind in KINDS:
        assert kind in summary


def test_the_checkout_report_is_well_formed() -> None:
    """The real suite prints one row per pin and a matching count."""
    result = _run()
    assert result.returncode == 0
    assert result.stderr == ""
    lines = result.stdout.splitlines()
    assert lines[-1].startswith("pins: ")
    assert int(lines[-1].split()[1]) == len(lines) - 1
    for line in lines[:-1]:
        _path, kind, _target = (part.strip() for part in line.split("|", 2))
        assert kind in KINDS
    assert int(lines[-1].split()[1]) > 0
