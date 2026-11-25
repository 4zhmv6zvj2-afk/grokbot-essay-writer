"""Packaged tip sheet and handbook load from the wheel, not a checkout path."""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

from essay_writer import build_status, debug_log, handbook
from essay_writer.build_status import tip_sheet
from essay_writer.handbook import read_handbook
from essay_writer.runtime_data import HANDBOOK, TIP_SHEET, handbook_text, tip_sheet_text

REPO = Path(__file__).resolve().parents[1]
DOCS_TIP = REPO / "docs" / "templates" / "mid-status.md"
DOCS_HANDBOOK = REPO / "docs" / "referencing-harvard.md"


def test_packaged_runtime_files_match_the_docs_copies() -> None:
    assert tip_sheet_text() == DOCS_TIP.read_text(encoding="utf-8")
    assert handbook_text() == DOCS_HANDBOOK.read_text(encoding="utf-8")
    assert (
        hashlib.sha256(tip_sheet_text().encode()).hexdigest()
        == hashlib.sha256(DOCS_TIP.read_bytes()).hexdigest()
    )
    assert TIP_SHEET.read_text(encoding="utf-8") == tip_sheet_text()
    assert HANDBOOK.read_text(encoding="utf-8") == handbook_text()


def test_runtime_loaders_do_not_use_checkout_parents() -> None:
    """The 0.9.20 crash: Path(__file__).parents[2] / docs/... from a wheel."""
    status_src = inspect.getsource(build_status)
    assert ' / "docs" / "templates" / "mid-status.md"' not in status_src
    assert "parents[2]" not in status_src
    handbook_src = inspect.getsource(handbook)
    assert "handbook_text()" in handbook_src
    assert "handbook_body" in handbook_src
    land_src = inspect.getsource(debug_log._land_sha_from_file)
    assert "_checkout_root" in inspect.getsource(debug_log)
    assert "parents[2]" not in land_src


def test_tip_sheet_and_handbook_load_without_checkout_docs(monkeypatch, tmp_path) -> None:
    """A missing checkout docs tree must not stop the packaged loaders."""
    monkeypatch.setattr(
        "essay_writer.handbook.handbook_path",
        lambda: tmp_path / "missing" / "referencing-harvard.md",
    )
    monkeypatch.setattr(
        "essay_writer.known_paths.repo_root",
        lambda: tmp_path / "not-a-checkout",
    )
    loaded = tip_sheet()
    assert loaded["any"]["start"]
    checked = read_handbook()
    assert checked["checked"] is True
    assert checked["endnote"] == "Harvard"
    assert checked["handbook"] == "essay_writer.runtime/referencing-harvard.md"
