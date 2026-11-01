"""Writing-basics checklists in docs and prompt paths."""

import re
from pathlib import Path

from essay_writer.doors import DOORS
from essay_writer.server import INSTRUCTIONS
from essay_writer.writing_basics import (
    BASICS_MARKER,
    CHECKLISTS,
    STAGE_ORDER,
    basics_lines,
)

REPO = Path(__file__).resolve().parents[1]
HELPERS = REPO / "docs" / "academic-writing-helpers.md"


def test_stage_keys_complete():
    assert set(STAGE_ORDER) == set(CHECKLISTS)
    for stage in STAGE_ORDER:
        assert basics_lines(stage), f"stage {stage} needs curated bullets"


def test_helpers_checklists_match_prompt_wiring():
    text = HELPERS.read_text(encoding="utf-8")
    markers = list(re.finditer(r"\*\*Basics checklist(?: \(([^)]+)\))?:\*\*", text))
    parsed: dict[str, list[str]] = {}
    for index, match in enumerate(markers):
        stage = match.group(1)
        if not stage:
            before = text[: match.start()]
            headings = [line for line in before.splitlines() if line.startswith("### ")]
            stage = headings[-1].split(".", 1)[0].removeprefix("### ")
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        bullets = []
        for line in text[match.end() : end].splitlines():
            if line.startswith("### ") or line.startswith("## "):
                break
            if line.startswith("- "):
                bullets.append(line[2:].strip())
        parsed[stage] = bullets
    assert list(parsed) == list(STAGE_ORDER)
    for stage in STAGE_ORDER:
        assert parsed[stage] == list(CHECKLISTS[stage]), stage


def test_helpers_has_basics_checklist_per_stage():
    text = HELPERS.read_text(encoding="utf-8")
    markers = text.count("**Basics checklist:**") + text.count("**Basics checklist (")
    assert markers >= 11  # stages 1–3, 5–10 plus 4a and 4b
    assert "**Basics checklist (4a):**" in text
    assert "**Basics checklist (4b):**" in text
    assert "genre-from-brief" in text.casefold()
    assert "harvard referencing" in text.casefold()
    assert "not apa" in text.casefold()


def test_server_and_doors_carry_basics():
    assert BASICS_MARKER in INSTRUCTIONS
    assert "stage 9" in INSTRUCTIONS.casefold()
    wired = [d for d in DOORS if BASICS_MARKER in d["description"]]
    assert {d["tool"] for d in wired} >= {
        "essay.originals",
        "essay.research.summary",
        "essay.research.full",
        "essay.pack.validate",
        "essay.pack.render_word",
        "essay.revise",
    }
