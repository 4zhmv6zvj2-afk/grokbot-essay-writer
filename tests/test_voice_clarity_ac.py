"""Voice and clarity on the shared stage row. Stable ids: AC1–AC7.

Build covered: Cursor cursor_stage_launch and Grok Build stage_launch both
read essay_writer.stage_llm.stage_settings. The plain-words bullet is that
shared row, so every stage 5–8 genre carries it. Prompt text only. No new
pass/fail in gates.py or validate.py.
"""

from pathlib import Path

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.specialists.writer import _rewrite_supported
from essay_writer.stage_llm import stage_settings
from essay_writer.student_voice import for_word, say, strip_word_labels, student_surface_hits
from essay_writer.writing_basics import (
    NO_ASSISTANT_VOICE,
    PLAIN_WORDS,
    TEMPLATE_OPENERS,
    basics_lines,
)

REPO = Path(__file__).resolve().parents[1]
HELPERS = REPO / "docs" / "academic-writing-helpers.md"
STAGES = ("5", "6", "7", "8")
GENRES = (None, "diary", "essay", "report")
OTHER_HELPERS = (
    "docs/essay-writing-helpers.md",
    "docs/report-writing-helpers.md",
    "docs/reflective-diary-helpers.md",
)


def _rules(command: list[str]) -> str:
    return command[command.index("--rules") + 1]


def test_ac1_plain_words_bullet_on_stages_5_to_8_and_the_diary():
    """AC1. Every stage 5–8 genre carries the filler, intensifier, and hedge bullet."""
    for stage in STAGES:
        for genre in GENRES:
            item = stage_settings(stage, genre)
            assert PLAIN_WORDS in item["rules"]
            assert PLAIN_WORDS in item["prompt_overlay"]
            assert student_surface_hits(item["prompt_overlay"]) == []
            assert student_surface_hits(item["rules"]) == []
    assert PLAIN_WORDS in stage_settings("5", "diary")["rules"]
    assert PLAIN_WORDS in stage_settings("8", "diary")["rules"]
    # Stages that are not draft or edit paths keep their own row.
    for stage in ("1", "2", "3", "4a", "4b", "9", "10"):
        assert PLAIN_WORDS not in stage_settings(stage)["rules"]


def test_ac2_helpers_and_launchers_carry_the_same_bullet():
    """AC2. The helper note, Cursor, and Grok Build read one bullet, not a second copy."""
    helpers = HELPERS.read_text(encoding="utf-8")
    assert helpers.count(PLAIN_WORDS) == 4
    for stage in STAGES:
        for line in basics_lines(stage):
            assert line in helpers
    for stage in STAGES:
        shared = stage_settings(stage)
        build = stage_launch(stage)
        cursor = cursor_stage_launch(stage)
        assert build["settings"]["rules"] == shared["rules"]
        assert cursor["settings"]["rules"] == shared["rules"]
        assert PLAIN_WORDS in _rules(build["command"])
        assert PLAIN_WORDS in cursor["settings"]["rules"]


def test_ac3_bullet_names_the_three_classes_and_stays_prompt_only():
    """AC3. Filler, empty intensifiers, and stacked hedges are named. No similarity score, no gate."""
    for phrase in (
        "Cut words that do no work in the sentence.",
        "Empty intensifiers such as very, really, quite, and extremely",
        "significantly adds nothing when no figure follows it",
        "Filler phrases such as in order to, due to the fact that, and it is worth noting that",
        "Keep at most one hedge in a sentence.",
        "it could perhaps be argued that",
        "it may possibly be the case that",
        "A single hedge stays only when the writer means it.",
    ):
        assert phrase in PLAIN_WORDS
    gates = (REPO / "src" / "essay_writer" / "gates.py").read_text(encoding="utf-8")
    validate = (REPO / "src" / "essay_writer" / "validate.py").read_text(encoding="utf-8")
    assert "PLAIN_WORDS" not in gates
    assert "PLAIN_WORDS" not in validate
    assert student_surface_hits(PLAIN_WORDS) == []
    assert "%" not in PLAIN_WORDS
    for name in OTHER_HELPERS:
        text = (REPO / name).read_text(encoding="utf-8")
        assert PLAIN_WORDS not in text


def test_ac4_no_assistant_voice_bullet_on_stages_5_to_8_and_the_diary():
    """AC4. Every stage 5–8 genre tells the writer to speak as the student, not a tool."""
    helpers = HELPERS.read_text(encoding="utf-8")
    assert helpers.count(NO_ASSISTANT_VOICE) == 4
    for stage in STAGES:
        for genre in GENRES:
            item = stage_settings(stage, genre)
            assert NO_ASSISTANT_VOICE in item["rules"]
            assert NO_ASSISTANT_VOICE in item["prompt_overlay"]
            assert student_surface_hits(item["prompt_overlay"]) == []
            assert student_surface_hits(item["rules"]) == []
    for phrase in (
        "Do not write as an assistant or as a model.",
        "No note that the writer is an AI",
        "The essay speaks as the student, not as a tool.",
    ):
        assert phrase in NO_ASSISTANT_VOICE
    assert student_surface_hits(NO_ASSISTANT_VOICE) == []


def test_ac5_model_self_reference_is_dropped_from_chat_and_word():
    """AC5. A model self-reference is caught in student text and cut from chat and Word."""
    leaky = "As an AI language model, I can only suggest a plan."
    assert student_surface_hits(leaky) == ["assistant voice"]
    assert say(leaky) == "I can only suggest a plan."
    assert for_word(leaky) == "I can only suggest a plan."
    assert strip_word_labels(leaky) == "I can only suggest a plan."
    assert say("I am an AI. I can only help with the draft.") == (
        "I can only help with the draft."
    )
    assert strip_word_labels("I'm an AI. This section needs one more source.") == (
        "This section needs one more source."
    )
    # The rule itself stays plain wording, and ordinary uses are untouched.
    assert student_surface_hits("As an assistant, I can help.") == []
    assert say("This is a model answer.") == "This is a model answer."
    refused = "That note uses a label that stays off the stage file. Use plain words."
    assert student_surface_hits(refused) == []


def test_ac6_word_band_stretch_adds_no_padding_and_no_stock_opening():
    """AC6. A short draft stretches from gathered sentences without empty padding."""
    used = (
        "This article presents the author's development of a year-long module on "
        "Africa in Greco-Roman literature and its receptions."
    )
    unused = (
        "It argues that the equivalence of curriculum diversification with "
        "decolonization can be pernicious in its tokenizing effects, and that a "
        "committed practice of decolonizing pedagogy cannot be limited to studying "
        "Africa in Greco-Roman texts."
    )
    for sentence in (used, unused):
        for variant in range(12):
            line = _rewrite_supported(sentence, variant)
            assert "and also that" not in line
            assert "gathered record" not in line.casefold()
            assert sentence not in line
    plain = _rewrite_supported("Demand rose sharply in 2019.", 0)
    assert plain == "The text notes that demand rose sharply in 2019."
    assert "also that" not in plain


def test_ac7_template_openers_are_named_and_repeating_a_key_term_stays_allowed():
    """AC7. One paragraph opener, not a repeated one. Repeating a key term is not the rule."""
    helpers = HELPERS.read_text(encoding="utf-8")
    assert helpers.count(TEMPLATE_OPENERS) == 4
    for stage in STAGES:
        for genre in GENRES:
            item = stage_settings(stage, genre)
            assert TEMPLATE_OPENERS in item["rules"]
            assert TEMPLATE_OPENERS in item["prompt_overlay"]
            assert student_surface_hits(item["prompt_overlay"]) == []
    for phrase in (
        "Do not start more than one paragraph with the same words.",
        "In today's world",
        "Throughout history",
        "This essay will discuss",
        "Repeating a key term is not the same thing.",
    ):
        assert phrase in TEMPLATE_OPENERS
    assert student_surface_hits(TEMPLATE_OPENERS) == []
    accepted = "Tie sentences by repeating the key words"
    assert accepted in helpers
