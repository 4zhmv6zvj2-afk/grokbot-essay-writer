"""Confirm-card hydration, bold brief labels, and unmounted delivery speech."""

from pathlib import Path

from docx import Document
from helpers import (
    ESSAY,
    open_sequence,
    picked,
    plant_gathered_source,
    plant_renderable_pack,
)

from essay_writer.assignment_gate import read_assignment
from essay_writer.build_status import subject_for
from essay_writer.paths import essay_dir, work_dir
from essay_writer.review import essay_review
from essay_writer.server import INSTRUCTIONS
from essay_writer.specialists.grok_bot import OPENING_CHOICE
from essay_writer.specialists.writer import FIRST_DRAFT_NOTE
from essay_writer.stage_llm import stage_settings
from essay_writer.stage_track import essay_stage, load_pointer
from essay_writer.textutil import genre_from_brief_text
from essay_writer.writing_basics import CHECKLISTS, STAGE_ORDER

QUESTION = "How should the firm manage the corridor?"
LOOK = f"This is a report. {QUESTION}"


def _stage_look(seq: str) -> str:
    from essay_writer.specialists.grok_bot import basics_pass_lines

    return "\n".join(basics_pass_lines(seq)) + "\n" + LOOK
BOLD_BRIEF = (
    "**Genre:** report\n"
    "Supply chain context and warehouse analysis that must not become the status line.\n"
    f"**Question:** {QUESTION}\n"
)


def _brief(text: str) -> None:
    folder = essay_dir(ESSAY)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(text, encoding="utf-8")


def test_bold_genre_and_question_labels_do_not_join_the_brief(workspace):
    assert genre_from_brief_text("**Genre:** report\n") == "report"
    assert genre_from_brief_text("*Genre:* essay\n") == "essay"
    _brief("**Format:** essay\n**Task:** Should the council publish the figure?\n")
    seq = open_sequence()
    seen = read_assignment(seq)
    assert seen["format"] == "essay"
    assert seen["question"] == "Should the council publish the figure?"
    _brief(BOLD_BRIEF)
    seen = read_assignment(seq)
    assert seen["format"] == "report"
    assert seen["question"] == QUESTION
    assert subject_for(seq) == QUESTION
    assert "warehouse" not in subject_for(seq)
    _brief("**Genre:** report\n" + ("Warehouse analysis of the corridor network. " * 8))
    assert read_assignment(seq)["question"] is None
    assert subject_for(seq) == seq
    assert "Warehouse" not in subject_for(seq)


def test_card_only_confirm_hydrates_every_card_stage_and_typed_confirm_stays_refused(workspace):
    _brief(BOLD_BRIEF)
    seq = open_sequence()
    look = _stage_look(seq)
    draft = essay_stage(seq, "1", "draft", look)
    assert draft["ok"] is True, draft
    typed = essay_stage(seq, "1", "confirm")
    assert typed["refused"] == "confirm-card"
    typed = essay_stage(seq, "1", "confirm", cardAction="yes", cardDigest=draft["digest"])
    assert typed["refused"] == "confirm-card"
    assert load_pointer(seq)["saved"] == []
    saved = essay_stage(seq, "1", "confirm", cardAction="confirm", cardDigest=draft["digest"])
    assert saved["stored"] is True, saved
    assert saved["current"] == "2"

    for stage in STAGE_ORDER:
        if stage == "1":
            continue
        draft = essay_stage(seq, stage, "draft", look)
        assert draft["ok"] is True, draft
        if stage == "4a":
            plant_gathered_source(seq)
        if stage == "5":
            assert draft["stored"] is True, draft
            assert "card" not in draft
            continue
        refused = essay_stage(seq, stage, "confirm", cardAction="ok", cardDigest=draft["digest"])
        assert refused["refused"] == "confirm-card"
        assert refused["stored"] is not True
        if stage == "10":
            plant_renderable_pack(seq)
        saved = essay_stage(seq, stage, "confirm", cardAction="confirm", cardDigest=draft["digest"])
        assert saved["stored"] is True, saved
        if stage == "10":
            assert "Documents" not in saved["next"]
            assert "this chat" in saved["next"]
            assert "sequence" in saved["next"]
            assert "does not submit" in saved["next"]
            assert saved["final_word"]["reason"] == "mac-not-mounted"
            assert saved["final_word"]["place"] == ""


def test_card_only_confirm_restores_stage7_fields(workspace):
    _brief(BOLD_BRIEF)
    seq = open_sequence()
    look = _stage_look(seq)
    for stage in STAGE_ORDER:
        if stage == "7":
            break
        draft = essay_stage(seq, stage, "draft", look)
        assert draft["ok"] is True, draft
        if stage == "4a":
            plant_gathered_source(seq)
        if stage == "5":
            continue
        saved = essay_stage(seq, stage, "confirm", **picked(draft))
        assert saved["stored"] is True, saved
    asked = essay_stage(seq, "7", "draft", look)
    assert asked["ok"] is True, asked
    edited = essay_stage(
        seq,
        "7",
        "draft",
        look,
        answers="Keep the corridor claim.",
        edited="The corridor claim stays.",
        webCheck={"currency": True, "clarity": True},
    )
    assert edited["ok"] is True, edited
    saved = essay_stage(seq, "7", "confirm", cardAction="confirm", cardDigest=edited["digest"])
    assert saved["stored"] is True, saved
    assert saved["current"] == "8"


def test_review_opens_the_sequence_word_and_unmounted_findings_stay_in_chat(workspace):
    _brief(BOLD_BRIEF)
    seq = open_sequence()
    path = work_dir(seq) / "output" / f"{seq}.docx"
    path.parent.mkdir(parents=True)
    document = Document()
    document.add_paragraph(LOOK + " (Smith, 2020).")
    document.save(str(path))
    draft = essay_review(seq, "9", "PASS", "draft", constitution=LOOK)
    assert draft["word_opened"] is True
    assert "Opened the saved Word file" in draft["findings"]
    stored = essay_review(seq, "9", "PASS", "confirm", constitution=LOOK)
    assert stored["stored"] is True, stored
    assert stored["word_opened"] is True
    assert stored["findings_file"]["reason"] == "mac-not-mounted"
    assert stored["findings_file"]["wrote"] is False
    assert stored["findings_file"]["place"] == ""
    assert "Documents" not in stored["next"]
    assert "this chat" in stored["next"]
    assert "sequence" in stored["next"]


def test_opening_and_stage5_argument_are_on_the_shared_briefing():
    assert "A is a new essay" in OPENING_CHOICE
    assert "essay.sequence.new" in OPENING_CHOICE
    assert "MOD1004AA-2" in OPENING_CHOICE
    assert "Do not delete it" in OPENING_CHOICE
    assert OPENING_CHOICE in INSTRUCTIONS
    assert "Do not invent a Documents path." in INSTRUCTIONS
    sheet = (Path(__file__).resolve().parents[1] / "docs" / "templates" / "bot.md").read_text(
        encoding="utf-8"
    )
    assert "A — new essay" in sheet
    assert "MOD1004AA-2" in sheet
    assert "FIRST-RUN.txt" in sheet
    assert "argument that answers the question" in CHECKLISTS["5"][0]
    assert CHECKLISTS["5"][0] in stage_settings("5")["prompt_overlay"]
    assert "essay argument" in FIRST_DRAFT_NOTE
    assert "Do not paste them in as the body." in FIRST_DRAFT_NOTE
