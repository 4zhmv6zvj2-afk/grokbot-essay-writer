"""Rule coverage for the shared-only stage briefing."""

from __future__ import annotations

from essay_writer.prompt_content import SHARED_REVISIT, STAGE7_AGENT
from essay_writer.specialists.grok_bot import CHECKLIST_WALK
from essay_writer.stage_llm import STAGE_KEYS, stage_rules_briefing, stage_settings
from essay_writer.writing_basics import STAGE_ORDER, basics_lines

BRIEFING = stage_rules_briefing()


def test_shared_stage_bullets_are_covered() -> None:
    for stage in STAGE_ORDER:
        shared = basics_lines(stage)
        assert shared, stage
        for bullet in shared:
            assert bullet in BRIEFING, (stage, bullet)


def test_genre_only_bullets_stay_out_of_the_briefing() -> None:
    for stage in STAGE_ORDER:
        shared = set(basics_lines(stage))
        for genre in ("essay", "report", "diary"):
            for bullet in set(basics_lines(stage, genre)) - shared:
                assert bullet not in BRIEFING, (stage, genre, bullet)


def test_launch_still_carries_shared_plus_genre() -> None:
    for stage in STAGE_ORDER:
        shared = set(basics_lines(stage))
        for genre in ("essay", "report", "diary"):
            rules = stage_settings(stage, genre)["rules"]
            for bullet in shared:
                assert bullet in rules, (stage, genre, bullet)
            for bullet in set(basics_lines(stage, genre)) - shared:
                assert bullet in rules, (stage, genre, bullet)


def test_common_blocks_appear_once() -> None:
    assert BRIEFING.count(CHECKLIST_WALK) == 1
    assert BRIEFING.count(SHARED_REVISIT) == 1
    assert BRIEFING.count(STAGE7_AGENT) == 1


def test_each_stage_has_its_own_rules() -> None:
    for stage in STAGE_ORDER:
        assert f"Stage {stage} — " in BRIEFING
        assert f"Tracking file: tracking/{stage}.md" in BRIEFING


def test_reviewer_has_rules_but_no_writing_walk() -> None:
    reviewer = stage_settings("eqr")["rules"]
    assert reviewer in BRIEFING
    assert CHECKLIST_WALK not in reviewer
    assert STAGE_KEYS[-1] == "eqr"
