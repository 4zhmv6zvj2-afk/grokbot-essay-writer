"""Student proof docs in chat and Mac. Stable ids: AC1–AC8.

Build covered: Cursor and Grok Build share ship_4b, write_findings_note,
essay.stage Stage 4b Confirm, and essay.review for stages 6 and 9.
"""

from __future__ import annotations

import base64
import inspect
from pathlib import Path

from docx import Document
from helpers import (
    ESSAY,
    mac_handoff_sequence_dir,
    open_sequence,
    picked,
    plant_gathered_source,
)

from essay_writer.paths import work_dir
from essay_writer.review import essay_review
from essay_writer.shells import front_office_call
from essay_writer.specialists.eqr import CLAIM_CHECKS, NORTH_STAR, write_findings_note
from essay_writer.stage_track import essay_stage
from essay_writer.student_voice import speak

REPO = Path(__file__).resolve().parents[1]
CONSTITUTION = "This is a report. How do chokepoints constrain the corridor?"


def _essay_bot(tmp_path) -> Path:
    return tmp_path / "Documents" / "Essay Bot"


def _brief() -> None:
    from essay_writer.paths import essay_dir

    folder = essay_dir(ESSAY)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(
        f"Genre: report\nQuestion: {CONSTITUTION}\n",
        encoding="utf-8",
    )


def _student_word(seq: str) -> None:
    path = work_dir(seq) / "output" / f"{seq}.docx"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.add_paragraph(CONSTITUTION + " (Smith, 2020).")
    document.save(str(path))


def _through_4a(seq: str) -> None:
    for stage, look in (
        ("1", "The task is a report."),
        ("2", "Purpose and scope are locked."),
        ("3", "The plan holds the central theme."),
    ):
        draft = essay_stage(seq, stage, "draft", look)
        essay_stage(seq, stage, "confirm", look, **picked(draft))
    plant_gathered_source(seq)
    drafted_4a = essay_stage(seq, "4a", "draft", "One source is gathered.")
    essay_stage(seq, "4a", "confirm", "One source is gathered.", **picked(drafted_4a))


def test_ac1_stage_4b_zip_delivers_in_chat_and_mac(workspace, tmp_path, monkeypatch):
    """AC1. critical-reviews.zip is in the chat payload and the Mac Essay Bot folder."""
    bot = _essay_bot(tmp_path)
    bot.mkdir(parents=True)
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(bot))
    seq = open_sequence()
    _through_4a(seq)
    drafted = essay_stage(seq, "4b", "draft", "The read can start.")
    saved = essay_stage(seq, "4b", "confirm", "The read can start.", **picked(drafted))
    assert saved["stored"] is True
    chat = saved["delivery"]["reviews_zip"]["chat"]
    assert chat["deliver"] == "chat"
    assert chat["name"] == "critical-reviews.zip"
    assert "zip_base64" in chat
    archive = work_dir(seq) / "output" / "critical-reviews.zip"
    assert base64.b64decode(chat["zip_base64"]) == archive.read_bytes()
    assert (mac_handoff_sequence_dir(bot, seq) / "critical-reviews.zip").is_file()


def test_ac2_fo_speech_names_4b_zip_in_chat(workspace, tmp_path, monkeypatch):
    """AC2. Front-office speech points at critical-reviews.zip after Stage 4b save."""
    bot = _essay_bot(tmp_path)
    bot.mkdir(parents=True)
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(bot))
    seq = open_sequence()
    _through_4a(seq)
    drafted = essay_stage(seq, "4b", "draft", "The read can start.")
    spoken = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "4b",
            "confirmPhase": "confirm",
            "look": "The read can start.",
            **picked(drafted),
        },
    )
    assert "critical-reviews.zip" in (spoken.get("next") or "").casefold()
    assert "attached" in (spoken.get("next") or "").casefold()


def test_ac3_stage_6_findings_word_delivers_in_chat_and_mac(workspace, monkeypatch, tmp_path):
    """AC3. Stage 6 EQR findings Word is in chat and copied to the Mac handoff folder."""
    documents = tmp_path / "Documents"
    documents.mkdir(parents=True)
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    _brief()
    seq = open_sequence()
    _student_word(seq)
    essay_review(seq, "6", "PASS", "draft", constitution=CONSTITUTION)
    stored = essay_review(seq, "6", "PASS", "confirm", constitution=CONSTITUTION)
    assert stored["stored"] is True
    chat = stored["delivery"]["findings"]
    assert chat["name"] == f"{ESSAY}-findings.docx"
    assert "docx_base64" in chat
    mac_copy = stored["findings_file"]["mac_copy"]
    assert mac_copy["copied"] is True
    assert (mac_handoff_sequence_dir(documents, seq) / f"{ESSAY}-findings.docx").is_file()
    assert (documents / ESSAY / f"{ESSAY}-findings.docx").is_file()


def test_ac4_fo_speech_names_stage_6_findings_in_chat(workspace, monkeypatch, tmp_path):
    """AC4. Front-office speech points at the Stage 6 findings Word file."""
    documents = tmp_path / "Documents"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    _brief()
    seq = open_sequence()
    _student_word(seq)
    essay_review(seq, "6", "PASS", "draft", constitution=CONSTITUTION)
    spoken = speak(essay_review(seq, "6", "PASS", "confirm", constitution=CONSTITUTION))
    assert f"{ESSAY}-findings.docx" in (spoken.get("next") or "")
    assert "attached" in (spoken.get("next") or "").casefold()


def test_ac5_stage_6_uses_write_findings_note_chat_docx(workspace, monkeypatch, tmp_path):
    """AC5. Stage 6 confirm goes through write_findings_note and returns chat_docx."""
    documents = tmp_path / "Documents"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    _brief()
    seq = open_sequence()
    _student_word(seq)
    draft = essay_review(seq, "6", "PASS", "draft", constitution=CONSTITUTION)
    findings = draft["findings"]
    direct = write_findings_note(seq, findings, documents=documents)
    assert "chat_docx" in direct
    assert direct["chat_docx"]["name"] == f"{ESSAY}-findings.docx"
    stored = essay_review(seq, "6", "PASS", "confirm", constitution=CONSTITUTION)
    assert stored["findings_file"]["chat_docx"]["name"] == f"{ESSAY}-findings.docx"


def test_ac6_stage_6_mac_fold_from_write_findings_note(workspace, monkeypatch, tmp_path):
    """AC6. write_findings_note copies findings into Documents/Essay Bot/<module>/<essay_id>/."""
    documents = tmp_path / "Documents"
    documents.mkdir(parents=True)
    bot = _essay_bot(tmp_path)
    bot.mkdir(parents=True)
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(bot))
    _brief()
    seq = open_sequence()
    _student_word(seq)
    draft = essay_review(seq, "6", "PASS", "draft", constitution=CONSTITUTION)
    written = write_findings_note(seq, draft["findings"], documents=documents)
    assert written["mac_copy"]["copied"] is True
    assert (mac_handoff_sequence_dir(bot, seq) / f"{ESSAY}-findings.docx").is_file()
    assert (documents / ESSAY / f"{ESSAY}-findings.docx").is_file()


def test_ac7_stage_9_findings_word_delivers_in_chat_and_mac(workspace, monkeypatch, tmp_path):
    """AC7. Stage 9 review Word delivers in chat and on the Mac."""
    documents = tmp_path / "Documents"
    documents.mkdir(parents=True)
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    _brief()
    seq = open_sequence()
    _student_word(seq)
    draft = essay_review(seq, "9", "PASS", "draft", constitution=CONSTITUTION)
    assert NORTH_STAR in draft["findings"]
    assert CLAIM_CHECKS in draft["findings"]
    stored = essay_review(seq, "9", "PASS", "confirm", constitution=CONSTITUTION)
    assert stored["delivery"]["findings"]["name"] == f"{ESSAY}-findings.docx"
    assert (mac_handoff_sequence_dir(documents, seq) / f"{ESSAY}-findings.docx").is_file()


def test_ac8_fo_speech_names_stage_9_findings_in_chat(workspace, monkeypatch, tmp_path):
    """AC8. Front-office speech points at the Stage 9 findings Word file."""
    documents = tmp_path / "Documents"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    _brief()
    seq = open_sequence()
    _student_word(seq)
    essay_review(seq, "9", "PASS", "draft", constitution=CONSTITUTION)
    spoken = speak(essay_review(seq, "9", "PASS", "confirm", constitution=CONSTITUTION))
    assert f"{ESSAY}-findings.docx" in (spoken.get("next") or "")
    assert "attached" in (spoken.get("next") or "").casefold()


def test_build_covered_shared_delivery_helpers():
    """Build covered: one ship_4b and one write_findings_note path for Cursor and Build."""
    from essay_writer import research_packs
    from essay_writer.specialists import eqr, researcher

    ship_src = inspect.getsource(research_packs.ship_4b)
    assert "chat_zip" in ship_src
    assert "copy_deliverable_to_mac" in ship_src
    findings_src = inspect.getsource(eqr.write_findings_note)
    assert "chat_docx" in findings_src
    assert "copy_deliverable_to_mac" in findings_src
    assert inspect.getsource(researcher.deliver_critical_reviews)
