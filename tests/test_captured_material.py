"""Captured module code and the fishery opening stay out of the tree.

The needles are built at runtime so this file does not store them whole.
"""

from __future__ import annotations

import subprocess

from test_essay_author import tracked_text

MODULE_CODE = "ENVS" + "5003HK"
FISHERY_OPENING = "When is it fair to close a " + "fishery"


def _hits(root=None) -> list[str]:
    found: list[str] = []
    for name, text in tracked_text(root=root):
        if MODULE_CODE in text or FISHERY_OPENING in text:
            found.append(name)
    return found


def test_captured_markers_stay_out_of_the_tree():
    """The working tree has neither the captured module code nor that opening."""
    assert _hits() == []


def test_the_captured_scan_reads_a_tree_without_git(monkeypatch, tmp_path):
    """Without git, the scan reads files on disk and skips a tool cache."""

    def unavailable(*_args, **_kwargs):
        raise subprocess.CalledProcessError(128, ["git", "ls-files"])

    monkeypatch.setattr(subprocess, "check_output", unavailable)
    root = tmp_path / "unpacked"
    note = root / "notes" / "essay.md"
    note.parent.mkdir(parents=True)
    note.write_text(FISHERY_OPENING + "\n", encoding="utf-8")
    cache = root / ".mypy_cache"
    cache.mkdir()
    (cache / "secret.txt").write_text(MODULE_CODE + "\n", encoding="utf-8")
    assert _hits(root) == ["notes/essay.md"]
