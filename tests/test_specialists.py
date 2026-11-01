"""Layer 1. Four specialists, one function each, spine calls them."""

from pathlib import Path

from essay_writer import build_office, late_chain, stage_track, word
from essay_writer.dig import essay_dig
from essay_writer.first_run import package_root
from essay_writer.known_paths import allow_research_path
from essay_writer.research import essay_research_full, essay_research_summary
from essay_writer.research_packs import ship_4a
from essay_writer.review import REVIEW_PROMPT as review_prompt
from essay_writer.review import essay_review
from essay_writer.server import HANDLERS, REVIEW_HANDLERS
from essay_writer.shells import (
    bot_share_document,
    cursor_shell,
    front_office,
    front_office_call,
)
from essay_writer.specialists import ROLES
from essay_writer.specialists.eqr import REVIEW_PROMPT, eqr_verdict
from essay_writer.specialists.grok_bot import (
    CHECKLIST_WALK,
    DOOR_WALK,
    LANGUAGE,
    MCP_DOWN_SPEECH,
)
from essay_writer.specialists.grok_bot import front_office_call as grok_speak
from essay_writer.specialists.researcher import essay_dig as researcher_dig
from essay_writer.specialists.researcher import ship_4a as researcher_ship
from essay_writer.specialists.writer import FIRST_DRAFT_NOTE, essay_pack_render_word
from essay_writer.spine import essay_stage
from essay_writer.stage_llm import first_draft_note
from essay_writer.stage_track import essay_stage as stage_track_stage
from essay_writer.word import essay_pack_render_word as word_render
from essay_writer.writing_basics import CHECKLIST_WALK as overlay_walk
from essay_writer.writing_basics import DOOR_WALK as overlay_door
from essay_writer.writing_basics import MCP_DOWN_SPEECH as overlay_down


def test_four_roles_and_the_spine():
    assert ROLES == ("grok_bot", "writer", "researcher", "eqr")
    assert essay_stage is stage_track_stage is HANDLERS["essay.stage"]


def test_handlers_are_the_specialist_entries_and_the_original_functions():
    assert researcher_dig is essay_dig is HANDLERS["essay.dig"]
    assert cursor_shell()["handlers"]["essay.dig"] is essay_dig
    assert front_office()["handlers"]["essay.dig"] is essay_dig
    assert HANDLERS["essay.research.summary"] is essay_research_summary
    assert HANDLERS["essay.research.full"] is essay_research_full
    assert essay_pack_render_word is word_render is HANDLERS["essay.pack.render_word"]
    assert REVIEW_HANDLERS["essay.review"] is essay_review
    assert researcher_ship is ship_4a
    from essay_writer.specialists.researcher import allow_research_path as via

    assert via is allow_research_path
    from essay_writer.review import eqr_verdict as review_verdict

    assert eqr_verdict is review_verdict


def test_personality_has_one_source():
    assert overlay_walk is CHECKLIST_WALK
    assert overlay_door is DOOR_WALK
    assert overlay_down is MCP_DOWN_SPEECH
    assert first_draft_note() == FIRST_DRAFT_NOTE
    assert review_prompt is REVIEW_PROMPT
    share = bot_share_document({"essay-writer": {"command": "essay-writer", "args": []}})
    assert share["chat_tone"]["language"] is LANGUAGE
    sheet = (package_root() / "docs" / "templates" / "bot.md").read_text(encoding="utf-8")
    assert "Default to English" in LANGUAGE
    assert "current message" in LANGUAGE.casefold()
    assert "reply in the same language family" in LANGUAGE
    assert "Default to English" in sheet
    assert front_office_call is grok_speak


def test_spine_and_build_call_the_specialists():
    spine = Path(stage_track.__file__).resolve().parent.joinpath("spine.py").read_text(encoding="utf-8")
    assert "essay_writer.specialists.researcher" in spine
    assert "essay_writer.specialists.eqr" in spine
    assert "def assignment_gate" not in spine
    office = Path(build_office.__file__).read_text(encoding="utf-8")
    assert "essay_writer.specialists.researcher" in office
    assert "def essay_dig" not in office
    assert "essay_writer.specialists.eqr" in Path(word.__file__).read_text(encoding="utf-8")
    assert "essay_writer.specialists.eqr" in Path(late_chain.__file__).read_text(encoding="utf-8")


def test_later_layers_are_not_in_this_ship():
    root = package_root() / "src" / "essay_writer"
    text = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    assert "def assignment_gate" in text
    assert "per-sequence delete" not in text.casefold()
