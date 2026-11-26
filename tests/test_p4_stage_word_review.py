"""P4 behaviour: review order, critical notes, cites, titles, and comments."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from helpers import open_sequence
from test_first_draft_word import _first_draft_word, _note_path, _save_intact

from essay_writer.cite_fit import strip_token
from essay_writer.context_fit import MODEL_LINE, student_review_text
from essay_writer.harvard_ref_check import compliance_misses
from essay_writer.late_chain import _write_comments
from essay_writer.paths import essay_dir, module_code, work_dir
from essay_writer.review import eqr_record, eqr_verdict, essay_review
from essay_writer.roll_forward import has_critical_note
from essay_writer.specialists.eqr import student_findings_text
from essay_writer.specialists.writer import (
    UNREADABLE_DRAFT,
    finish_first_draft,
    first_draft_unreadable,
)
from essay_writer.state import load_state, save_state
from essay_writer.word import (
    _cover_without_opening,
    _word_document_title,
    document_title,
    saved_first_draft_text,
)

QUESTION = "Whose interests count when a river allocates water?"
OPENING = "Water moves downhill through the named reach."


def test_the_pass_is_recorded_only_after_the_word_write(workspace, monkeypatch):
    """A failed first-draft write leaves the pass unrecorded. A success stores the draft text."""
    from essay_writer import word as word_mod

    real_write = word_mod.write_first_draft_word
    seq, look = _save_intact()
    shown = essay_review(seq, "6", "PASS", "draft")
    assert shown.get("stored") is not True
    seen: list[str | None] = []

    def fail_write(essay_id: str) -> dict[str, object]:
        seen.append(eqr_verdict(essay_id, "6"))
        return {"wrote": False, "path": "", "reason": "disk-full"}

    monkeypatch.setattr(word_mod, "write_first_draft_word", fail_write)
    refused = essay_review(seq, "6", "PASS", "confirm")
    assert seen == [None]
    assert refused.get("stored") is not True
    assert refused.get("reason") == "disk-full"
    assert eqr_record(seq, "6") is None
    assert eqr_verdict(seq, "6") is None
    assert not _first_draft_word(seq).is_file()

    saved_seq, saved_look = _save_intact("MOD2002BB")
    preview = essay_review(saved_seq, "6", "PASS", "draft")
    assert preview.get("stored") is not True
    during: list[str | None] = []

    def watch_write(essay_id: str) -> dict[str, object]:
        during.append(eqr_verdict(essay_id, "6"))
        return real_write(essay_id)

    monkeypatch.setattr(word_mod, "write_first_draft_word", watch_write)
    stored = essay_review(saved_seq, "6", "PASS", "confirm")
    assert stored.get("stored") is True, stored
    assert during == [None]
    record = eqr_record(saved_seq, "6")
    assert isinstance(record, dict)
    assert record.get("draft_text") == saved_look
    assert saved_first_draft_text(saved_seq) == saved_look
    assert eqr_verdict(saved_seq, "6") == "PASS"
    path = _note_path(saved_seq, "5")
    path.write_text(
        path.read_text(encoding="utf-8").replace(saved_look, saved_look + " Later.", 1),
        encoding="utf-8",
    )
    assert saved_first_draft_text(saved_seq) != saved_look
    assert eqr_verdict(saved_seq, "6") is None
    assert workspace is not None
    assert look


def test_a_name_only_markdown_is_not_a_critical_note(workspace):
    """A non-empty review that names the paper and lacks the marker does not count."""
    seq = open_sequence()
    paper = {
        "id": "src-herring-2019",
        "title": "Herring stock recovery after closure",
        "doi": "10.1000/herring.2019",
    }
    folder = work_dir(seq) / "output" / "reviews"
    folder.mkdir(parents=True)
    note = folder / "herring-stock-recovery-after-closure.md"
    note.write_text(
        "Herring stock recovery after closure\n10.1000/herring.2019\n",
        encoding="utf-8",
    )
    assert has_critical_note(seq, paper) is False
    note.write_text(
        "Critical note:\n\nHerring stock recovery after closure\n10.1000/herring.2019\n",
        encoding="utf-8",
    )
    assert has_critical_note(seq, paper) is True
    stored = note.read_text(encoding="utf-8")
    assert "Critical note:" in stored
    assert "Critical note:" not in student_review_text(stored)
    assert workspace is not None


def test_a_stripped_name_reports_the_gap_and_a_can_do_phrase_stays(workspace):
    """Narrative cites that were the subject leave a gap. A can-do attitude stays readable."""
    del workspace
    earlier = strip_token("Earlier work by Ada (2020) found the same pattern.", "ada, 2020")
    counted = strip_token("The count from Ada (2020) stays in the table.", "ada, 2020")
    joint = strip_token("Ada (2020) and Jones (2021) argue for the same limit.", "ada, 2020")
    for report, leftover in (
        (earlier, "Earlier work by found"),
        (counted, "The count from stays"),
        (joint, "and Jones (2021) argue"),
    ):
        assert leftover in report.text
        assert report.removed
        assert any("2020" in span for span in report.removed)
        assert report.subject_gap is True
        assert first_draft_unreadable(report) is not None
    kept = strip_token("A can-do attitude (Ada, 2020) keeps the work moving.", "ada, 2020")
    assert "can-do attitude" in kept.text
    assert kept.removed
    assert kept.subject_gap is False
    assert first_draft_unreadable(kept) is None
    assert first_draft_unreadable("A can-do attitude keeps the work moving.") is None


def test_stage_5_refuses_a_draft_that_loses_its_subject(workspace):
    """Stage 5 strips a narrative cite that was the subject and does not store the draft."""
    from test_citation_list import _plant, _source, _walk, _word_path

    from essay_writer.stage_note import _note_look
    from essay_writer.stage_run import essay_stage

    seq = open_sequence()
    _plant(
        seq,
        [
            _source(
                seq,
                "smith",
                "Smith, J.",
                "2020",
                title="Chokepoints and crude",
                doi="10.1000/strait",
            )
        ],
    )
    _walk(seq)
    draft = "Earlier work by Ada (2020) found the same pattern."
    assert first_draft_unreadable(draft) is None
    held = essay_stage(seq, "5", "draft", draft)
    assert held["ok"] is False, held
    assert held["stored"] is False
    assert held["reason"] == UNREADABLE_DRAFT
    assert _note_look(seq, "5") in (None, "")
    assert not _word_path(seq).is_file()
    assert workspace is not None


def test_a_short_draft_does_not_store_the_question_or_filler(workspace):
    """A draft that cannot reach the band stays the student's text."""
    del workspace
    seq = open_sequence()
    folder = essay_dir(module_code(seq))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(
        f"Genre: essay\nQuestion: {QUESTION}\nWord count: 2,000 words (1,800 to 2,200).\n",
        encoding="utf-8",
    )
    short = "Water moves downhill."
    finished = finish_first_draft(seq, short)
    assert finished["ready"] is False
    assert finished["text"].strip() == short
    assert QUESTION not in finished["text"]
    assert "takes up the assignment" not in finished["text"]


def test_comments_drop_only_the_model_line(workspace, tmp_path: Path):
    """A quoted model name stays. The metadata line and the bare marker leave the Word file."""
    seq = open_sequence()
    findings = (
        f"{MODEL_LINE}\n"
        "Critical note:\n"
        'The method quotes "grok-4.7" as a label.\n'
        "North-star judgement\n"
        "The claim holds.\n"
    )
    reviewed = student_review_text(findings)
    scrubbed = student_findings_text(findings)
    assert "Critical note:" in findings
    assert MODEL_LINE not in reviewed
    assert MODEL_LINE not in scrubbed
    assert "Critical note:" not in reviewed
    assert "Critical note:" not in scrubbed
    assert "grok-4.7" in scrubbed
    assert "Overall judgement" in scrubbed
    state = load_state(seq)
    state["eqr"] = {
        "9": {
            "verdict": "PASS",
            "seat": "reviewer",
            "word_opened": True,
            "findings": findings,
        }
    }
    save_state(seq, state)
    path = tmp_path / "comments.docx"
    _write_comments(seq, path)
    text = "\n".join(paragraph.text for paragraph in Document(str(path)).paragraphs)
    assert MODEL_LINE not in text
    assert "Critical note:" not in text
    assert "grok-4.7" in text
    assert workspace is not None


def test_the_cover_drops_the_opening_once_and_the_title_stays_short(workspace):
    """The heading stays. The title is the stored short title, then the id, then the file name."""
    sections = [{"heading": "Introduction", "body": OPENING}]
    lines = ["Introduction", OPENING, "The next sentence stays.", OPENING]
    kept = _cover_without_opening(lines, sections)
    assert kept[0] == "Introduction"
    assert kept.count(OPENING) == 1
    assert "The next sentence stays." in kept

    long_title = ("Herring stock recover after the closure " * 4).strip()
    assert len(long_title) <= 255
    assert long_title != OPENING
    assert document_title("C" * 255, "ASSESS", "file-name", opening=OPENING) == "C" * 255
    assert document_title("D" * 256, "ASSESS", "file-name", opening=OPENING) == "ASSESS"
    assert document_title(long_title, "ASSESS", "file-name", opening=OPENING) == long_title
    assert document_title("", "ASSESS", "file-name", opening=OPENING, fallback="ASSESS") == "ASSESS"
    assert (
        document_title(OPENING, "ASSESS", "file-name", opening=OPENING, fallback="ASSESS")
        == "ASSESS"
    )
    assert document_title("", "", "file-name", opening=OPENING, fallback="file-name") == "file-name"

    seq = open_sequence()
    draft = work_dir(seq) / "output" / f"{seq}.docx"
    draft.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.core_properties.title = "Short herring title"
    document.add_paragraph(OPENING)
    document.save(str(draft))
    target = work_dir(seq) / "output" / "harbour-final.docx"
    pack = {"sections": [{"heading": "Introduction", "body": OPENING}]}
    assert _word_document_title(seq, pack, pack, target) == "Short herring title"
    draft.unlink()
    same = {"sections": [{"heading": "Introduction", "body": seq}]}
    assert _word_document_title(seq, same, same, target) == "harbour-final"
    packed = {"title": "Pack title", "sections": [{"heading": "Introduction", "body": OPENING}]}
    assert _word_document_title(seq, packed, packed, target) == seq
    assert workspace is not None


def test_an_unmatched_source_is_a_recorded_miss(workspace, tmp_path: Path):
    """A source with no reference line is a checked miss."""
    del workspace
    path = tmp_path / "refs.docx"
    document = Document()
    document.add_paragraph("The corridor depends on a narrow strait (Alden, 2019).")
    document.add_paragraph("References")
    document.add_paragraph("Alden, P. (2019) Narrow straits. Journal of Routes, 1(1), pp. 1-2.")
    document.save(str(path))
    misses = compliance_misses(
        path,
        [
            {
                "author": "Alden, P.",
                "year": "2019",
                "title": "Narrow straits",
                "id": "src-alden-2019",
            },
            {
                "author": "Berry, R.",
                "year": "2020",
                "title": "Unused harbour note",
                "id": "src-berry-2020",
            },
        ],
    )
    unmatched = [item for item in misses if item.get("code") == "source-line"]
    assert unmatched
    assert any("Berry" in item.get("detail", "") for item in unmatched)
