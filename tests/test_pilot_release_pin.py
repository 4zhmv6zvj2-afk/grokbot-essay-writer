"""The release tag, the expected version, and the wheel name stay one pin."""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

from pilot_simulation import parse_args, release_pin  # noqa: E402

TRIAGE = TOOLS / "incident_triage.py"
FAKE = "1.2.3"


def _project_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version = tomllib.loads(text)["project"]["version"]
    assert isinstance(version, str)
    return version


def test_a_tag_keeps_the_wheel_name_and_version_together() -> None:
    pin = release_pin(f"v{FAKE}")
    assert pin.tag == f"v{FAKE}"
    assert pin.version == FAKE
    assert pin.wheel_name == f"essay_writer-{FAKE}-py3-none-any.whl"


def test_omitted_tag_uses_the_pyproject_version() -> None:
    project = _project_version()
    pin = release_pin(parse_args([]).tag)
    assert pin.tag == f"v{project}"
    assert pin.version == project
    assert pin.wheel_name == f"essay_writer-{project}-py3-none-any.whl"


def _persona(runs: Path, version: str) -> None:
    folder = runs / "careful"
    folder.mkdir(parents=True)
    record = {
        "persona": "careful",
        "version": version,
        "steps": ["open"],
        "faults": [],
        "incident_count": 0,
        "stopped": False,
        "stop_code": "",
    }
    (folder / "run.json").write_text(json.dumps(record) + "\n", encoding="utf-8")
    (folder / "faults.jsonl").write_text("", encoding="utf-8")
    (folder / "incident.jsonl").write_text("", encoding="utf-8")
    (folder / "incident.jsonl.1").write_text("", encoding="utf-8")


def test_triage_names_the_requested_version_and_the_pyproject_default(tmp_path: Path) -> None:
    project = _project_version()
    runs = tmp_path / "runs"
    _persona(runs, FAKE)
    requested = subprocess.run(
        [sys.executable, str(TRIAGE), "--runs", str(runs), "--version", FAKE],
        capture_output=True,
        text=True,
        check=False,
    )
    assert requested.returncode == 0
    assert requested.stdout.startswith(
        f"These four runs are simulations on installed essay-writer {FAKE}. "
    )
    assert "dropped_runs  0" in requested.stdout
    default = subprocess.run(
        [sys.executable, str(TRIAGE), "--runs", str(runs)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert default.returncode == 0
    assert default.stdout.startswith(
        f"These four runs are simulations on installed essay-writer {project}. "
    )
    dropped = "0" if project == FAKE else "1"
    assert f"dropped_runs  {dropped}" in default.stdout
