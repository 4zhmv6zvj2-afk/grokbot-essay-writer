"""What each seat is given to read. The reviewer does not get the writing notes."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_HELPERS = _ROOT / "docs" / "academic-writing-helpers.md"
_HARVARD = _ROOT / "docs" / "referencing-harvard.md"


def seat_reading(seat: str) -> str:
    """Research reads the writing helpers. Write also reads Harvard Referencing.

    The reviewer seat reads neither file.
    """
    helpers = _HELPERS.read_text(encoding="utf-8")
    if seat == "research":
        return helpers
    if seat == "write":
        harvard = _HARVARD.read_text(encoding="utf-8")
        return helpers + "\n\n" + harvard
    return ""
