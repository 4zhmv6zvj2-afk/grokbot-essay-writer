"""The release tag, the expected version, and the wheel name stay one pin."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import pilot_schema as schema  # noqa: E402
from pilot_simulation import parse_args, release_pin  # noqa: E402

TRIAGE = TOOLS / "incident_triage.py"


def test_default_wheel_name_matches_the_pinned_version() -> None:
    version, wheel = release_pin(schema.TAG)
    assert version == schema.VERSION == "0.9.21"
    assert wheel == schema.WHEEL_NAME == f"essay_writer-{version}-py3-none-any.whl"
    assert parse_args([]).tag == schema.TAG


def test_another_tag_keeps_the_wheel_name_and_version_together() -> None:
    version, wheel = release_pin("v1.2.3")
    assert version == "1.2.3"
    assert wheel == f"essay_writer-{version}-py3-none-any.whl"


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


def test_triage_names_the_requested_version_and_the_default_stays(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _persona(runs, "1.2.3")
    requested = subprocess.run(
        [sys.executable, str(TRIAGE), "--runs", str(runs), "--version", "1.2.3"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert requested.returncode == 0
    assert requested.stdout.startswith(
        "These four runs are simulations on installed essay-writer 1.2.3. "
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
        "These four runs are simulations on installed essay-writer 0.9.21. "
    )
    assert "dropped_runs  1" in default.stdout
