"""The look note lives in the two docs. The stage door is unchanged.

Opaque ids. The acceptance label for each case is in the docstring.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.doors import DOORS
from essay_writer.stage_llm import stage_settings

REPO = Path(__file__).resolve().parents[1]
HELPERS = REPO / "docs" / "academic-writing-helpers.md"
WORKFLOW = REPO / "docs" / "workflow.md"
LOOK = "look is the student's own sentence for this stage; omit it and no final look is written."
CHANGED = "A changed look needs a fresh draft."
MARK = "**Shared rules:**"


def test_case_1():
    """essay-u1-d1: the helper and the workflow template say the student's sentence is the look.

    AC1: The look note is in both docs. The stage door keeps its cap.
    The changed-look line stays on the door. The new sentence does not.
    """
    helper = HELPERS.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    template = REPO / "tools" / "doc_templates" / "workflow.md"
    template_text = template.read_text(encoding="utf-8")
    old = "omit it and the stage guidance is the final look."
    assert LOOK in helper
    assert LOOK in workflow
    assert LOOK in template_text
    assert old not in helper
    assert old not in workflow
    assert old not in template_text
    assert helper.index(LOOK) < helper.index("## Stage checklists")
    paragraph = next(
        line for line in workflow.splitlines() if line.startswith("`essay.stage` writes")
    )
    assert "Confirm saves the final look" in paragraph
    assert LOOK in paragraph
    stage = next(door for door in DOORS if door["tool"] == "essay.stage")
    assert CHANGED in stage["description"]
    assert LOOK not in stage["description"]
    assert len(stage["description"]) <= 1200
    assert sum(len(door["description"]) for door in DOORS) <= 24000
    rules = stage_settings("5")["rules"]
    assert stage_launch("5")["settings"]["rules"] == rules
    assert cursor_stage_launch("5")["settings"]["rules"] == rules


def test_case_2():
    """AC2: Shared rules still has a blank line before the label and after the bullets."""
    helper = HELPERS.read_text(encoding="utf-8")
    path = REPO / "tools" / "generate_docs.py"
    spec = importlib.util.spec_from_file_location("generate_docs", path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    assert module.render(helper) == helper
    lines = helper.splitlines()
    marks = [index for index, line in enumerate(lines) if line == MARK]
    assert marks
    for index in marks:
        assert lines[index - 1] == ""
        cursor = index + 1
        assert lines[cursor].startswith("- ")
        while cursor < len(lines) and lines[cursor].startswith("- "):
            cursor += 1
        assert lines[cursor] == ""
