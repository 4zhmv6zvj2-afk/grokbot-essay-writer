"""Slice 4 — template sheets exist and stay within essay-door rules."""

from pathlib import Path

from essay_writer.health import essay_health
from essay_writer.server import HANDLERS

REPO = Path(__file__).resolve().parents[1]
REVIEW = REPO / "docs" / "templates" / "review.md"
BOT = REPO / "docs" / "templates" / "bot.md"


def test_template_files_exist():
    assert REVIEW.is_file()
    assert BOT.is_file()


def test_review_sheet_strips_regulator_language():
    text = REVIEW.read_text(encoding="utf-8")
    lowered = text.casefold()
    assert "afrc" not in lowered
    assert "quinn" not in lowered
    assert "client-pack" not in lowered
    assert "official accounting" not in lowered
    assert "auditing standard" not in lowered


def test_review_sheet_covers_checklist_topics():
    text = REVIEW.read_text(encoding="utf-8")
    lowered = text.casefold()
    assert "genre" in lowered
    assert "essay" in lowered and "report" in lowered
    assert "academic-writing-helpers.md" in text
    assert "referencing-harvard.md" in text
    assert "noted" in lowered and "open" in lowered
    assert "synthetic" in lowered
    assert "match" in lowered and "draft" in lowered


def test_bot_sheet_one_essay_id_and_no_silent_word():
    text = BOT.read_text(encoding="utf-8")
    lowered = text.casefold()
    assert "one essay id" in lowered
    assert "switched on" in lowered
    assert "not switched on" not in lowered
    assert "essay-bot.share.json" in text
    assert "silent confirm" in lowered or "never silent" in lowered
    assert "start word" in lowered
    assert "from this sheet" in lowered
    silent_word_phrases = (
        "silent word",
        "silently save",
        "silent save",
        "save word without",
        "word without confirm",
    )
    assert not any(phrase in lowered for phrase in silent_word_phrases)


def test_health_still_same_doors_no_bot_door(workspace):
    report = essay_health()
    names = {door["tool"] for door in report["doors"]}
    assert names == set(HANDLERS)
    assert not any("bot" in name.casefold() for name in names)
