"""What each seat is given to read. The reviewer does not get the writing notes."""

from __future__ import annotations

from essay_writer.prompt_loader import raw


def seat_reading(seat: str) -> str:
    """The write seat reads the stage rules and Harvard Referencing.

    The reviewer seat reads neither. The old research seat was never wired and
    is gone; the research stages read the writing helpers from the server
    instructions.
    """
    if seat == "write":
        return raw("seats/write.md")
    return ""
