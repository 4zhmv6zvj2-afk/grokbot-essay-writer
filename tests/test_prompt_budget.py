"""Prompt-bundle budget and single-source guards.

The shared craft rules live once in ``prompts/craft/voice.md``. Writing stages
render them once per stage in ``stage_llm.prompt_overlay``; a stage file must not
inline the same sentence again. Non-craft rules shared by several stages live in
``front_office/chat.md`` and render once per relevant stage. The assembled
instructions plus the door descriptions stay under a measured cap so a new copy
fails here before it reaches the first student message.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from essay_writer.doors import DOORS
from essay_writer.prompt_content import (
    CRAFT_BY_STAGE,
    CRAFT_SECTIONS,
    PRECEDENCE,
    SHARED_STAGE_RULES,
    SHARED_STAGE_SECTIONS,
)
from essay_writer.prompt_loader import sections
from essay_writer.seats import seat_reading
from essay_writer.server import INSTRUCTIONS
from essay_writer.stage_llm import stage_rules_briefing, stage_settings
from essay_writer.writing_basics import STAGE_ORDER

REPO = Path(__file__).resolve().parents[1]
PROMPTS = REPO / "src" / "essay_writer" / "prompts"
STAGES_DIR = PROMPTS / "stages"
CRAFT = PROMPTS / "craft" / "voice.md"
WRITING_STAGES = ("5", "6", "7", "8")
GENRES = (None, "essay", "report", "diary")
LONG_LINE = 62

# Empty on purpose. Every repeated non-craft sentence now has one definition in
# the shared prompt layer (front_office/chat.md or CHECKLIST_WALK) and renders
# once per relevant stage. A new repeated long line outside the shared layer
# fails test_stage_files_do_not_repeat_a_long_line.
KNOWN_SHARED_PREFIXES: tuple[str, ...] = ()

# Approximate budget: instructions + every door description, measured on this
# tree. One token is estimated at four characters; no tokenizer dependency.
# 33,497 measured after the shared-rule editorial pass (was 34,000). The
# precedence block renders once in the combined briefing and once per stage
# overlay, and the six inlined gloss copies are gone, so the cap is lowered to
# lock that shrink in.
MAX_ASSEMBLED_TOKENS = 33_600


def _stage_files() -> dict[str, Path]:
    return {path.stem: path for path in sorted(STAGES_DIR.glob("*.md"))}


def _long_bullets(path: Path) -> set[str]:
    return {
        line[2:]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("- ") and len(line[2:]) >= LONG_LINE
    }


def _repeated_long_lines() -> dict[str, set[str]]:
    seen: dict[str, set[str]] = defaultdict(set)
    for stage, path in _stage_files().items():
        for line in _long_bullets(path):
            seen[line].add(stage)
    return {line: stages for line, stages in seen.items() if len(stages) > 1}


def test_craft_sections_are_loaded_from_one_source():
    craft = sections("craft/voice.md")
    assert set(CRAFT_SECTIONS) == set(WRITING_STAGES)
    for stage, keys in CRAFT_SECTIONS.items():
        assert keys, stage
        assert set(keys) <= set(craft), stage
        assert CRAFT_BY_STAGE[stage] == tuple(craft[key] for key in keys), stage


def test_stage_files_do_not_inline_the_shared_craft_rules():
    craft = sections("craft/voice.md")
    for stage, path in _stage_files().items():
        body = path.read_text(encoding="utf-8")
        for name, section in craft.items():
            assert section not in body, (stage, name)


def test_stage_5_to_8_render_each_craft_rule_exactly_once():
    for stage in WRITING_STAGES:
        for genre in GENRES:
            item = stage_settings(stage, genre)
            overlay = item["prompt_overlay"]
            rules = item["rules"]
            assert overlay.count("Craft rules:") == 1, (stage, genre)
            assert rules.count("Craft rules:") == 1, (stage, genre)
            for section in CRAFT_BY_STAGE[stage]:
                assert overlay.count(section) == 1, (stage, genre, section[:40])
            assert overlay in rules
    for stage in ("1", "2", "3", "4a", "4b", "9", "10"):
        assert "Craft rules:" not in stage_settings(stage)["prompt_overlay"]


def test_stage_files_do_not_repeat_a_long_line():
    craft = set(sections("craft/voice.md").values())
    repeated = _repeated_long_lines()
    assert KNOWN_SHARED_PREFIXES == ()
    assert not repeated, sorted(repeated)
    assert not (craft & set(repeated))


def test_stage_files_do_not_inline_a_shared_stage_rule():
    for stage, path in _stage_files().items():
        body = path.read_text(encoding="utf-8")
        assert PRECEDENCE not in body, stage
        for key, section in SHARED_STAGE_SECTIONS.items():
            assert section not in body, (stage, key)


def test_precedence_names_brief_then_rubric_then_the_shared_rules():
    assert "the brief comes first" in PRECEDENCE
    assert "rubric or mark scheme" in PRECEDENCE
    assert "these shared rules" in PRECEDENCE


def test_precedence_is_not_pasted_into_a_stage_or_genre_file():
    paths = [*STAGES_DIR.glob("*.md"), *(PROMPTS / "genres").glob("*.md")]
    for path in paths:
        body = path.read_text(encoding="utf-8").casefold()
        assert "win over these helpers" not in body, path.name
        assert "win over helper defaults" not in body, path.name


def test_shared_stage_rules_render_once_per_relevant_stage():
    for stage in STAGE_ORDER:
        for genre in GENRES:
            item = stage_settings(stage, genre)
            assert item["prompt_overlay"].count(PRECEDENCE) == 1, (stage, genre)
            assert item["rules"].count(PRECEDENCE) == 1, (stage, genre)
            for key, section in SHARED_STAGE_SECTIONS.items():
                expected = 1 if key in SHARED_STAGE_RULES.get(stage, ()) else 0
                assert item["prompt_overlay"].count(section) == expected, (stage, genre, key)


def test_combined_briefing_renders_a_shared_rule_once_per_relevant_stage():
    briefing = stage_rules_briefing()
    assert briefing.count(PRECEDENCE) == 1
    for key, section in SHARED_STAGE_SECTIONS.items():
        stages = [stage for stage, keys in SHARED_STAGE_RULES.items() if key in keys]
        assert stages, key
        assert briefing.count(section) == len(stages), key


def test_assembled_instructions_and_doors_stay_under_the_token_cap():
    doors = " ".join(door["description"] for door in DOORS)
    assembled = INSTRUCTIONS + "\n" + doors
    tokens = len(assembled) // 4
    assert tokens < MAX_ASSEMBLED_TOKENS, (tokens, MAX_ASSEMBLED_TOKENS)


def test_dead_research_seat_is_gone():
    assert not (PROMPTS / "seats" / "research.md").exists()
    assert seat_reading("research") == ""
    assert seat_reading("write")
