"""The generated helper lists the shared rules a stage already renders.

Opaque ids. The acceptance label for each case is in the docstring.
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.doors import DOORS
from essay_writer.prompt_content import CRAFT_BY_STAGE, SHARED_STAGE_LINES
from essay_writer.prompt_loader import bullets, sections
from essay_writer.stage_llm import stage_settings
from essay_writer.writing_basics import CHECKLISTS

REPO = Path(__file__).resolve().parents[1]
HELPERS = REPO / "docs" / "academic-writing-helpers.md"
MARK = "**Shared rules:**"


def _generate_docs():
    path = REPO / "tools" / "generate_docs.py"
    spec = importlib.util.spec_from_file_location("generate_docs", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_case_1():
    """AC1: Shared craft and shared stage lines are in the generated helper.

    The checklist blocks stay the stage checklists. Stages that already render
    shared craft, or a shared stage line, list that text under Shared rules.
    Cursor and Grok Build still read the same stage rules. The generator check
    matches the file.
    """
    helper = HELPERS.read_text(encoding="utf-8")
    module = _generate_docs()
    assert module.render(helper) == helper
    voice = sections("craft/voice.md")
    for key in ("content_check", "phrasebank_pointer", "edit_recheck"):
        assert voice[key] in helper
    assert helper.count(voice["content_check"]) == 2
    assert helper.count(voice["phrasebank_pointer"]) == 1
    assert helper.count(voice["edit_recheck"]) == 1
    for stage, lines in CRAFT_BY_STAGE.items():
        rules = stage_settings(stage)["rules"]
        for line in lines:
            assert line in rules
            assert line in helper
            assert helper.count(line) == sum(
                1 for values in CRAFT_BY_STAGE.values() if line in values
            )
    for stage, lines in SHARED_STAGE_LINES.items():
        rules = stage_settings(stage)["rules"]
        for line in lines:
            assert line in rules
            assert line in helper
    for stage, checklist in CHECKLISTS.items():
        assert checklist[0] in helper
        if stage in CRAFT_BY_STAGE or stage in SHARED_STAGE_LINES:
            assert MARK in helper
    for door in DOORS:
        assert voice["content_check"] not in door["description"]
        assert MARK not in door["description"]
    for stage in ("5", "6", "7", "8"):
        rules = stage_settings(stage)["rules"]
        assert stage_launch(stage)["settings"]["rules"] == rules
        assert cursor_stage_launch(stage)["settings"]["rules"] == rules
    assert "The tool drafts." in helper
    assert "Stage 6 is the student's read-through and feedback, not a tool rewrite." in helper
    assert "Stage 7 asks questions and edits from the student's answers." in helper


def test_case_2():
    """AC2: The voice sections and the stage-6 read list stay. Bullets stay flat.

    The prompt loader still returns one bullet per dashed line.
    """
    voice = sections("craft/voice.md")
    assert voice["content_check"]
    assert voice["phrasebank_pointer"]
    assert voice["edit_recheck"]
    assert voice["content_check"] in stage_settings("5")["rules"]
    assert voice["phrasebank_pointer"] in stage_settings("5")["rules"]
    assert voice["edit_recheck"] in stage_settings("8")["rules"]
    read_list = sections("front_office/chat.md")["stage6_read_list"]
    assert read_list.startswith("Read the draft and edit it yourself.")
    assert "show the short read list once, then stop" in stage_settings("6")["rules"]
    for stage, lines in CHECKLISTS.items():
        assert bullets(f"stages/{_file(stage)}", "shared") == lines
        assert all("\n" not in line for line in lines)
    source = inspect.getsource(bullets)
    assert 'startswith("- ")' in source


def _file(stage: str) -> str:
    names = {
        "1": "01.md",
        "2": "02.md",
        "3": "03.md",
        "4a": "04a.md",
        "4b": "04b.md",
        "5": "05.md",
        "6": "06.md",
        "7": "07.md",
        "8": "08.md",
        "9": "09.md",
        "10": "10.md",
    }
    return names[stage]
