"""Cut 2 leftovers. Opened Word requirement list for stage 9; stage 6 answers-only.

AC1: Stage 9 pass only when the opened Word shows the asks; no file = no pass.
AC2: Top-band rows still mark; format and citation skip; no invent.
AC3: Stage 6 question-only.
AC4: Writer cannot clear; front office stage 9 does not remark; unlock unchanged.
AC5: Cursor and Grok Build share opened_word_gate (shared function).
Build covered: shared function + thin wrappers.
"""

import inspect
import json

from docx import Document
from helpers import ESSAY, TOPIC, open_sequence, pack, source, write_upload

from essay_writer.build_office import opened_word_gate as build_gate
from essay_writer.build_office import stage_launch
from essay_writer.build_office import top_band_mark as build_mark
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.cursor_office import opened_word_gate as cursor_gate
from essay_writer.cursor_office import top_band_mark as cursor_mark
from essay_writer.paths import work_dir
from essay_writer.research import essay_research_summary
from essay_writer.review import PERSON_BLOCK, essay_review, writer_clears_left
from essay_writer.specialists.eqr import (
    REVIEW_PROMPT,
    mark_top_band_rows,
    opened_word_gate,
    read_top_band_rows,
    submit_pass_unlocked,
)
from essay_writer.specialists.grok_bot import front_office_stage9
from essay_writer.state import load_state, save_state
from essay_writer.validate import essay_pack_validate

QUESTION = "How do chokepoints constrain the corridor?"
CONSTITUTION = (
    "This is a report. How do chokepoints constrain the corridor? Band 70-100. "
    "It sustains an original thesis with specific gathered sources and judges the alternatives."
)
TOP = (
    "This is a report. How do chokepoints constrain the corridor? Band 70-100. "
    "It sustains an original thesis with specific gathered sources and judges the alternatives."
)
LOWER = (
    "This is a report. How do chokepoints constrain the corridor? 70-100. "
    "This lists nearby topics and names some sources and describes the events."
)
TABLE = """
| Criterion | 40-59 | 60-69 | 70-100 |
| --- | --- | --- | --- |
| Argument | lists nearby topics | states a claim | sustains an original thesis |
| Use of evidence | names some sources | uses several sources | specific gathered sources |
| Critical thinking | describes the events | explains the causes | judges the alternatives |
| Format | loose layout | tidy layout | exact margins |
| Citations | missing harvard | some harvard | exact citation lines |
"""
WORD_SENTENCE = (
    "Stage 9 checks the same requirement list on the opened Word file. "
    "The constitution is not that check."
)


def _ready(workspace) -> str:
    write_upload(workspace)
    folder = workspace / "Essay-writer" / ESSAY
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(
        "Genre: report\nQuestion: How do chokepoints constrain the corridor?\n",
        encoding="utf-8",
    )
    (folder / "mark-scheme.md").write_text(TABLE, encoding="utf-8")
    seq = open_sequence()
    essay_research_summary(seq, TOPIC, "draft", [source()])
    essay_research_summary(seq, TOPIC, "confirm", [source()])
    essay_pack_validate(seq, pack(), "draft")
    essay_pack_validate(seq, pack(), "confirm")
    return seq


def _docx(path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    document.save(str(path))


def _submit(seq: str):
    return work_dir(seq) / "output" / f"{seq}.docx"


def test_ac1_stage9_checks_opened_word_not_constitution(workspace):
    """AC1. The requirement list is read from the opened file. No file = no pass."""
    seq = _ready(workspace)
    path = _submit(seq)
    absent = essay_review(seq, "9", "PASS", "draft", constitution=CONSTITUTION)
    assert absent["ok"] is False
    assert absent["stored"] is not True
    assert "opened Word file" in absent["reason"]
    assert "eqr" not in load_state(seq)

    _docx(path, ["Pass."])
    constitution_only = essay_review(seq, "9", "PASS", "draft", constitution=CONSTITUTION)
    assert constitution_only["ok"] is False
    assert constitution_only["refused"] == "assignment-gate"
    assert constitution_only["stored"] is not True
    assert "eqr" not in load_state(seq)

    _docx(path, [TOP + " (Smith, 2020)."])
    drafted = essay_review(seq, "9", "PASS", "draft", constitution="Pass.")
    assert drafted["ok"] is True, drafted
    assert WORD_SENTENCE in REVIEW_PROMPT


def test_ac2_top_band_rows_still_mark_format_and_citations_skip(workspace):
    """AC2. Top-band rows still mark. Format and citation rows stay out."""
    seq = _ready(workspace)
    read = read_top_band_rows(TABLE)
    assert read["skipped"] == ["format", "citations"]
    path = _submit(seq)
    _docx(path, [LOWER])
    refused = essay_review(seq, "9", "PASS", "draft", constitution=CONSTITUTION)
    assert refused["ok"] is False
    assert refused.get("top_band", {}).get("missed") == ["argument", "evidence", "critical thinking"]
    assert "format" not in refused["reason"].casefold()
    assert "citation" not in refused["reason"].casefold()

    _docx(path, [TOP + " (Smith, 2020)."])
    drafted = essay_review(seq, "9", "PASS", "draft", constitution=CONSTITUTION)
    assert drafted["ok"] is True, drafted
    stored = essay_review(seq, "9", "PASS", "confirm", constitution=CONSTITUTION)
    assert stored["stored"] is True, stored
    assert stored["top_band"]["top_band"] is True
    assert cursor_mark(seq, TOP) == build_mark(seq, TOP) == mark_top_band_rows(seq, TOP)


def test_ac3_stage6_question_only_not_requirement_list(workspace):
    """AC3. Stage 6 does not run the opened-word requirement list."""
    seq = _ready(workspace)
    path = _submit(seq)
    _docx(path, ["Format: report. The margins are wide."])
    before = path.read_bytes()
    refused = essay_review(seq, "6", "PASS", "draft", constitution=CONSTITUTION)
    assert refused["ok"] is False
    assert "answers the assignment question" in refused["reason"]
    assert refused["refused"] != "assignment-gate"
    assert path.read_bytes() == before

    source = inspect.getsource(essay_review)
    stage6 = source.split('stage == "6"', 1)[1].split('stage == "9"', 1)[0]
    assert "opened_word_gate" not in stage6
    assert "answers_assignment_question" in stage6


def test_ac4_writer_fo_and_unlock_unchanged(workspace, monkeypatch):
    """AC4. Writer cannot clear. Front office does not remark. Unlock path unchanged."""
    assert writer_clears_left() == 0
    seq = _ready(workspace)
    path = _submit(seq)
    _docx(path, [TOP + " (Smith, 2020)."])
    before = json.dumps(load_state(seq).get("eqr"))
    refused = essay_review(seq, "9", "PASS", "confirm", seat="writer", constitution=CONSTITUTION)
    assert refused["ok"] is False
    assert refused["refused"] == "seat"
    assert PERSON_BLOCK in refused["reason"]
    assert json.dumps(load_state(seq).get("eqr")) == before

    essay_review(seq, "9", "PASS", "draft", constitution=CONSTITUTION)
    essay_review(seq, "9", "PASS", "confirm", constitution=CONSTITUTION)
    state = load_state(seq)
    state["eqr"]["9"]["submit_sha256"] = "0" * 64
    save_state(seq, state)
    seen = json.dumps(load_state(seq).get("eqr"), sort_keys=True)

    def _boom(*_args, **_kwargs):
        raise AssertionError("stage 9 marked again")

    monkeypatch.setattr("essay_writer.review.essay_review", _boom)
    stop = front_office_stage9(seq)
    assert stop["remarked"] is False
    assert stop["reason"] == "stale"
    assert json.dumps(load_state(seq).get("eqr"), sort_keys=True) == seen
    assert submit_pass_unlocked(seq)["reason"] == "stale"


def test_ac5_build_covered_shared_opened_word_gate(workspace):
    """AC5. Cursor and Grok Build call the same opened_word_gate."""
    seq = _ready(workspace)
    word = TOP
    assert cursor_gate(seq, word) == build_gate(seq, word) == opened_word_gate(seq, word)
    assert "opened_word_gate as _gate" in inspect.getsource(build_gate)
    assert "opened_word_gate as _gate" in inspect.getsource(cursor_gate)
    cursor = cursor_stage_launch("eqr")
    build = stage_launch("eqr")
    assert cursor["settings"]["rules"] == build["settings"]["rules"]
    assert WORD_SENTENCE in cursor["settings"]["rules"]
    review_source = inspect.getsource(essay_review)
    stage9 = review_source.split('if verdict == "PASS" and stage == "9":', 1)[1].split(
        'if verdict == "PASS" and stage == "6":', 1
    )[0]
    assert "opened_word_gate" in stage9
    assert "constitution" not in stage9
