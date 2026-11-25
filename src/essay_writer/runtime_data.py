"""Packaged runtime text: tip sheet and handbook.

These files ship inside the wheel. Callers read them through
``importlib.resources``, not through a checkout path. The docs/ copies stay
for humans; tests require the packaged bytes to match.
"""

from __future__ import annotations

from importlib.resources import files

_ROOT = files("essay_writer.runtime")
TIP_SHEET_NAME = "mid-status.md"
HANDBOOK_NAME = "referencing-harvard.md"
TIP_SHEET = _ROOT.joinpath(TIP_SHEET_NAME)
HANDBOOK = _ROOT.joinpath(HANDBOOK_NAME)


def tip_sheet_text() -> str:
    return TIP_SHEET.read_text(encoding="utf-8")


def handbook_text() -> str:
    return HANDBOOK.read_text(encoding="utf-8")
