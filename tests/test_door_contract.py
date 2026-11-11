"""Door descriptions are the contract. Writing guidance stays in the stage rules.

Opaque ids. The acceptance label for each case is in the docstring.
"""

from __future__ import annotations

import json
from pathlib import Path

from test_prompt_budget import MAX_ASSEMBLED_TOKENS

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.doors import DOORS
from essay_writer.prompt_content import SHARED_STAGE_SECTIONS
from essay_writer.prompt_loader import bullets, sections
from essay_writer.server import INSTRUCTIONS
from essay_writer.stage_llm import stage_settings, stage_tool_description
from essay_writer.writing_basics import CHECKLISTS

REPO = Path(__file__).resolve().parents[1]
SNAPSHOT = REPO / "tests" / "snapshots" / "prompts.json"
MAX_DOOR_CHARS = 1_200
MAX_DOOR_CHARS_TOTAL = 24_000
WRITING_MARKERS = (
    "Basics checklist",
    "Ban AI-glue",
    "Stage LLM",
    "Research file work on this computer",
)


def test_case_1():
    """AC1: Door descriptions are contract-only. Writing checklists live in the stage rules.

    The research-path rule and the stage 4a and 4b checklists stay on those stage
    rules. Cursor and Grok Build read that same rules text. The prompt loader
    still returns flat checklist bullets.
    """
    research_path = SHARED_STAGE_SECTIONS["research_path"]
    for stage in ("4a", "4b"):
        rules = stage_settings(stage)["rules"]
        assert research_path in rules
        assert CHECKLISTS[stage][0] in rules
        assert stage_launch(stage)["settings"]["rules"] == rules
        assert cursor_stage_launch(stage)["settings"]["rules"] == rules
        for line in CHECKLISTS[stage]:
            assert line in rules
    assert bullets("stages/04a.md", "shared") == CHECKLISTS["4a"]
    assert all("\n" not in line for line in CHECKLISTS["4a"])
    for door in DOORS:
        description = door["description"]
        assert research_path not in description
        for marker in WRITING_MARKERS:
            assert marker not in description, door["tool"]
        for stage in ("4a", "4b"):
            assert CHECKLISTS[stage][0] not in description
    stage = next(door["description"] for door in DOORS if door["tool"] == "essay.stage")
    assert stage_tool_description() == stage
    assert "from the stage rules" in stage


def test_case_2():
    """AC2: Each door is at most 1,200 characters, and the doors together are at most 24,000."""
    lengths = {door["tool"]: len(door["description"]) for door in DOORS}
    assert lengths
    over = {tool: count for tool, count in lengths.items() if count > MAX_DOOR_CHARS}
    assert over == {}
    assert sum(lengths.values()) <= MAX_DOOR_CHARS_TOTAL


def test_case_3():
    """AC3: content_check, phrasebank_pointer, and edit_recheck stay, and so does the stage-6 read list."""
    voice = sections("craft/voice.md")
    assert "content_check" in voice and voice["content_check"]
    assert "phrasebank_pointer" in voice and voice["phrasebank_pointer"]
    assert "edit_recheck" in voice and voice["edit_recheck"]
    assert voice["content_check"] in stage_settings("5")["rules"]
    assert voice["phrasebank_pointer"] in stage_settings("5")["rules"]
    assert voice["edit_recheck"] in stage_settings("8")["rules"]
    rules = stage_settings("6")["rules"]
    assert "show the short read list once, then stop" in rules
    assert "Do not rewrite the draft for them." in rules
    read_list = sections("front_office/chat.md")["stage6_read_list"]
    assert read_list.startswith("Read the draft and edit it yourself.")


def test_case_4():
    """AC4: The prompt snapshot matches the live doors, and the assembled prompt stays under the cap."""
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    live = {door["tool"]: door["description"] for door in DOORS}
    assert snapshot["doors"] == live
    assembled = INSTRUCTIONS + "\n" + " ".join(door["description"] for door in DOORS)
    tokens = len(assembled) // 4
    assert tokens < MAX_ASSEMBLED_TOKENS
