"""Golden conversations. Synthetic fixtures, a fake shell, the real doors.

The five paths are the gather and citation list, the first draft, the review
pass and first-draft Word file, the final Word file, and the two refusals
(unreadable draft, missing question). Each path checks the student reply,
the file on disk, and, where a Word file is written, the text inside it.
"""

from __future__ import annotations

import json
from pathlib import Path

from conversations.drive import (
    citation_list_path,
    docx_text,
    final_word,
    first_draft,
    gather_and_list,
    missing_question,
    open_sequence,
    output_dir,
    review_first_word,
    unreadable_draft,
)
from conversations.fixtures import DRAFT, FINAL_SENTENCE, SHORT
from conversations.shell import FakeShell
from essay_writer.source_floor import ASK_QUESTION
from essay_writer.specialists.writer import UNREADABLE_DRAFT


def test_gather_writes_the_citation_list_and_a_word_note(workspace: Path) -> None:
    """The shell confirms the synthetic gather. The list and a Word note land on disk."""
    shell = FakeShell()
    seq = open_sequence(shell)
    saved = gather_and_list(shell, seq)
    assert saved.get("stored") is True, saved
    assert shell.student_line(saved)
    listed = json.loads(citation_list_path(seq).read_text(encoding="utf-8"))
    assert listed.get("written") is True
    assert listed["entries"]
    notes = list(output_dir(seq).rglob("*.docx"))
    assert notes
    assert workspace.is_dir()


def test_first_draft_stores_the_student_sentence(workspace: Path) -> None:
    """Stage 5 stores the synthetic draft and says what happens next."""
    shell = FakeShell()
    seq = open_sequence(shell)
    gathered = gather_and_list(shell, seq)
    assert gathered.get("stored") is True, gathered
    saved = first_draft(shell, seq)
    assert saved.get("stored") is True, saved
    line = shell.student_line(saved)
    assert line
    note = (output_dir(seq).parent / "tracking" / "5.md").read_text(encoding="utf-8")
    assert SHORT in note or DRAFT.split(".")[0] in note
    assert workspace.is_dir()


def test_review_pass_writes_the_first_draft_word_file(workspace: Path) -> None:
    """A reviewer pass writes the first-draft Word file from the saved sentence."""
    shell = FakeShell()
    seq = open_sequence(shell)
    assert gather_and_list(shell, seq).get("stored") is True
    assert first_draft(shell, seq).get("stored") is True, shell.replies[-1]["result"]
    saved = review_first_word(shell, seq)
    assert saved.get("stored") is True, saved
    assert shell.student_line(saved)
    path = output_dir(seq) / f"{seq}.docx"
    assert path.is_file()
    text = docx_text(path)
    assert "ports shape coastal trade" in text
    assert workspace.is_dir()


def test_stage10_writes_the_final_word_file(workspace: Path) -> None:
    """Stage 10 confirm writes the final Word file and names it in the reply."""
    shell = FakeShell()
    seq = open_sequence(shell)
    _write = gather_and_list(shell, seq)
    assert _write.get("stored") is True, _write
    saved = final_word(shell, seq)
    assert saved.get("stored") is True, saved
    assert shell.student_line(saved)
    finals = list(output_dir(seq).rglob("*-final.docx"))
    assert len(finals) == 1
    assert FINAL_SENTENCE in docx_text(finals[0])
    assert workspace.is_dir()


def test_missing_question_and_unreadable_draft_are_refused(workspace: Path) -> None:
    """The two refusal paths speak the door's sentence and write no Word file."""
    shell = FakeShell()
    seq = open_sequence(shell)
    missing = missing_question(shell, seq)
    assert missing.get("ok") is False, missing
    assert missing.get("reason") == ASK_QUESTION
    assert shell.student_line(missing) == ASK_QUESTION
    assert not citation_list_path(seq).is_file()

    broken_shell = FakeShell()
    broken_seq = open_sequence(broken_shell)
    broken = unreadable_draft(broken_shell, broken_seq)
    assert broken.get("ok") is False, broken
    assert broken.get("reason") == UNREADABLE_DRAFT
    assert UNREADABLE_DRAFT in broken_shell.student_line(broken)
    assert not (output_dir(broken_seq) / f"{broken_seq}.docx").is_file()
    assert workspace.is_dir()
