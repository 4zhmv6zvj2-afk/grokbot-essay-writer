"""Triage must not print planted essay text or paths.

The subprocess is the tool a person runs. Assertions look at stdout, the exit
code, and the report file.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRIAGE = ROOT / "tools" / "incident_triage.py"
ACCEPTANCE = ROOT / "tools" / "release_acceptance.py"

ESSAY = "The fisheries opening stayed on the page."
PATH = "/Users/student/essay.txt"
VOLUME = "/Volumes/secret"


def test_sentinels_match_release_acceptance() -> None:
    text = ACCEPTANCE.read_text(encoding="utf-8")
    assert 'ESSAY_SENTINEL = "The fisheries opening stayed on the page."' in text
    assert 'PATH_SENTINEL = "/Users/student/essay.txt"' in text


def _run(runs: Path, out: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(TRIAGE), "--runs", str(runs)]
    if out is not None:
        command.extend(["--out", str(out)])
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _run_record() -> dict[str, object]:
    return {
        "persona": "error-prone",
        "version": "0.9.21",
        "steps": ["open", "gather", "walk_4b"],
        "faults": ["malformed_payload", "timeout", "crash", "refused_save"],
        "incident_count": 4,
        "stopped": False,
        "stop_code": "",
    }


def test_poisoned_rows_stay_out_of_the_report(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    persona = runs / "error-prone"
    persona.mkdir(parents=True)
    (persona / "run.json").write_text(json.dumps(_run_record()) + "\n", encoding="utf-8")
    rows = [
        {
            "code": "sentinel-row",
            "severity": "warn",
            "disposition": "refuse",
            "message": ESSAY,
            "prompt": PATH,
            "tool": "state",
            "stage": "load",
            "exc": "",
            "build": "",
        },
        {
            "code": "state-damaged",
            "severity": "warn",
            "disposition": "refuse",
            "tool": "state",
            "stage": "load",
            "message": "",
            "prompt": "",
            "exc": "",
            "build": "abc",
            "sequence": "MOD1004AA-1",
            "time": "2020-01-01T00:00:00+00:00",
        },
        {
            "code": "tool-row",
            "severity": "info",
            "disposition": "retry",
            "tool": ESSAY,
            "message": "",
            "prompt": "",
            "exc": "",
            "build": "",
            "stage": "",
        },
        {
            "code": "volume-row",
            "severity": "error",
            "disposition": "fallback",
            "message": VOLUME,
            "tool": "state",
            "stage": "load",
            "exc": "",
            "build": "",
        },
    ]
    payload = "".join(json.dumps(row) + "\n" for row in rows)
    (persona / "incident.jsonl").write_text(payload, encoding="utf-8")
    faults = [
        {
            "persona": "error-prone",
            "fault": "refused_save",
            "origin": "product",
            "observed": "refused",
        },
        {
            "persona": "error-prone",
            "fault": "crash",
            "origin": "harness",
            "observed": "previous_bytes_kept",
        },
    ]
    (persona / "faults.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in faults),
        encoding="utf-8",
    )
    out = tmp_path / "report.txt"
    completed = _run(runs, out)
    assert completed.returncode == 0
    assert completed.stderr == ""
    written = out.read_text(encoding="utf-8")
    assert completed.stdout == written
    for text in (completed.stdout, written):
        assert "state-damaged  1" in text
        assert "sentinel-row" not in text
        assert "tool-row" not in text
        assert "volume-row" not in text
        assert ESSAY not in text
        assert PATH not in text
        assert "/Users/" not in text
        assert "/Volumes/" not in text
        assert "message" not in text
        assert "prompt" not in text
        assert "sequence" not in text
        assert str(tmp_path) not in text
        assert "dropped_rows  3" in text
        product = text.index("By fault product")
        harness = text.index("By fault harness")
        assert product < text.index("refused_save=refused  1") < harness
        assert harness < text.index("crash=previous_bytes_kept  1")


def test_empty_runs_print_the_disclaimer(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    completed = _run(runs)
    assert completed.returncode == 0
    assert completed.stdout.startswith(
        "These four runs are simulations on installed essay-writer 0.9.21. "
        "They are not validation with real students.\n"
    )
    assert "dropped_rows  0" in completed.stdout
    assert "dropped_runs  0" in completed.stdout
    assert ESSAY not in completed.stdout
    assert PATH not in completed.stdout


def test_non_persona_directory_is_not_named(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    (runs / ESSAY).mkdir(parents=True)
    completed = _run(runs)
    assert completed.returncode == 0
    assert ESSAY not in completed.stdout
    assert PATH not in completed.stdout
    assert "/Users/" not in completed.stdout
    assert "dropped_runs  1" in completed.stdout
