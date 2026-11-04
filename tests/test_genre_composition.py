"""Pack A composition: shared stage bodies plus additive genre sections."""

from __future__ import annotations

from essay_writer.prompt_content import CHECKLISTS, GENRE_ADDITIONS, SHARED_STAGES
from essay_writer.writing_basics import basics_lines


def test_rewritten_stages_have_a_shared_body() -> None:
    for stage in SHARED_STAGES:
        assert CHECKLISTS[stage], stage


def test_genre_lines_are_shared_plus_additions() -> None:
    for stage in SHARED_STAGES:
        for genre in ("essay", "report", "diary"):
            assert basics_lines(stage, genre) == (
                CHECKLISTS[stage] + GENRE_ADDITIONS[(genre, stage)]
            ), (stage, genre)


def test_no_genre_is_empty_for_the_rewritten_stages() -> None:
    for stage in SHARED_STAGES:
        for genre in ("essay", "report", "diary"):
            assert basics_lines(stage, genre), (stage, genre)


def test_shared_and_genre_sections_do_not_repeat_a_bullet() -> None:
    for stage in SHARED_STAGES:
        shared = set(CHECKLISTS[stage])
        for genre in ("essay", "report", "diary"):
            extra = set(GENRE_ADDITIONS[(genre, stage)])
            assert not (shared & extra), (stage, genre, shared & extra)
