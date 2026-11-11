"""Guards for the shared Python version policy.

The policy lives in the public python-mcp-bootstrap repository
(``docs/version-policy.md``): the floor is the 3.12 line, CI runs the lines
3.12-3.15, resolves the latest patch in each line, and prints it; the committed
``.python-version`` names the 3.15 line, and the release build keeps its exact
3.12.13 pin. These checks pin the policy files and the vendored release on
purpose: a change to any of them is a policy change and should be reviewed.
"""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / ".github" / "workflows" / "ci.yml"
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
VENDOR = ROOT / "src" / "essay_writer" / "_vendor"


def _job(workflow: str, name: str) -> str:
    """Text of one top-level job block in a GitHub workflow file."""
    match = re.search(rf"(?m)^  {re.escape(name)}:\s*$", workflow)
    assert match, f"no {name} job"
    following = re.compile(r"(?m)^  [A-Za-z0-9_-]+:\s*$").search(workflow, match.end())
    end = following.start() if following else len(workflow)
    return workflow[match.start() : end]


def _matrix_versions(job: str) -> list[str]:
    match = re.search(r"(?m)^\s*matrix:\s*$\n(?:\s*#.*\n)*\s*python-version:\s*\[(.*?)\]", job)
    assert match, "no Python matrix"
    return [item.strip().strip("\"'") for item in match.group(1).split(",")]


def test_ci_matrix_uses_version_lines() -> None:
    workflow = CI.read_text(encoding="utf-8")
    job = _job(workflow, "test")
    assert _matrix_versions(job) == ["3.12", "3.13", "3.14", "3.15"]
    # check-latest resolves the newest patch in each line; python -VV prints it.
    assert "check-latest: true" in job
    assert "python -VV" in job
    # Patch pins belong in neither the matrix nor the workflow.
    assert "3.12.13" not in workflow


def test_coverage_is_measured_on_the_3_12_line() -> None:
    job = _job(CI.read_text(encoding="utf-8"), "test")
    assert "if: matrix.python-version == '3.12'" in job
    assert "if: matrix.python-version != '3.12'" in job
    assert "--cov-fail-under=85" in job


def test_macos_job_runs_the_3_15_line() -> None:
    job = _job(CI.read_text(encoding="utf-8"), "test-macos")
    assert 'python-version: "3.15"' in job
    assert "check-latest: true" in job


def test_artifact_job_builds_on_the_3_12_line() -> None:
    job = _job(CI.read_text(encoding="utf-8"), "artifacts")
    assert 'python-version: "3.12"' in job
    assert "check-latest: true" in job


def test_release_build_keeps_the_exact_3_12_13_pin() -> None:
    release = RELEASE.read_text(encoding="utf-8")
    assert 'python-version: "3.12.13"' in release


def test_committed_python_version_names_the_3_15_line() -> None:
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.15"


def test_package_floor_is_3_12() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requires_python = pyproject["project"]["requires-python"]
    assert requires_python == ">=3.12"

    from essay_writer import python_bootstrap as boot
    from essay_writer._vendor import python_mcp_bootstrap as core

    assert boot.REQUIRED == (3, 12, 0)
    assert boot.REQUIRED >= (3, 12, 0)
    # The vendored core carries the same floor as the package.
    assert core.REQUIRED == boot.REQUIRED


def test_vendored_core_is_the_released_0_2_0() -> None:
    manifest = json.loads((VENDOR / "VENDOR.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256((VENDOR / "python_mcp_bootstrap.py").read_bytes()).hexdigest()
    assert manifest["name"] == "python-mcp-bootstrap"
    assert manifest["version"] == "0.2.0"
    assert manifest["tag"] == "v0.2.0"
    assert manifest["commit"].startswith("fd8e0b9")
    assert manifest["sha256"] == digest
    assert "local_patch" not in manifest
