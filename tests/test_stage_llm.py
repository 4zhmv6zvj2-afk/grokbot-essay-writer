"""Per-stage LLM settings. Fast off. Every stage uses a 256k context."""

from pathlib import Path

from essay_writer.doors import DOORS
from essay_writer.review import REVIEW_INSTRUCTIONS, REVIEW_PROMPT
from essay_writer.server import INSTRUCTIONS, house_instructions
from essay_writer.stage_llm import (
    HOUSE_MODEL,
    STAGE_KEYS,
    all_stage_settings,
    stage_settings,
)
from essay_writer.writing_basics import CHECKLIST_WALK, CHECKLISTS, STAGE_ORDER

REPO = Path(__file__).resolve().parents[1]


def test_every_stage_has_one_model_and_fast_off():
    settings = all_stage_settings()
    assert tuple(settings) == STAGE_KEYS
    assert set(STAGE_ORDER) <= set(settings)
    assert "eqr" in settings
    for item in settings.values():
        assert item["model"] == HOUSE_MODEL == "grok-4.7"
        assert item["fast"] is False


def test_every_stage_uses_256k_context():
    for stage, item in all_stage_settings().items():
        assert item["context_window"] == 256_000, stage
        assert item["context_window"] != 500_000


def test_reasoning_follows_the_locks():
    reasoning = {stage: stage_settings(stage)["reasoning"] for stage in STAGE_KEYS}
    assert reasoning == {
        "1": "high",
        "2": "high",
        "3": "high",
        "4a": "high",
        "4b": "xhigh",
        "5": "xhigh",
        "6": "high",
        "7": "high",
        "8": "high",
        "9": "high",
        "10": "medium",
        "eqr": "xhigh",
    }


def test_prompt_overlay_is_the_existing_stage_prompt():
    for stage, lines in CHECKLISTS.items():
        overlay = stage_settings(stage)["prompt_overlay"]
        bullets = "\n".join(f"- {line}" for line in lines)
        assert overlay.startswith(CHECKLIST_WALK)
        assert bullets in overlay
        assert "Do not paste the rest of the Basics checklist into the chat." in overlay
    assert "purpose and scope" in stage_settings("2")["prompt_overlay"]
    assert "central theme" in stage_settings("3")["prompt_overlay"]
    assert stage_settings("eqr")["prompt_overlay"] == REVIEW_PROMPT
    assert CHECKLIST_WALK not in stage_settings("eqr")["prompt_overlay"]


def test_writer_and_reviewer_briefings_carry_the_settings():
    assert "256000" in INSTRUCTIONS
    assert "500000" not in INSTRUCTIONS
    assert "Fast is off" in INSTRUCTIONS
    assert "one markdown per paper" in INSTRUCTIONS.casefold()
    assert "xhigh" in INSTRUCTIONS
    reviewer = house_instructions(REVIEW_INSTRUCTIONS)
    assert "reasoning xhigh" in reviewer
    assert "context 256000" in reviewer
    assert "fast off" in reviewer.casefold()
    assert "500000" not in reviewer


def test_doors_with_stage_prompts_name_model_effort_and_context():
    by_tool = {door["tool"]: door["description"] for door in DOORS}
    full = by_tool["essay.research.full"]
    summary = by_tool["essay.research.summary"]
    validate = by_tool["essay.pack.validate"]
    word = by_tool["essay.pack.render_word"]
    assert "Stage LLM (no-fast)" in full
    assert "Basics 4b:" in full
    assert "context 256000" in full
    assert "context 500000" not in full
    assert "reasoning xhigh" in full
    assert "context 500000" not in summary
    assert "context 256000" in summary
    assert "Basics 5:" in validate
    assert "reasoning xhigh" in validate
    assert "context 256000" in validate
    assert "one markdown per paper" in validate.casefold()
    assert "one markdown per paper" in word.casefold()
    assert "Stage LLM" not in by_tool["essay.health"]
    assert "Stage LLM" not in by_tool["essay.setup"]


def test_docs_record_the_same_locks():
    workflow = (REPO / "docs" / "workflow.md").read_text(encoding="utf-8")
    assert "grok-4.7" in workflow
    assert "256000" in workflow
    assert "500000" not in workflow
    assert "critical-reviews.zip" in workflow.casefold()
    assert "word file per paper" in workflow.casefold() or "one word file per paper" in workflow.casefold()
    assert "fast is off" in workflow.casefold()
