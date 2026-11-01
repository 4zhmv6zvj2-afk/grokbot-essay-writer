"""Anti-glue prompt on every final student Word path. Stable ids: AC1–AC8.

Build covered: Cursor cursor_stage_launch and Grok Build stage_launch both
read essay_writer.stage_llm.stage_settings. The anti-glue line is that shared
row. Grok Build puts it on grok --rules. Cursor puts the same rules on the
launch settings row. No new residual. Pax: skipped (this checkout has no Pax tests).
"""

from pathlib import Path

from helpers import open_sequence, picked, plant_gathered_source

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.doors import DOORS
from essay_writer.server import INSTRUCTIONS
from essay_writer.shells import front_office_call
from essay_writer.specialists.grok_bot import STAGE9_OWN_WORDS, saved_next
from essay_writer.stage7 import questions_for
from essay_writer.stage_llm import stage_settings, stage_title
from essay_writer.stage_track import essay_stage
from essay_writer.student_voice import student_surface_hits
from essay_writer.writing_basics import ANTI_GLUE, basics_lines

REPO = Path(__file__).resolve().parents[1]
STAGES = ("5", "6", "7", "8")
GENRES = (None, "diary", "essay", "report")
WORD_DOORS = ("essay.pack.validate", "essay.pack.render_word", "essay.revise")
OTHER_HELPERS = (
    "docs/essay-writing-helpers.md",
    "docs/report-writing-helpers.md",
    "docs/reflective-diary-helpers.md",
)
STAGE7_QUESTIONS = (
    "Does the structure still match the brief?",
    "Does the argument still answer the question?",
    "Which sentences are unclear?",
    "Which claims should be checked for currency?",
    "Which lines are too vague to defend from the sources?",
)


def _rules(command: list[str]) -> str:
    return command[command.index("--rules") + 1]


def _door(tool: str) -> str:
    return next(door["description"] for door in DOORS if door["tool"] == tool)


def _overlay(stage: str, genre: str | None) -> str:
    item = stage_settings(stage, genre)
    return item["prompt_overlay"] + "\n" + item["rules"]


def test_ac1_stages_5_to_8_shared_and_diary_carry_the_bullet():
    for stage in STAGES:
        for genre in GENRES:
            text = _overlay(stage, genre)
            assert "person the brief names" in text
            assert "Ban AI-glue" in text
            assert "ask the student once for one real detail" in text
            assert "Never invent a lecture, a reading, or a workplace detail." in text
            assert text.count(ANTI_GLUE) >= 1
            assert student_surface_hits(stage_settings(stage, genre)["prompt_overlay"]) == []
    assert questions_for("MOD1004AA-1") == list(STAGE7_QUESTIONS)
    assert len(STAGE7_QUESTIONS) == 5


def test_ac2_cursor_and_grok_build_launches_carry_the_same_rules():
    for stage in STAGES:
        shared = stage_settings(stage)
        build = stage_launch(stage)
        cursor = cursor_stage_launch(stage)
        assert build["settings"]["rules"] == shared["rules"]
        assert cursor["settings"]["rules"] == shared["rules"]
        assert ANTI_GLUE in _rules(build["command"])
        assert ANTI_GLUE in cursor["settings"]["rules"]
        assert build["source"] == cursor["source"] == "essay_writer.stage_llm.stage_settings"


def test_ac3_stage5_quiet_chat_does_not_speak_the_glue_bullet(workspace):
    seq = open_sequence()
    look = "Saved from the brief."
    for stage in ("1", "2", "3", "4a", "4b"):
        draft = essay_stage(seq, stage, "draft", look)
        assert draft["ok"] is True, draft
        if stage == "4a":
            plant_gathered_source(seq)
        saved = essay_stage(seq, stage, "confirm", look, **picked(draft))
        assert saved["stored"] is True, saved
    quiet = essay_stage(seq, "5", "draft", look)
    assert quiet["ok"] is True, quiet
    assert quiet["quiet"] is True
    assert quiet["checklist_in_chat"] is False
    spoken = " ".join(
        quiet.get(key) if isinstance(quiet.get(key), str) else ""
        for key in ("next", "chat", "confirm_line")
    )
    assert "Ban AI-glue" not in spoken
    assert "ask the student once" not in spoken
    assert "Walk this Basics checklist" not in spoken
    assert ANTI_GLUE in stage_settings("5")["rules"]


def test_ac4_diary_keeps_its_voice_and_essay_report_are_not_forced_first_person():
    for stage in STAGES:
        diary = stage_settings(stage, "diary")["rules"]
        essay = stage_settings(stage, "essay")["rules"]
        report = stage_settings(stage, "report")["rules"]
        assert "not forced into third person" in diary
        assert "brief voice" in diary
        assert "must be third person" not in diary.casefold()
        for text in (essay, report):
            assert "not forced into first person to sound human" in text
            assert "use first person to sound human" not in text.casefold()
    assert "does not turn it into a third-person essay" in stage_settings("8", "diary")["rules"]


def test_ac5_academic_helpers_stages_5_to_8_match_the_bullet():
    helpers = (REPO / "docs" / "academic-writing-helpers.md").read_text(encoding="utf-8")
    for stage in STAGES:
        assert ANTI_GLUE in helpers
        for line in basics_lines(stage):
            assert line in helpers
    for name in OTHER_HELPERS:
        assert "Ban AI-glue" not in (REPO / name).read_text(encoding="utf-8")


def test_ac6_stage9_save_names_title_opening_and_one_body_paragraph(workspace):
    seq = open_sequence()
    look = "Kept."
    for stage in ("1", "2", "3", "4a", "4b", "5", "6"):
        draft = essay_stage(seq, stage, "draft", look)
        assert draft["ok"] is True, draft
        if stage == "4a":
            plant_gathered_source(seq)
        if stage == "5":
            continue
        saved = essay_stage(seq, stage, "confirm", look, **picked(draft))
        assert saved["stored"] is True, saved
    asked = essay_stage(seq, "7", "draft", look)
    assert asked["ok"] is True, asked
    answered = essay_stage(seq, "7", "draft", look, answers="all fine / none")
    assert answered["ok"] is True, answered
    saved7 = essay_stage(seq, "7", "confirm", look, **picked(answered))
    assert saved7["stored"] is True, saved7
    draft8 = essay_stage(seq, "8", "draft", look)
    saved8 = essay_stage(seq, "8", "confirm", look, **picked(draft8))
    assert saved8["current"] == "9", saved8
    draft9 = essay_stage(seq, "9", "draft", look)
    assert draft9["stored"] is False
    assert STAGE9_OWN_WORDS not in (draft9.get("next") or "")
    saved9 = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "9",
            "confirmPhase": "confirm",
            "look": look,
            **picked(draft9),
        },
    )
    assert saved9["stored"] is True, saved9
    assert saved9["current"] == "10"
    nxt = saved9["next"]
    assert STAGE9_OWN_WORDS in nxt
    assert "title" in nxt.casefold()
    assert "opening" in nxt.casefold()
    assert "body paragraph" in nxt.casefold()
    assert "own words" in nxt.casefold()
    assert "citation" in nxt.casefold()
    assert "person the brief names" in nxt
    assert "grammarly" not in nxt.casefold()
    bot = (REPO / "docs" / "templates" / "bot.md").read_text(encoding="utf-8")
    assert STAGE9_OWN_WORDS in bot
    assert "grammarly" not in bot.casefold()
    assert saved_next("10", stage_title("10")).startswith(STAGE9_OWN_WORDS)


def test_ac7_pack_render_and_revise_carry_the_overlay():
    for tool in WORD_DOORS:
        assert ANTI_GLUE in _door(tool)
    assert ANTI_GLUE in INSTRUCTIONS


def test_ac8_build_covered_both_shells_prompt_text_only():
    """Build covered. No glue hard-fail and no similarity or AI-score chase."""
    test_ac2_cursor_and_grok_build_launches_carry_the_same_rules()
    assert "%" not in ANTI_GLUE
    assert "grammarly" not in ANTI_GLUE.casefold()
    hits = [
        path.name
        for path in (REPO / "src").rglob("*.py")
        if "Ban AI-glue" in path.read_text(encoding="utf-8")
    ]
    assert hits == ["writing_basics.py"]
