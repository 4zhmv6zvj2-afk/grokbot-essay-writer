"""Guards for the release-proof chain: pins, verify-after-sign, and reproduce.

The review of v0.6.3 found the "reproducible build" claim proved only inside one
floating CI run: ``runs-on: ubuntu-latest``, cosign installed at whatever the
installer defaulted to, and signing never followed by verification. These
checks pin the workflow strings that close those gaps, so weakening the proof
is a visible test failure rather than a silent regression. The values are
deliberately literal: a runner image, cosign pin, or identity change must be
reviewed and re-pinned here.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
CI = WORKFLOWS / "ci.yml"
RELEASE = WORKFLOWS / "release.yml"
REPRODUCE = WORKFLOWS / "reproduce.yml"

PINNED_RUNNER = "ubuntu-24.04"
COSIGN_RELEASE = "v3.1.4"
COSIGN_INSTALLER_ACTION = "sigstore/cosign-installer@756fe2d284c7292c4e9b62c8a28f1e5629c59532"
CERTIFICATE_IDENTITY = (
    "https://github.com/4zhmv6zvj2-afk/grokbot-essay-writer"
    "/.github/workflows/release.yml@refs/heads/main"
)
CERTIFICATE_OIDC_ISSUER = "https://token.actions.githubusercontent.com"
REPOSITORY = "4zhmv6zvj2-afk/grokbot-essay-writer"
CHECKOUT_ACTION = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
SETUP_PYTHON_ACTION = "actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _job(workflow: str, name: str) -> str:
    """Text of one top-level job block in a GitHub workflow file."""
    match = re.search(rf"(?m)^  {re.escape(name)}:\s*$", workflow)
    assert match, f"no {name} job"
    following = re.compile(r"(?m)^  [A-Za-z0-9_-]+:\s*$").search(workflow, match.end())
    end = following.start() if following else len(workflow)
    return workflow[match.start() : end]


def _steps(job: str) -> list[tuple[str, str]]:
    """(name, text) for every named step in a job block, in file order."""
    starts = list(re.finditer(r"(?m)^      - name: (.+)$", job))
    steps = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(job)
        steps.append((match.group(1).strip(), job[match.start() : end]))
    return steps


def _step(job: str, name: str) -> str:
    for step_name, text in _steps(job):
        if step_name == name:
            return text
    raise AssertionError(f"no {name!r} step in the job")


def _step_index(job: str, name: str) -> int:
    names = [step_name for step_name, _ in _steps(job)]
    assert name in names, f"no {name!r} step in the job"
    return names.index(name)


def _pinned_runner_lines(workflow: str) -> list[str]:
    """Every ``runs-on:`` value in a workflow, comments excluded."""
    return re.findall(r"(?m)^\s*runs-on:\s*(\S+)\s*$", workflow)


def test_release_job_runs_on_the_pinned_runner_image() -> None:
    release = _read(RELEASE)
    job = _job(release, "release")
    assert f"runs-on: {PINNED_RUNNER}" in job
    # ubuntu-latest floats to a new image without a review.
    assert "ubuntu-latest" not in _pinned_runner_lines(release)


def test_ci_ubuntu_jobs_use_the_same_pinned_image() -> None:
    ci = _read(CI)
    for name in ("test", "artifacts"):
        assert f"runs-on: {PINNED_RUNNER}" in _job(ci, name), name
    # macOS may stay on the floating label; Ubuntu may not.
    assert "ubuntu-latest" not in _pinned_runner_lines(ci)


def test_cosign_is_pinned_by_action_sha_and_explicit_release() -> None:
    job = _job(_read(RELEASE), "release")
    install = _step(job, "Install cosign")
    assert COSIGN_INSTALLER_ACTION in install
    assert re.search(r"@[0-9a-f]{40}\b", install), "cosign-installer is not commit-pinned"
    assert f'cosign-release: "{COSIGN_RELEASE}"' in install
    assert re.fullmatch(r"v\d+\.\d+\.\d+", COSIGN_RELEASE), "pin a concrete cosign tag"
    assert not re.search(r"cosign-release:\s*[\"']?(latest|main)\b", install)


def test_signing_is_followed_by_cosign_verification() -> None:
    job = _job(_read(RELEASE), "release")
    verify = _step(job, "Verify the Sigstore signatures with cosign")
    # Fail on any mismatch: set -e and an explicit non-zero exit.
    assert "set -euo pipefail" in verify
    assert "exit 1" in verify
    assert "cosign verify-blob" in verify
    assert "--bundle" in verify
    assert f'--certificate-identity "{CERTIFICATE_IDENTITY}"' in verify
    assert f'--certificate-oidc-issuer "{CERTIFICATE_OIDC_ISSUER}"' in verify
    # The wheel, the sdist, and the checksum file are all verified.
    for artifact in ('"dist/*.whl"', '"dist/*.tar.gz"', '"dist/SHA256SUMS"'):
        assert artifact in verify
    # The verification runs before the bundles are uploaded, so nothing that
    # does not verify can ship.
    assert _step_index(job, "Sign the build artifacts with Sigstore") < _step_index(
        job, "Verify the Sigstore signatures with cosign"
    )
    assert _step_index(job, "Verify the Sigstore signatures with cosign") < _step_index(
        job, "Upload the signature bundles to the release"
    )


def test_build_provenance_is_verified_with_gh_attestation_verify() -> None:
    job = _job(_read(RELEASE), "release")
    verify = _step(job, "Verify the build provenance with gh attestation verify")
    assert "gh attestation verify" in verify
    assert f"--repo {REPOSITORY}" in verify
    assert "dist/*.whl" in verify
    assert "dist/*.tar.gz" in verify
    # The provenance must exist before it can be verified; run after attestation.
    assert _step_index(job, "Attest build provenance") < _step_index(
        job, "Verify the build provenance with gh attestation verify"
    )


def test_reproduce_workflow_has_dispatch_and_weekly_schedule() -> None:
    reproduce = _read(REPRODUCE)
    assert re.search(r"(?m)^on:\s*$", reproduce)
    assert "workflow_dispatch:" in reproduce
    assert "tag:" in reproduce
    assert re.search(r"(?m)^  schedule:\s*$", reproduce)
    assert re.search(r'(?m)^\s*- cron: "0 6 \* \* 1"$', reproduce), "not the weekly cron"
    # The input may be empty; the workflow resolves the latest release itself.
    assert "REQUESTED_TAG: ${{ inputs.tag }}" in reproduce
    assert "releases/latest" in reproduce
    assert "--jq '.tag_name'" in reproduce


def test_reproduce_workflow_is_read_only_and_pinned() -> None:
    reproduce = _read(REPRODUCE)
    job = _job(reproduce, "reproduce")
    assert re.search(r"(?m)^permissions:\n  contents: read$", reproduce)
    assert "contents: write" not in reproduce
    assert "id-token: write" not in reproduce
    assert f"runs-on: {PINNED_RUNNER}" in job
    assert "ubuntu-latest" not in _pinned_runner_lines(reproduce)
    assert CHECKOUT_ACTION in job
    assert SETUP_PYTHON_ACTION in job
    assert 'python-version: "3.12.13"' in job


def test_reproduce_workflow_downloads_the_published_assets() -> None:
    job = _job(_read(REPRODUCE), "reproduce")
    download = _step(job, "Download the published release assets")
    assert "gh release download" in download
    assert "sha256sum -c SHA256SUMS" in download
    checkout = _step(job, "Check out the tagged tree")
    assert "ref: ${{ steps.release.outputs.tag }}" in checkout


def test_reproduce_workflow_rebuilds_and_compares_against_sha256sums() -> None:
    job = _job(_read(REPRODUCE), "reproduce")
    assert "--require-hashes -r requirements-build.txt" in job
    assert "SOURCE_DATE_EPOCH=$(git log -1 --format=%ct)" in job
    rebuild = _step(job, "Rebuild the artifacts from the tag")
    assert "python tools/reproducible_build.py --outdir rebuilt" in rebuild
    compare = _step(job, "Compare the rebuilt hashes with the published SHA256SUMS")
    assert "SHA256SUMS" in compare
    assert "published" in compare
    assert "rebuilt" in compare
    # A hash mismatch must fail the run, not just print a table.
    assert "MISMATCH" in compare
    assert "sys.exit(1)" in compare
