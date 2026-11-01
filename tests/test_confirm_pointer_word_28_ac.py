"""Bugs #28–#31 and the #26 Word gap. One confirm loop, one Word render.

AC1–AC4 are the door and the pointer. AC5–AC6 are the docx. AC7 is the briefing.
Essay Bot may only show the Confirm card the door returned.
"""

import inspect
import zipfile
from pathlib import Path

from docx import Document
from helpers import mac_handoff_sequence_dir, picked, plant_gathered_source, with_word_references

from essay_writer.assignment_gate import read_assignment
from essay_writer.brief_contract import (
    MAPPED_TYPE_OVERLAY,
    register_mapping,
    sequence_registration,
    unregister_mapping,
)
from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch, stage_host_launch
from essay_writer.late_chain import write_stage10
from essay_writer.paths import essay_dir, work_dir
from essay_writer.projects import essay_sequence_new
from essay_writer.server import INSTRUCTIONS
from essay_writer.setup import SHELL_CURSOR, SHELL_GROK_BUILD
from essay_writer.shells import cursor_shell, front_office
from essay_writer.stage_llm import stage_settings
from essay_writer.stage_track import essay_stage, load_pointer
from essay_writer.state import load_state, save_state
from essay_writer.word import empty_footer_refusal, essay_pack_render_word, write_docx
from essay_writer.writing_basics import STAGE_ORDER

REPO = Path(__file__).resolve().parents[1]
LOOK = "The task is a short report on the corridor."
NUMBER = "445566"
MODULE = "QUA9001HK"
BRIEF = """
Assignment title: Individual reflective diary

Module title: Practice module
Module code: QUA9001HK

Aim: Understand the practice by reflecting on your own decisions.

Assignment task: Write four entries. Each entry names one decision and critically analyses it with theory and evidence.

Title page: module title, module code, assignment title, registration number, and the word count.
The name stays off the title page and the file.

Pages: Arial, size 12. 2.5 cm margins on all sides. Page numbers in the lower right.
"""
def _open(module: str) -> str:
    draft = essay_sequence_new(module, "draft")
    assert draft["ok"] is True, draft
    opened = essay_sequence_new(module, "confirm")
    assert opened["ok"] is True, opened
    return opened["sequence_id"]


def _note(seq: str, stage: str) -> str:
    return (work_dir(seq) / "tracking" / f"{stage}.md").read_text(encoding="utf-8")


def _footer(path: Path) -> str:
    return zipfile.ZipFile(path).read("word/footer1.xml").decode("utf-8")


def _pack(seq: str, *, number: str | None) -> dict:
    body = {
        "essay_id": seq,
        "title": "Individual reflective diary",
        "referencing": "harvard",
        "assessment": "Individual reflective diary",
        "module_title": "Practice module",
        "conclusion": "noted",
        "student_name": "Ada Example",
        "sections": [
            {
                "heading": "One decision",
                "body": "A decision, with theory, on the practice the brief names.",
            }
        ],
    }
    if number:
        body["registration_number"] = number
    return body


def _report(pack: dict) -> dict:
    return {
        "title": "Individual reflective diary",
        "word_count": {"counted": 40, "stated": 2000},
        "sections": pack["sections"],
        "figures": [],
        "tables": [],
        "sources": [],
    }


def test_ac1_finished_answer_returns_the_card(workspace):
    """AC1. A finished answer returns confirm fields and next. Stage 5 has no card."""
    seq = _open("MOD1004AA")
    for stage in STAGE_ORDER:
        if stage == "5":
            done = essay_stage(seq, "5", "draft", LOOK)
            assert done["ok"] is True, done
            assert done["stored"] is True
            assert "card" not in done
            assert load_pointer(seq)["current"] == "6"
            continue
        kwargs = {"answers": "all fine"} if stage == "7" else {}
        draft = essay_stage(seq, stage, "draft", LOOK, **kwargs)
        assert draft["ok"] is True, draft
        assert draft["stored"] is False
        assert draft["card"]["kind"] == "confirm"
        assert draft["cardAction"] == "confirm"
        assert draft["cardDigest"] == draft["digest"]
        assert isinstance(draft.get("next"), str) and draft["next"].strip()
        assert load_pointer(seq)["current"] == stage
        assert stage not in load_pointer(seq)["saved"]
        assert "Status: draft" in _note(seq, stage)
        assert "Status: final" not in _note(seq, stage)
        if stage == "10":
            break
        if stage == "4a":
            plant_gathered_source(seq)
        saved = essay_stage(seq, stage, "confirm", **picked(draft))
        assert saved["stored"] is True, saved


def test_ac2_stray_fields_do_not_change_the_card(workspace):
    """AC2. Extra confirm fields still save. No-card no-change returns a card on stage 2."""
    seq = _open("MOD1004AA")
    essay_stage(seq, "1", "confirm", **picked(essay_stage(seq, "1", "draft", LOOK)))
    draft = essay_stage(seq, "2", "draft", LOOK)
    saved = essay_stage(
        seq,
        "2",
        "confirm",
        look="a different look",
        answers="change the year",
        edited="A new sentence.",
        webCheck={"currency": False},
        **picked(draft),
    )
    assert saved["ok"] is True, saved
    assert saved["stored"] is True
    assert load_pointer(seq)["current"] == "3"
    assert "2" in load_pointer(seq)["saved"]
    assert LOOK in _note(seq, "2")
    assert "change the year" not in _note(seq, "2")

    other = _open("RPT1008AA")
    opened = essay_stage(other, "1", "draft", LOOK)
    assert opened["ok"] is True, opened
    quiet = essay_stage(other, "2", "confirm", look="all fine")
    assert quiet["ok"] is False or quiet.get("card", {}).get("stage") == "1"
    # Stage 2 is not current yet. No-change on the current stage, which is not stage 7.
    held = essay_stage(other, "1", "confirm", look="all fine")
    assert held["ok"] is True, held
    assert held["stored"] is False
    assert held["card"]["kind"] == "confirm"
    assert held["cardAction"] == "confirm"
    assert held["cardDigest"]
    assert load_pointer(other)["current"] == "1"
    assert "1" not in load_pointer(other)["saved"]
    assert "Status: draft" in _note(other, "1")


def test_ac3_confirm_returns_the_next_card_and_clears_waiting(workspace):
    """AC3. Confirm saves, moves current, and returns the next card. Stage 5 does not."""
    seq = _open("MOD1004AA")
    draft = essay_stage(seq, "1", "draft", LOOK)
    saved = essay_stage(seq, "1", "confirm", **picked(draft))
    pointer = load_pointer(seq)
    assert "1" in pointer["saved"]
    assert pointer["current"] == "2"
    assert pointer["waiting_stage"] == "2"
    assert pointer["waiting_digest"] == saved["cardDigest"]
    assert saved["repost"] is False
    assert saved["card"]["stage"] == "2"
    assert saved["card"]["kind"] == "confirm"
    assert saved["card"]["stage"] != "1"

    for stage in STAGE_ORDER:
        if stage == "5":
            break
        if stage == "1":
            continue
        opened = essay_stage(seq, stage, "draft", LOOK)
        if stage == "4a":
            plant_gathered_source(seq)
        essay_stage(seq, stage, "confirm", **picked(opened))
    done = essay_stage(seq, "5", "draft", LOOK)
    assert done["stored"] is True, done
    assert done["explicit_end"] is True
    assert "card" not in done
    assert load_pointer(seq)["current"] == "6"
    assert load_pointer(seq)["waiting_digest"] is None


def test_ac4_saved_stage_does_not_replay_its_card(workspace):
    """AC4. Confirm of a saved stage is not waiting, and the card is current's."""
    seq = _open("MOD1004AA")
    draft = essay_stage(seq, "1", "draft", LOOK)
    essay_stage(seq, "1", "confirm", **picked(draft))
    again = essay_stage(seq, "1", "confirm", **picked(draft))
    assert again["ok"] is False, again
    assert "already saved" in again["reason"]
    assert again["waiting_confirm"] is False
    assert again.get("card", {}).get("stage") != "1"
    assert again["card"]["stage"] == load_pointer(seq)["current"] == "2"
    fresh = essay_stage(seq, "2", "draft", "Purpose stays with the brief.")
    assert fresh["ok"] is True, fresh
    assert fresh["card"]["stage"] == "2"
    assert fresh["card"]["stage"] != "1"


def test_ac5_ac6_registration_once_and_page_field(workspace, monkeypatch, tmp_path):
    """AC5 and AC6. Stored registration on 6 and 10. Lower-right PAGE. Empty footer refuses."""
    documents = tmp_path / "Documents"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    folder = essay_dir(MODULE)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(BRIEF, encoding="utf-8")
    seq = _open(MODULE)
    record = read_assignment(seq)
    assert record["title_page"]["registration"] is True
    assert record["page_layout"]["page_number"] == "right"

    empty = _pack(seq, number=None)
    reasons = set()
    for stage in ("6", "7", "9"):
        refused = essay_pack_render_word(seq, empty, "confirm", stage=stage)
        assert refused["ok"] is False, refused
        assert refused["refused"] == "title-page"
        assert "registration number" in refused["reason"]
        assert "invented" in refused["reason"]
        assert refused.get("wrote") is not True
        reasons.add(refused["reason"])
    state = load_state(seq)
    state["saved_pack"] = dict(empty)
    save_state(seq, state)
    final_refused = write_stage10(seq)
    assert final_refused["ok"] is False, final_refused
    assert final_refused["refused"] == "title-page"
    assert "registration number" in final_refused["reason"]
    reasons.add(final_refused["reason"])
    assert len(reasons) == 1
    assert sequence_registration(seq) is None

    supplied = _pack(seq, number=NUMBER)
    preview = essay_pack_render_word(seq, supplied, "draft", stage="6")
    assert preview.get("refused") != "title-page"
    assert sequence_registration(seq) == NUMBER

    bare = _pack(seq, number=None)
    assert "registration_number" not in bare
    report = _report(bare)
    stage6 = work_dir(seq) / "output" / f"{seq}.docx"
    write_docx(seq, bare, report, stage6)
    state = load_state(seq)
    state["saved_pack"] = with_word_references(bare)
    save_state(seq, state)
    final = write_stage10(seq)
    assert final["copied"] is True, final
    final_path = mac_handoff_sequence_dir(documents, seq) / f"{MODULE}-final.docx"
    assert final_path.is_file()
    stage6_text = "\n".join(paragraph.text for paragraph in Document(str(stage6)).paragraphs)
    final_text = "\n".join(paragraph.text for paragraph in Document(str(final_path)).paragraphs)
    for text in (stage6_text, final_text):
        assert "Practice module" in text
        assert MODULE in text
        assert "Individual reflective diary" in text
        assert f"Registration number: {NUMBER}" in text
        assert "Ada Example" not in text
    assert "Counted words:" in stage6_text
    assert "Counted words:" in final_text
    for path in (stage6, final_path):
        footer = _footer(path)
        assert "PAGE" in footer
        assert "instrText" in footer
        assert 'w:val="right"' in footer

    blank = tmp_path / "empty.docx"
    Document().save(blank)
    refused_footer = empty_footer_refusal(blank)
    assert refused_footer is not None
    assert refused_footer["refused"] == "footer"
    assert "empty footer" in refused_footer["reason"]


def test_ac7_briefing_follows_the_pointer_and_the_record():
    """AC7. The three briefings print a required number and do not freelance the next card."""
    bot = (REPO / "docs" / "templates" / "bot.md").read_text(encoding="utf-8")
    workflow = (REPO / "docs" / "workflow.md").read_text(encoding="utf-8")
    for text in (INSTRUCTIONS, bot, workflow):
        assert "Essay Bot may only show the Confirm card the door returned" in text
        assert "does not pick the next stage itself" in text
        assert "latest tool result" in text or "card the tool returned" in text
        assert "registration number" in text
        assert "Do not invent a registration number" in text
        lowered = text.casefold()
        assert "lower right" in lowered or "where the assignment record says" in lowered


def test_build_covered_cursor_and_grok_share_the_word_path(monkeypatch):
    """Both mid-office shells use one stage record and one write_docx final."""
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_CURSOR)
    cursor = stage_host_launch("10")
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_GROK_BUILD)
    grok = stage_host_launch("10")
    assert cursor_stage_launch("10")["settings"]["rules"] == stage_launch("10")["settings"]["rules"]
    assert cursor["settings"]["rules"] == grok["settings"]["rules"] == stage_settings("10")["rules"]
    register_mapping("fieldnote", lambda text: {})
    try:
        overlay = stage_settings("2", "fieldnote")["prompt_overlay"]
    finally:
        unregister_mapping("fieldnote")
    assert overlay == MAPPED_TYPE_OVERLAY
    assert "page layout" in overlay
    assert "registration number" in overlay
    source = inspect.getsource(write_stage10)
    assert "write_docx(" in source
    assert "copy2" not in source
    assert cursor_shell()["handlers"]["essay.stage"] is front_office()["handlers"]["essay.stage"]
    assert "diary-only" not in stage_settings("10")["rules"]
