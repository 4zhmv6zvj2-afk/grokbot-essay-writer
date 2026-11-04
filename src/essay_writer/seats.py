"""What each seat is given to read. The reviewer does not get the writing notes."""

from __future__ import annotations

from essay_writer.prompt_loader import raw


def seat_reading(seat: str) -> str:
    """Research reads the writing helpers. Write also reads Harvard Referencing.

    The reviewer seat reads neither file.
    """
    if seat == "research":
        return raw("seats/research.md")
    if seat == "write":
        return raw("seats/write.md")
    return ""
