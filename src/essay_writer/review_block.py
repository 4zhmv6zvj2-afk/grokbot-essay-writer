"""The writer cannot clear a review. This number does not increase."""

WRITER_CLEARS_LEFT = 0
PERSON_BLOCK = "You can't clear this review. Only the reviewer can clear it."


def writer_clears_left() -> int:
    return WRITER_CLEARS_LEFT
