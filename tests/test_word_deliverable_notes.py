"""Word deliverable notes."""

from essay_writer.build_office import stage_launch
from essay_writer.server import INSTRUCTIONS
from essay_writer.stage_llm import stage_settings
from essay_writer.writing_basics import CHECKLIST_WALK

REPO = __import__("pathlib").Path(__file__).resolve().parents[1]


def _rules(stage: str) -> str:
    command = stage_launch(stage)["command"]
    return command[command.index("--rules") + 1]


def test_word_budget_and_mark_scheme_win_on_overlays():
    stage_1 = stage_settings("1")["prompt_overlay"]
    assert "Do not invent a word budget" in stage_1
    assert "mark-scheme" in stage_1.casefold()
    stage_3 = stage_settings("3")["prompt_overlay"]
    assert "Do not invent a section list or word budget" in stage_3
    stage_8 = stage_settings("8")["prompt_overlay"]
    assert "Listed mark-scheme sections" in stage_8
    assert "Do not invent a word budget" in stage_8
    assert "Inditex" not in stage_8
    assert "MOD1004AA" not in _rules("8")


def test_jargon_gloss_and_method_from_opened_file():
    assert "GHG Scope 1, 2, and 3" in CHECKLIST_WALK
    assert "not a closed list" in CHECKLIST_WALK
    assert "opened gathered file" in CHECKLIST_WALK
    overlay_5 = stage_settings("5")["prompt_overlay"]
    assert "gloss jargon" in overlay_5.casefold()
    assert "Plain-English gloss only" in overlay_5
    assert "Inditex" not in overlay_5
    rules_6 = stage_settings("6")["rules"]
    assert "Plain-English gloss only" in rules_6


def test_stage_five_ai_only_and_stage_six_first_edit():
    overlay_5 = stage_settings("5")["prompt_overlay"]
    assert "AI-authored" in overlay_5
    assert "does not read or edit Word" in overlay_5
    overlay_6 = stage_settings("6")["prompt_overlay"]
    assert overlay_6.index("first read") < overlay_6.index("structure is clear")
    assert "master copy" in overlay_6.casefold()
    assert "Do not guess path" in overlay_6
    assert CHECKLIST_WALK in INSTRUCTIONS or "Student chat never shows" in INSTRUCTIONS


def test_no_false_sentence_tightening():
    for stage in ("6", "8"):
        overlay = stage_settings(stage)["prompt_overlay"]
        assert "Do not tighten prose below what the opened Word file already says" in overlay
        assert "false one" in overlay
