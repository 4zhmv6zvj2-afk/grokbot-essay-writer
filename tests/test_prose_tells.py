"""Four prose-habit craft rules. Stable ids: AC1–AC5.

Dashes, staged run-ups, decorated formatting, and model knowledge guesses
live once in craft/voice.md. Mechanical rules ride stages 5–8; model_gap
rides stages 5 and 8 next to open_gap. Prompt text only. No new gate, no
detector chase, and edit_recheck still guards names, numbers, and cites.
"""

from pathlib import Path

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.prompt_loader import sections as prompt_sections
from essay_writer.stage_llm import stage_settings
from essay_writer.student_voice import student_surface_hits

_CRAFT = prompt_sections("craft/voice.md")
DASH = _CRAFT["dash_connectors"]
RUNUP = _CRAFT["staged_runup"]
FORMAT = _CRAFT["decorated_format"]
MODEL_GAP = _CRAFT["model_gap"]
RECHECK = _CRAFT["edit_recheck"]

REPO = Path(__file__).resolve().parents[1]
HELPERS = REPO / "docs" / "academic-writing-helpers.md"
GENRES = (None, "diary", "essay", "report")
SHARED = ("5", "6", "7", "8")
CLAIM = ("5", "8")
OTHER = ("1", "2", "3", "4a", "4b", "9", "10")
THIN_ONLY = ("6", "7")
BANNED = (
    "humanizer",
    "gptzero",
    "turnitin",
    "grammarly",
    "detector %",
    "ai-score",
)


def _rules(command: list[str]) -> str:
    return command[command.index("--rules") + 1]


def test_ac1_mechanical_tells_on_stages_5_to_8():
    """AC1. Dashes, staged run-ups, and decorated formatting ride every writing stage."""
    for section in (DASH, RUNUP, FORMAT):
        for stage in SHARED:
            for genre in GENRES:
                item = stage_settings(stage, genre)
                assert section in item["rules"]
                assert section in item["prompt_overlay"]
                assert student_surface_hits(item["prompt_overlay"]) == []
                assert student_surface_hits(item["rules"]) == []
        for stage in OTHER:
            assert section not in stage_settings(stage)["rules"]


def test_ac2_model_gap_on_stages_5_and_8_only():
    """AC2. Model knowledge guesses sit with the full craft row, not the thin edit row."""
    for stage in CLAIM:
        for genre in GENRES:
            item = stage_settings(stage, genre)
            assert MODEL_GAP in item["rules"]
            assert MODEL_GAP in item["prompt_overlay"]
    for stage in (*THIN_ONLY, *OTHER):
        assert MODEL_GAP not in stage_settings(stage)["rules"]


def test_ac3_one_source_and_both_launchers():
    """AC3. One copy in craft/voice.md; Cursor and Grok Build read the same rules."""
    craft = (REPO / "src" / "essay_writer" / "prompts" / "craft" / "voice.md").read_text(
        encoding="utf-8"
    )
    helpers = HELPERS.read_text(encoding="utf-8")
    for section in (DASH, RUNUP, FORMAT, MODEL_GAP):
        assert craft.count(section) == 1
        assert section in helpers
    for stage in SHARED:
        shared = stage_settings(stage)
        build = stage_launch(stage)
        cursor = cursor_stage_launch(stage)
        assert build["settings"]["rules"] == shared["rules"]
        assert cursor["settings"]["rules"] == shared["rules"]
        assert DASH in _rules(build["command"])
        assert RUNUP in cursor["settings"]["rules"]
        assert FORMAT in shared["rules"]
    for stage in CLAIM:
        assert MODEL_GAP in stage_settings(stage)["rules"]
    assert helpers.count(DASH) == len(SHARED)
    assert helpers.count(MODEL_GAP) == len(CLAIM)


def test_ac4_bullets_name_the_tells_and_stay_prompt_only():
    """AC4. Named tells stay prose quality. No detector tool, no gate hook."""
    for phrase in (
        "Do not use an em dash or a double hyphen as a connector",
        "Prefer a comma, a colon, a parenthesis, or a full stop",
    ):
        assert phrase in DASH
    for phrase in (
        "Let's dive in",
        "Here's what you need to know",
        "Great question",
        "I hope this helps",
        "Keep the content that follows",
    ):
        assert phrase in RUNUP
    for phrase in (
        "bold labels",
        "emoji headings",
        "bold label and a colon",
        "The Word file is not a chat reply",
    ):
        assert phrase in FORMAT
    for phrase in (
        "say that the source does not cover it, or cut the sentence",
        "While specific details are limited",
        "it likely",
        "They are not a detector score",
    ):
        assert phrase in MODEL_GAP
    for section in (DASH, RUNUP, FORMAT, MODEL_GAP):
        assert student_surface_hits(section) == []
        folded = section.casefold()
        for banned in BANNED:
            assert banned not in folded
    gates = (REPO / "src" / "essay_writer" / "gates.py").read_text(encoding="utf-8")
    validate = (REPO / "src" / "essay_writer" / "validate.py").read_text(encoding="utf-8")
    for name in ("dash_connectors", "staged_runup", "decorated_format", "model_gap"):
        assert name not in gates
        assert name not in validate


def test_ac5_edit_recheck_guards_names_numbers_and_cites():
    """AC5. A wording pass must not change a name, number, date, quote, or citation."""
    assert "A true sentence must not become a false one." in RECHECK
    assert "A name, number, date, quote, or citation must not change." in RECHECK
    assert RECHECK in stage_settings("8")["rules"]
    assert RECHECK not in stage_settings("5")["rules"]
    fixture = (
        "Here's what you need to know — while specific details are limited, "
        "Smith (2019) likely grew up in **Key Finding:** a pivotal landscape."
    )
    for tell in (
        "Here's what you need to know",
        "while specific details are limited",
        "likely",
        "Key Finding:",
    ):
        assert tell.casefold() in fixture.casefold()
    assert "Smith (2019)" in fixture
