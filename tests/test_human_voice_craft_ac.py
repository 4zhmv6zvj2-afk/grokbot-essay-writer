"""Human-voice craft on the shared stage row. Stable ids: AC1–AC5.

Build covered: Cursor cursor_stage_launch and Grok Build stage_launch both
read essay_writer.stage_llm.stage_settings. The eight craft rules, the
thickened anti-glue and voice limits, the stage 8 tone line, and the
reviewer's stock-line note are that shared row. Prompt text only. No similarity or
AI score, and no new pass/fail in gates.py or validate.py.
"""

import inspect
from pathlib import Path

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.specialists.eqr import (
    CLAIM_CHECKS,
    NORTH_STAR,
    REVIEW_LIMIT,
    REVIEW_PROMPT,
    findings_note_clears,
)
from essay_writer.stage7 import questions_for
from essay_writer.stage_llm import stage_settings
from essay_writer.writing_basics import (
    ANTI_GLUE,
    CRAFT_ANCHOR,
    CRAFT_COMMITMENT,
    CRAFT_REFUSAL,
    CRAFT_REVISE,
    CRAFT_SOURCES,
    VOICE_LIMIT,
)

REPO = Path(__file__).resolve().parents[1]
HELPERS = REPO / "docs" / "academic-writing-helpers.md"
STAGES = ("5", "6", "7", "8")
GENRES = (None, "diary", "essay", "report")

# Rules 1–8, in Iris's order. Rules 3–5 are the shared glue and voice lines.
EIGHT = (
    "Keep the commitment the writer means.",
    "Tie each claim to one thing the writer can point at",
    "Use words the writer can define out loud.",
    "A paragraph closer must not only restate the topic sentence.",
    "Use a connective only when the relation is true.",
    "rewrite the ideas in the writer's sentences",
    "A paraphrase keeps that source's specific claim.",
    "Do not chase a third-party similarity or AI-score number",
)
STAGE7_QUESTION = "Which lines are too vague to defend from the sources?"
OLD_STAGE7_QUESTION = "Where should the academic tone be clearer?"
OLD_CLOSER = "closing sentence that restates the point"
STOCK_NOTE = (
    "The findings note may name a leftover stock line, or a line that could sit on any assignment. "
    "Naming that line is not a score. Do not rewrite those lines. Naming them does not fail the review."
)
PLANTED = (
    "plant a grammar error",
    "add a typo",
    "deliberate mistake",
    "insert an error",
    "grammarly",
    "turnitin",
    "increase burstiness",
    "raise perplexity",
    "human %",
    "detector %",
)


def _rules(command: list[str]) -> str:
    return command[command.index("--rules") + 1]


def _stage5_helpers() -> str:
    text = HELPERS.read_text(encoding="utf-8")
    start = text.index("### 5. Write your first draft")
    end = text.index("### 6. Re-read and make changes")
    return text[start:end]


def _clear_findings(extra: str = "") -> str:
    lines = [
        NORTH_STAR,
        "What the mark scheme scores is the argument.",
        "Format: the sections the brief names.",
        "The assignment asks for a judgement on the question.",
        CLAIM_CHECKS,
        "One gathered sentence was checked against the opened file.",
    ]
    if extra:
        lines.append(extra)
    return "\n".join(lines)


def test_ac1_stage5_carries_the_eight_craft_rules():
    """AC1. Stage 5 and the academic helpers carry the eight rules. No planted-error instruction."""
    rules = stage_settings("5")["rules"]
    overlay = stage_settings("5")["prompt_overlay"]
    helpers = _stage5_helpers()
    for phrase in EIGHT:
        assert phrase in rules
        assert phrase in overlay
        assert phrase in helpers
    assert "Do not open with a general sentence built only from the topic nouns." in rules
    assert "Do not close with an automatic In conclusion that only restates the topic." in rules
    assert OLD_CLOSER not in rules
    assert OLD_CLOSER not in helpers
    assert OLD_CLOSER not in (REPO / "docs" / "essay-writing-helpers.md").read_text(encoding="utf-8")
    folded = rules.casefold()
    for banned in PLANTED:
        assert banned not in folded
    assert CRAFT_COMMITMENT in rules
    assert CRAFT_ANCHOR in rules
    assert CRAFT_REVISE in rules
    assert CRAFT_SOURCES in rules
    assert CRAFT_REFUSAL in rules
    assert "%" not in ANTI_GLUE
    assert "grammarly" not in ANTI_GLUE.casefold()


def test_ac2_stages_5_to_8_thicken_glue_and_voice_without_a_gate():
    """AC2. Rules 3–5 sit on the shared limits for stages 5–8, including a diary. Not a hard fail."""
    for stage in STAGES:
        for genre in GENRES:
            text = stage_settings(stage, genre)["rules"]
            assert ANTI_GLUE in text
            assert VOICE_LIMIT in text
            assert "Use words the writer can define out loud." in text
            assert "do not swap in a rarer synonym the writer does not use." in text
            assert "Do not nominalize a verb into -ion, -ment, or -ance to sound scientific" in text
            assert "Use a connective only when the relation is true." in text
            assert "Do not open with a general sentence built only from the topic nouns." in text
            assert "A paragraph closer must not only restate the topic sentence." in text
    gates = (REPO / "src" / "essay_writer" / "gates.py").read_text(encoding="utf-8")
    validate = (REPO / "src" / "essay_writer" / "validate.py").read_text(encoding="utf-8")
    for source in (gates, validate):
        folded = source.casefold()
        assert "ANTI_GLUE" not in source
        assert "VOICE_LIMIT" not in source
        assert "Ban AI-glue" not in source
        assert "Do not edit toward a detector" not in source
        assert "sounds ai" not in folded
        assert "sounds-ai" not in folded
        for banned in PLANTED:
            assert banned not in folded


def test_ac3_stage8_tone_and_stage7_vague_lines_question():
    """AC3. Stage 8 keeps the writer's commitment and rewrites a chatbot paragraph. Stage 7 asks about vague lines."""
    tone = stage_settings("8")["rules"]
    assert "keeps the commitment the writer means" in tone
    assert "If a chatbot produced a paragraph, rewrite it in the writer's sentences." in tone
    assert "Tone is formal, objective, and evidence-based" in tone
    assert CRAFT_REVISE in tone
    questions = questions_for("MOD1004AA-1")
    assert questions[-1] == STAGE7_QUESTION
    assert OLD_STAGE7_QUESTION not in questions
    assert len(questions) == 5
    assert STAGE7_QUESTION in (REPO / "src" / "essay_writer" / "stage7.py").read_text(encoding="utf-8")


def test_ac4_review_may_name_stock_lines_without_a_new_fail():
    """AC4. The findings note may name a stock line. That is not a score, a rewrite, or a fail section."""
    assert STOCK_NOTE in REVIEW_PROMPT
    assert "not a score" in REVIEW_PROMPT
    assert "Do not rewrite those lines." in REVIEW_PROMPT
    assert "does not fail the review" in REVIEW_PROMPT
    assert REVIEW_LIMIT in REVIEW_PROMPT
    assert "Do not polish voice, elegance, or parallelism." in REVIEW_PROMPT
    assert "Keep the student's voice and the writer's voice." in REVIEW_PROMPT
    source = inspect.getsource(findings_note_clears)
    for token in ("stock", "detector", "rewrite", "ANTI_GLUE", "sounds"):
        assert token.casefold() not in source.casefold()
    plain = _clear_findings()
    named = _clear_findings("A leftover stock line could sit on any assignment.")
    assert findings_note_clears(plain) is True
    assert findings_note_clears(named) is True
    assert findings_note_clears("PASS") is False
    assert findings_note_clears("The independent review recorded a pass.") is False


def test_ac5_build_covered_cursor_and_grok_read_the_same_row():
    """AC5. Build covered. Both shells read the same stage_settings row."""
    for stage in STAGES:
        shared = stage_settings(stage)
        build = stage_launch(stage)
        cursor = cursor_stage_launch(stage)
        assert build["settings"]["rules"] == shared["rules"]
        assert cursor["settings"]["rules"] == shared["rules"]
        assert build["settings"]["prompt_overlay"] == shared["prompt_overlay"]
        assert cursor["settings"]["prompt_overlay"] == shared["prompt_overlay"]
        assert ANTI_GLUE in _rules(build["command"])
        assert VOICE_LIMIT in _rules(build["command"])
        assert ANTI_GLUE in cursor["settings"]["rules"]
        assert VOICE_LIMIT in cursor["settings"]["rules"]
        assert build["source"] == cursor["source"] == "essay_writer.stage_llm.stage_settings"
        assert "Use a connective only when the relation is true." in cursor["settings"]["rules"]
        assert "Use words the writer can define out loud." in _rules(build["command"])
    for stage in ("5", "8"):
        shared = stage_settings(stage)["rules"]
        assert CRAFT_REFUSAL in shared
        assert CRAFT_REFUSAL in _rules(stage_launch(stage)["command"])
        assert CRAFT_REFUSAL in cursor_stage_launch(stage)["settings"]["rules"]
    review = stage_settings("eqr")["rules"]
    build = stage_launch("eqr")
    cursor = cursor_stage_launch("eqr")
    assert STOCK_NOTE in review
    assert build["settings"]["rules"] == review
    assert cursor["settings"]["rules"] == review
    assert STOCK_NOTE in _rules(build["command"])
    assert STOCK_NOTE in cursor["settings"]["rules"]
    assert "Do not polish voice, elegance, or parallelism." in review
