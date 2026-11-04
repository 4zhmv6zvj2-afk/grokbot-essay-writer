"""Stage 9 refuses a pass when the opened Word misses a parsed engagement ask.

AC1: a word band already parsed from the marking document.
AC2: cover fields already parsed from the marking table.
AC3: diary headings already parsed from the diary brief.
AC4: opened Word without a literal top-band string still passes assignment_gate when
     the gate record already carries highest_band (submit_pass path).
An ask the documents did not record is not added.
Cursor and Grok Build use the same opened_word_gate.
"""

import inspect

from docx import Document
from helpers import open_sequence

from essay_writer.assignment_gate import assignment_gate, read_assignment
from essay_writer.build_office import opened_word_gate as build_gate
from essay_writer.cursor_office import opened_word_gate as cursor_gate
from essay_writer.diary import named_entries, title_page_spec
from essay_writer.paths import essay_dir, work_dir
from essay_writer.review import essay_review
from essay_writer.specialists.eqr import REVIEW_PROMPT, opened_word_gate
from essay_writer.specialists.writer import document_word_band
from essay_writer.state import load_state
from essay_writer.textutil import count_words

REPORT = "This is a report. How do chokepoints constrain the corridor?"
DIARY_BODY = (
    "This is a reflective diary. Understand the practice by reflecting on your own decisions. "
    "The entries name one decision and critically analyse it with theory and evidence."
)
HEADINGS = ("Quay watch", "Tide log", "Crane turn", "Gate count")
ASK_SENTENCE = (
    "Stage 9 refuses a pass when the opened Word file misses a word band, "
    "a cover field, or a diary heading already recorded from the brief, "
    "the marking table, or the diary."
)


def _brief(module: str, text: str) -> None:
    folder = essay_dir(module)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(text, encoding="utf-8")


def _scheme(module: str, text: str) -> None:
    folder = essay_dir(module)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "mark-scheme.md").write_text(text, encoding="utf-8")


def _docx(seq: str, lines: list[str]) -> None:
    path = work_dir(seq) / "output" / f"{seq}.docx"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    document.save(str(path))


def _joined(lines: list[str]) -> str:
    return "\n".join(lines)


def _same_gate(seq: str, text: str) -> dict:
    got = opened_word_gate(seq, text)
    assert cursor_gate(seq, text) == build_gate(seq, text) == got
    return got


def _inside_band(sentence: str, target: int) -> str:
    have = count_words(sentence, exclude_citations=False)
    extra = target - have
    assert extra > 0
    return sentence + " " + " ".join(["flows"] * extra)


def test_ac1_stage9_refuses_missed_word_band(workspace):
    """AC1. A parsed word band outside the opened Word refuses the stage 9 pass."""
    module = "MOD1011AA"
    _brief(
        module,
        "Genre: report\nQuestion: How do chokepoints constrain the corridor?\n",
    )
    _scheme(module, "Word count: 800 words.\n")
    seq = open_sequence(module)
    band = document_word_band(seq)
    assert band["min"] == 720
    assert band["max"] == 880
    assert read_assignment(seq)["highest_band"] is None

    _docx(seq, [REPORT])
    refused = essay_review(seq, "9", "PASS", "draft")
    assert refused["ok"] is False
    assert refused["stored"] is not True
    assert refused["refused"] == "engagement"
    assert refused["engagement"]["word_band"]["min"] == 720
    assert refused["engagement"]["word_band"]["max"] == 880
    assert refused["engagement"]["word_band"]["counted"] < 720
    assert "cover_fields" not in refused["engagement"]
    assert "diary_headings" not in refused["engagement"]
    assert "word band" in refused["reason"]
    assert "eqr" not in load_state(seq)
    gate = _same_gate(seq, REPORT)
    assert gate["engagement"] == refused["engagement"]
    assert "opened_word_gate as _gate" in inspect.getsource(build_gate)
    assert "opened_word_gate as _gate" in inspect.getsource(cursor_gate)
    assert ASK_SENTENCE in REVIEW_PROMPT

    held = _inside_band(REPORT, 800)
    assert count_words(held, exclude_citations=False) == 800
    _docx(seq, [held, "(Smith, 2020)."])
    drafted = essay_review(seq, "9", "PASS", "draft")
    assert drafted["ok"] is True, drafted
    assert opened_word_gate(seq, held) is None

    essay_dir(module).joinpath("mark-scheme.md").unlink()
    assert document_word_band(seq) == {}
    _docx(seq, [REPORT, "(Smith, 2020)."])
    quiet = essay_review(seq, "9", "PASS", "draft")
    assert quiet["ok"] is True, quiet
    assert opened_word_gate(seq, REPORT) is None


def test_ac2_stage9_refuses_missed_cover_fields(workspace):
    """AC2. Cover fields parsed from the marking table refuse a pass when the Word omits them."""
    module = "MOD1004AA"
    table = """
Genre: report
Question: How do chokepoints constrain the corridor?

# Marking criteria/feedback form

| Criterion | 0-39 | 70+ |
| --- | --- | --- |
| Title page | thin | registration number and student address |
"""
    _brief(module, table)
    seq = open_sequence(module)
    spec = title_page_spec(table)
    seen = read_assignment(seq)["title_page"]
    assert seen["fields"] == spec["fields"] == ["registration"]
    assert seen["labels"] == spec["labels"] == ["Student address"]
    # The table's top mark is 70+ on the gate record. Student Word must not carry that tip.
    assert read_assignment(seq)["highest_band"] == "70+"
    body = REPORT

    _docx(seq, [body])
    refused = essay_review(seq, "9", "PASS", "draft")
    assert refused["ok"] is False
    assert refused["stored"] is not True
    assert refused["refused"] == "engagement"
    assert refused["engagement"]["cover_fields"] == ["Registration number", "Student address"]
    assert "word_band" not in refused["engagement"]
    assert "diary_headings" not in refused["engagement"]
    assert "eqr" not in load_state(seq)
    assert _same_gate(seq, body)["engagement"] == refused["engagement"]

    shown = [
        body,
        "Registration number: 445566",
        "Student address: 12 Quay Road",
        "(Smith, 2020).",
    ]
    _docx(seq, shown)
    drafted = essay_review(seq, "9", "PASS", "draft")
    assert drafted["ok"] is True, drafted
    assert opened_word_gate(seq, _joined(shown)) is None

    _brief(
        module,
        "Genre: report\nQuestion: How do chokepoints constrain the corridor?\n",
    )
    # The first read copies the brief table to marking-table.md. That copy is not a new ask.
    copied = essay_dir(module) / "marking-table.md"
    if copied.is_file():
        copied.unlink()
    assert read_assignment(seq)["title_page"]["fields"] == []
    assert read_assignment(seq)["title_page"]["labels"] == []
    _docx(seq, [REPORT, "(Smith, 2020)."])
    quiet = essay_review(seq, "9", "PASS", "draft")
    assert quiet["ok"] is True, quiet
    assert opened_word_gate(seq, REPORT) is None


def test_ac4_opened_word_without_band_literal_unlocks_with_gate_metadata(workspace):
    """AC4. EQR does not require 70+ in student Word when the gate record has the top band."""
    module = "MOD1004AA"
    table = """
Genre: report
Question: How do chokepoints constrain the corridor?

# Marking criteria/feedback form

| Criterion | 0-39 | 70+ |
| --- | --- | --- |
| Title page | thin | registration number and student address |
"""
    _brief(module, table)
    seq = open_sequence(module)
    assert read_assignment(seq)["highest_band"] == "70+"
    assert "70+" not in REPORT
    assert assignment_gate(seq, REPORT, seat="eqr")["ok"] is True
    assert assignment_gate(seq, REPORT, seat="writer")["ok"] is False

    shown = [
        REPORT,
        "Registration number: 445566",
        "Student address: 12 Quay Road",
        "(Smith, 2020).",
    ]
    _docx(seq, shown)
    drafted = essay_review(seq, "9", "PASS", "draft")
    assert drafted["ok"] is True, drafted
    assert opened_word_gate(seq, _joined(shown)) is None
    assert "70+" not in _joined(shown)


def test_ac3_stage9_refuses_missed_diary_headings(workspace):
    """AC3. Diary headings the brief named refuse a pass when the Word omits them."""
    module = "QUA9001HK"
    named = """
Assignment title: Individual reflective diary

Aim: Understand the practice by reflecting on your own decisions.

Assignment task: Write four entries. Each entry names one decision and critically analyses it with theory and evidence.

Workshop topics
1. Quay watch
2. Tide log
3. Crane turn
4. Gate count
"""
    _brief(module, named)
    seq = open_sequence(module)
    assert named_entries(named) == list(HEADINGS)
    assert read_assignment(seq)["named_entries"] == list(HEADINGS)
    assert read_assignment(seq)["writing_type"] == "diary"

    _docx(seq, [DIARY_BODY])
    refused = essay_review(seq, "9", "PASS", "draft")
    assert refused["ok"] is False
    assert refused["stored"] is not True
    assert refused["refused"] == "engagement"
    assert refused["engagement"]["diary_headings"] == list(HEADINGS)
    assert "word_band" not in refused["engagement"]
    assert "cover_fields" not in refused["engagement"]
    assert "eqr" not in load_state(seq)
    assert _same_gate(seq, DIARY_BODY)["engagement"] == refused["engagement"]

    stage6 = essay_review(seq, "6", "PASS", "draft")
    assert stage6["ok"] is True, stage6
    assert stage6.get("refused") != "engagement"

    present = [
        DIARY_BODY,
        "Quay watch",
        "Tide log",
        "Crane turn",
        "Gate count",
        "(Smith, 2020).",
    ]
    _docx(seq, present)
    drafted = essay_review(seq, "9", "PASS", "draft")
    assert drafted["ok"] is True, drafted
    assert opened_word_gate(seq, _joined(present)) is None

    _brief(
        module,
        """
Assignment title: Individual reflective diary

Aim: Understand the practice by reflecting on your own decisions.

Assignment task: Write four entries. Each entry names one decision and critically analyses it with theory and evidence.
""",
    )
    assert read_assignment(seq)["named_entries"] == []
    _docx(seq, [DIARY_BODY, "(Smith, 2020)."])
    quiet = essay_review(seq, "9", "PASS", "draft")
    assert quiet["ok"] is True, quiet
    assert opened_word_gate(seq, DIARY_BODY) is None
