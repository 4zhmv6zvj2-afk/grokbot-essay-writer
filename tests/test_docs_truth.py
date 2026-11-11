"""Guards that the human docs match the tree they describe.

The review that prompted these checks found the README, SECURITY, CONTRIBUTING,
and docs/testing pages carrying stale test counts, a stale support table, a
broken glossary link, and confirm-gate claims stronger than the code. These
tests fail on the next version bump until the docs are updated with it.
"""

from __future__ import annotations

import re
from pathlib import Path

from essay_writer import __version__

ROOT = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_security_supported_versions_lists_the_current_line() -> None:
    security = _read("SECURITY.md")
    supported = security.split("## Supported versions", 1)[1].split("##", 1)[0]
    line = ".".join(__version__.split(".")[:2])
    assert f"| {line}.x |" in supported
    assert "yes" in supported


def test_readme_verify_example_matches_the_current_version() -> None:
    verify = _read("README.md").split("## Verify a release", 1)[1]
    assert f"essay_writer-{__version__}-py3-none-any.whl" in verify
    assert f"essay_writer-{__version__}.tar.gz" in verify
    assert f"v{__version__}" in verify


def test_readme_verify_section_names_the_checks() -> None:
    verify = _read("README.md").split("## Verify a release", 1)[1]
    assert "shasum -a 256 -c SHA256SUMS" in verify
    assert "cosign verify-blob" in verify
    assert "gh attestation verify" in verify


def test_docs_have_no_stale_test_counts() -> None:
    for name in ("README.md", "CONTRIBUTING.md", "docs/testing.md"):
        assert "1078" not in _read(name), name
    testing = _read("docs/testing.md")
    for stale in ("~65s", "22,220", "2,917", "213 calls", "51 files", "437 KB"):
        assert stale not in testing, stale


def test_architecture_glossary_link_resolves() -> None:
    architecture = _read("ARCHITECTURE.md")
    match = re.search(r"\[docs/GLOSSARY\.md\]\(([^)]+)\)", architecture)
    assert match, "the docs/GLOSSARY.md link is missing"
    assert match.group(1) == "docs/GLOSSARY.md"
    assert (ROOT / match.group(1)).is_file()


def test_confirm_gate_overclaims_are_gone() -> None:
    readme = _read("README.md")
    assert "Nothing is saved until the Confirm" not in readme
    assert "bound to the exact arguments" not in readme
    security = _read("SECURITY.md")
    assert "must pass before any file is changed" not in security


def test_the_docs_cover_a_checksum_file_that_omits_the_zip() -> None:
    """AC3. Both docs explain a present checksum file that does not list the zip."""
    for name in ("README.md", "SECURITY.md"):
        text = _read(name)
        paragraph = " ".join(text.split())
        assert "present but" in paragraph, name
        assert "no entry for the zip" in paragraph, name
        assert "unverified" in paragraph, name
        # A missing entry is not the same as a missing file.
        assert "rather than" in paragraph or "not the same as no" in paragraph, name
