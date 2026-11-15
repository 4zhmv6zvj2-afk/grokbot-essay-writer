"""Final Word folder: Mac handoff when configured, project-10 as the fallback.

The findings chat path names the folder that was written. Stable ids: AC1–AC3.
"""

from pathlib import Path

from docx import Document
from helpers import ESSAY, ensure_word_refs, mac_handoff_sequence_dir, open_sequence

from essay_writer.late_chain import comments_place, final_place, findings_place, write_stage10
from essay_writer.paths import essay_dir, work_dir
from essay_writer.prompt_loader import text
from essay_writer.review import essay_review

QUESTION = "How do chokepoints constrain the corridor?"
CONSTITUTION = f"This is a report. {QUESTION}"
REPO = Path(__file__).resolve().parents[1]


def _brief() -> None:
    folder = essay_dir(ESSAY)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(
        f"Genre: report\nQuestion: {QUESTION}\n",
        encoding="utf-8",
    )


def _student_word(seq: str) -> None:
    path = work_dir(seq) / "output" / f"{seq}.docx"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.add_paragraph(CONSTITUTION + " (Smith, 2020).")
    document.add_paragraph("Student copy of the finished draft.")
    document.save(str(path))


def _pass_review(seq: str) -> None:
    draft = essay_review(seq, "9", "PASS", "draft", constitution=CONSTITUTION)
    assert draft["ok"] is True, draft
    stored = essay_review(seq, "9", "PASS", "confirm", constitution=CONSTITUTION)
    assert stored["stored"] is True, stored


def test_ac1_configured_handoff_names_the_essay_bot_folder(workspace, monkeypatch, tmp_path):
    """AC1. A Mac handoff writes the sequence folder, and findings chat matches the file."""
    handoff = tmp_path / "Documents" / "Essay Bot"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(handoff))
    _brief()
    seq = open_sequence()
    _student_word(seq)
    _pass_review(seq)
    ensure_word_refs(seq)
    final = write_stage10(seq)
    project_findings = handoff / ESSAY / f"{ESSAY}-findings.docx"
    sequence = mac_handoff_sequence_dir(handoff, seq)
    spoken_final = f"Documents/Essay Bot/{ESSAY}/{seq}/{ESSAY}-final.docx"
    spoken_notes = f"Documents/Essay Bot/{ESSAY}/{seq}/{ESSAY}-comments.docx"
    spoken_findings = f"Documents/Essay Bot/{ESSAY}/{ESSAY}-findings.docx"
    assert final["copied"] is True, final
    assert final_place(seq) == spoken_final
    assert comments_place(seq) == spoken_notes
    assert final["place"] == spoken_final
    assert (sequence / f"{ESSAY}-final.docx").is_file()
    assert (sequence / f"{ESSAY}-comments.docx").is_file()
    assert (sequence / f"{ESSAY}-findings.docx").is_file()
    assert project_findings.is_file()
    assert not (handoff / f"{ESSAY}-10").exists()
    assert findings_place(seq) == spoken_findings
    assert final["findings_place"] == spoken_findings
    assert findings_place(seq) != f"Documents/{ESSAY}/{ESSAY}-findings.docx"


def test_ac2_fallback_uses_project_10_when_no_handoff(workspace, monkeypatch, tmp_path):
    """AC2. With no Mac handoff, Documents/<project>-10/ is the folder the tool returns."""
    monkeypatch.delenv("ESSAY_WRITER_MAC_DIR", raising=False)
    monkeypatch.setattr("essay_writer.first_run_mac.mac_deliverables_dir", lambda **_kwargs: None)
    documents = tmp_path / "Documents"
    documents.mkdir()
    _brief()
    seq = open_sequence()
    _student_word(seq)
    _pass_review(seq)
    ensure_word_refs(seq)
    final = write_stage10(seq, documents=documents)
    spoken_final = f"Documents/{ESSAY}-10/{ESSAY}-final.docx"
    spoken_notes = f"Documents/{ESSAY}-10/{ESSAY}-comments.docx"
    folder = documents / f"{ESSAY}-10"
    assert final["copied"] is True, final
    assert final_place(seq) == spoken_final
    assert comments_place(seq) == spoken_notes
    assert final["place"] == spoken_final
    assert (folder / f"{ESSAY}-final.docx").is_file()
    assert (folder / f"{ESSAY}-comments.docx").is_file()
    assert not (documents / "Essay Bot").exists()


def test_ac3_stage10_prompt_names_the_returned_folder_not_a_hardcoded_path():
    """AC3. Stage 10 does not hardcode a Documents path the tool may not produce."""
    stage = text("stages/10.md", "shared")
    assert "Documents/<project>-10/" not in stage
    assert "folder the tool returns" in stage
    helper = (REPO / "docs" / "academic-writing-helpers.md").read_text(encoding="utf-8")
    assert "Documents/<project>-10/" not in helper
    assert "folder the tool returns" in helper
