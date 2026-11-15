"""Leftover test wording: the neighbours still hold and the rematch stayed in tests.

Two leftover tests still described older wording after earlier stacked changes
landed. The spine test refused the brief-answer import that had already landed,
and the stage 4a isolation test asked for the old card words on a refused next
line. Both now assert the wording this tip speaks.

The neighbouring voice, traps, cover, promise, and stored-answer ids keep one
seat each in their own files. Product code, prompts, templates, the refusal
lines, the stage 7 card node, the brief, and the operator tone are untouched.

Ids are seated once. The id is the docstring and the pytest id.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import test_essay_voice
from test_essay_voice import (
    BIBLIOGRAPHY_NEXT,
    FIRST_RUN_OPENING,
    FRIEND,
    SOURCE_NEXT,
    VOICE_IDS,
    _assert_friend_sources,
    _assert_parent_cases,
    _assert_refusals,
    _assert_stage6_sentence,
    _module,
    _plant,
    _read,
    _seat_once,
    _seat_parents,
)

from essay_writer.paths import essay_dir
from essay_writer.stage_track import essay_stage

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "essay_writer"
TESTS = REPO / "tests"
VOICE_FILE = Path(test_essay_voice.__file__).resolve()
AC4_NODE = "test_ac4_stage7_skip_refuses_and_all_fine_opens_confirm"


def _function_source(path: Path, name: str) -> str:
    source = _read(path)
    lines = source.splitlines()
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"{name} is missing from {path.name}")


@pytest.mark.parametrize("case_id", [pytest.param("essay-left-c1", id="essay-left-c1")])
def test_the_neighbouring_cases_still_hold(case_id, workspace):
    """essay-left-c1: The voice, traps, cover, promise, and stored-answer cases still hold and keep one seat each."""
    assert case_id == "essay-left-c1"
    assert SOURCE_NEXT == "Add a gathered source, then press Confirm."
    assert BIBLIOGRAPHY_NEXT == "Add a bibliography, then press Confirm."
    _seat_parents()
    for name in VOICE_IDS:
        _seat_once(VOICE_FILE, name)
    _assert_friend_sources()
    _assert_stage6_sentence()
    _assert_parent_cases("31")


@pytest.mark.parametrize("case_id", [pytest.param("essay-left-d1", id="essay-left-d1")])
def test_a_partial_leftover_update_leaves_the_product_alone(case_id, workspace):
    """essay-left-d1: A partial leftover update keeps product code, prompts, refusal lines, the stage 7 node, and the brief as they are."""
    assert case_id == "essay-left-d1"

    track = _read(SRC / "stage_track.py")
    assert track.count("from essay_writer.assignment_gate import store_brief_answer") == 1
    assert "store_brief_answer(essay_id, args.formatAnswer, args.questionAnswer)" in track
    assert "def assignment_gate" not in _read(SRC / "spine.py")

    replies = _read(SRC / "stage_replies.py")
    assert f'_MISSING_SOURCE_NEXT = "{SOURCE_NEXT}"' in replies
    assert f'_MISSING_BIBLIOGRAPHY_NEXT = "{BIBLIOGRAPHY_NEXT}"' in replies

    node = _function_source(TESTS / "test_confirm_card_save.py", AC4_NODE)
    for locked in (
        'assert skipped["ok"] is False, skipped',
        'assert skipped["refused"] == "stage"',
        'assert skipped["stored"] is not True',
        'assert "Skipping the questions does not save" in skipped["reason"]',
        'assert "Please answer these questions" in skipped["next"]',
        'assert "Status: draft" in _stage_note(seq, "7")',
        'assert "7" not in load_pointer(seq)["saved"]',
        'assert opened["stored"] is False',
        'assert opened["next"].startswith("Open the Confirm card to save Stage 7")',
        'assert saved["stored"] is True',
        'assert saved["current"] == "8"',
    ):
        assert locked in node, locked

    # A refused 4a and 4b still keep the card and the locked next line.
    _assert_refusals("41")

    module = _module("41", 20)
    seq = _plant(module, f"Module code: {module}\nStudents meet on Tuesdays.\n")
    folder = essay_dir(module)
    brief = folder / "brief.md"
    before = brief.read_bytes()
    drafted = essay_stage(seq, "1", "draft", "A sentence of my own for this stage.")
    assert drafted["ok"] is True, drafted
    assert brief.read_bytes() == before
    assert not (folder / "brief-meta.json").exists()

    briefing = _read(SRC / "prompts" / "front_office" / "briefing.md")
    assert "Do not invent a Documents path." in briefing
    first_run = _read(REPO / "FIRST-RUN.txt")
    assert first_run.startswith(FIRST_RUN_OPENING)
    assert FRIEND not in first_run
