"""EQR marks the top-band table rows for argument, evidence, and critical thinking.

AC1. The mark is the top-band cell of those rows. A lower cell does not count.
Format and citation rows are not marked. A missing row is not invented.
AC2. A stage 9 pass is stored only when the opened file meets those rows.
Citations still have to be on that file before the pass unlocks it.
AC3. Stage 6 answers the assignment question only. It does not mark these rows.
AC4. The writer cannot clear the review. Front office stage 9 does not mark again.
AC5. Cursor and Grok Build call the same mark.
Build covered: one mark_top_band_rows path.
"""

import inspect
import json

from docx import Document
from helpers import ESSAY, TOPIC, open_sequence, pack, source, write_upload

from essay_writer.build_office import stage_launch
from essay_writer.build_office import top_band_mark as build_mark
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.cursor_office import top_band_mark as cursor_mark
from essay_writer.paths import essay_dir, work_dir
from essay_writer.research import essay_research_summary
from essay_writer.review import PERSON_BLOCK, essay_review, writer_clears_left
from essay_writer.specialists.eqr import (
    HIGHEST_BAND,
    REVIEW_PROMPT,
    answers_assignment_question,
    mark_top_band_rows,
    read_top_band_rows,
    stage6_scope,
    submit_pass_unlocked,
)
from essay_writer.specialists.grok_bot import front_office_stage9
from essay_writer.state import load_state, save_state
from essay_writer.student_voice import student_surface_hits
from essay_writer.validate import essay_pack_validate
from essay_writer.word import essay_pack_render_word

QUESTION = "How do chokepoints constrain the corridor?"
CONSTITUTION = (
    "This is a report. How do chokepoints constrain the corridor? Band 70-100. "
    "It sustains an original thesis with specific gathered sources and judges the alternatives."
)
LOWER = (
    "This is a report. How do chokepoints constrain the corridor? 70-100. "
    "This lists nearby topics and names some sources and describes the events."
)
TOP = (
    "This is a report. How do chokepoints constrain the corridor? Band 70-100. "
    "This sustains an original thesis with specific gathered sources and judges the alternatives."
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
ROW_SENTENCE = (
    "Stage 9 marks a mark scheme table row for argument, evidence, or critical thinking "
    "at the top band. It does not mark format. It does not mark citations. "
    "Stage 6 does not mark those rows."
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


def _scheme(text: str) -> None:
    folder = essay_dir(ESSAY)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "mark-scheme.md").write_text(text, encoding="utf-8")


def test_top_band_cells_are_the_mark_and_other_rows_are_not(workspace):
    """AC1. Top cell only. Format, citations, prose, and a missing row stay out."""
    seq = _ready(workspace)
    read = read_top_band_rows(TABLE)
    assert [row["row"] for row in read["rows"]] == ["argument", "evidence", "critical thinking"]
    assert [row["descriptor"] for row in read["rows"]] == [
        "sustains an original thesis",
        "specific gathered sources",
        "judges the alternatives",
    ]
    assert {row["band"] for row in read["rows"]} == {"70-100"}
    assert read["skipped"] == ["format", "citations"]
    for lower in ("lists nearby topics", "names some sources", "describes the events"):
        assert lower not in [row["descriptor"] for row in read["rows"]]
    for writer_cell in ("exact margins", "exact citation lines"):
        assert writer_cell not in [row["descriptor"] for row in read["rows"]]

    low = mark_top_band_rows(seq, LOWER)
    assert low["marked"] is True
    assert low["top_band"] is False
    assert low["missed"] == ["argument", "evidence", "critical thinking"]
    assert low["format"] is False
    assert low["citations"] is False
    assert low["skipped"] == ["format", "citations"]
    assert all(row["met"] is False for row in low["rows"])

    high = mark_top_band_rows(seq, TOP)
    assert high["top_band"] is True
    assert high["missed"] == []
    assert all(row["met"] is True for row in high["rows"])
    one = mark_top_band_rows(
        seq,
        "This sustains an original thesis and judges the alternatives.",
    )
    assert one["missed"] == ["evidence"]

    partial = """
| Criterion | 50-59 | 70-100 |
| Argument | lists nearby topics | sustains an original thesis |
| Use of evidence | names some sources | specific gathered sources |
| Format | loose layout | exact margins |
"""
    assert [row["row"] for row in read_top_band_rows(partial)["rows"]] == ["argument", "evidence"]
    assert "critical thinking" not in json.dumps(read_top_band_rows(partial))

    owned = """
| Criterion | 70-100 |
| Evidence of correct referencing | exact citation lines |
| Presentation of the argument | exact margins |
"""
    owned_rows = read_top_band_rows(owned)
    assert owned_rows["rows"] == []
    assert owned_rows["skipped"] == ["format", "citations"]

    prose = "High Distinction (80-100): evidence\nPass (50-59): adequate\n"
    assert read_top_band_rows(prose) == {"rows": [], "skipped": []}
    clarity = """
| Criterion | 0-39 | 70+ |
| --- | --- | --- |
| Clarity of the decisions | thin | exact and evidenced |
"""
    assert read_top_band_rows(clarity)["rows"] == []
    noband = """
| Criterion | Note |
| Argument | sustains an original thesis |
"""
    assert read_top_band_rows(noband)["rows"] == []
    left = """
| Criterion | 70-100 | 40-59 |
| Argument | sustains an original thesis | lists nearby topics |
"""
    assert read_top_band_rows(left)["rows"][0]["descriptor"] == "sustains an original thesis"
    tied = """
| Criterion | 80-100 | 70–100 |
| Argument | first wording | second wording |
"""
    assert read_top_band_rows(tied)["rows"][0]["band"] == "70–100"
    assert read_top_band_rows(tied)["rows"][0]["descriptor"] == "second wording"

    _scheme(prose)
    quiet = mark_top_band_rows(seq, TOP)
    assert quiet["marked"] is False
    assert quiet["rows"] == []
    assert quiet["top_band"] is True
    assert quiet["format"] is False
    assert quiet["citations"] is False


def test_stage9_pass_needs_the_top_band_and_citations_still_unlock(workspace, monkeypatch):
    """AC2. The opened file is marked. A lower cell does not store. Citations still gate the file."""
    seq = _ready(workspace)
    absent = essay_review(seq, "9", "PASS", "draft", constitution=CONSTITUTION)
    assert absent["ok"] is False
    assert absent["stored"] is not True
    assert "opened Word file" in absent["reason"]
    assert "eqr" not in load_state(seq)
    path = _submit(seq)
    _docx(path, [LOWER])
    before = path.read_bytes()
    refused = essay_review(seq, "9", "PASS", "draft", constitution=CONSTITUTION)
    assert refused["ok"] is False
    assert refused["stored"] is not True
    assert refused["reason"] == (
        "The review marks the top band for argument, evidence, critical thinking. "
        "Nothing was recorded."
    )
    assert "format" not in refused["reason"].casefold()
    assert "citation" not in refused["reason"].casefold()
    assert refused["top_band"]["missed"] == ["argument", "evidence", "critical thinking"]
    assert path.read_bytes() == before
    assert "eqr" not in load_state(seq)

    _docx(path, [TOP])
    refused_cites = essay_review(seq, "9", "PASS", "draft", constitution=CONSTITUTION)
    assert refused_cites["ok"] is False
    assert refused_cites["reason"] == "The opened Word file has no citations. Nothing was recorded."
    assert refused_cites.get("stored") is not True
    held = submit_pass_unlocked(seq)
    assert held["unlocked"] is False
    assert held["reason"] == "missing"
    word_pack = pack()
    word_pack["assessment"] = "Individual report. Band 70-100."
    essay_pack_validate(seq, word_pack, "draft")
    essay_pack_validate(seq, word_pack, "confirm")
    preview = essay_pack_render_word(seq, word_pack, "draft", stage="9")
    assert preview["wrote"] is False
    assert preview["submit_pass"] == "missing"
    blocked = essay_pack_render_word(seq, word_pack, "confirm", stage="9")
    assert blocked["ok"] is False
    assert blocked["wrote"] is False
    assert blocked["refused"] == "eqr"
    assert blocked["submit_pass"] == "missing"

    _docx(path, [TOP + " (Smith, 2020)."])
    drafted = essay_review(seq, "9", "PASS", "draft", constitution=CONSTITUTION)
    assert drafted["ok"] is True, drafted
    stored = essay_review(seq, "9", "PASS", "confirm", constitution=CONSTITUTION)
    assert stored["stored"] is True, stored
    mark = stored["top_band"]
    assert mark["top_band"] is True
    assert mark["format"] is False
    assert mark["citations"] is False
    assert [row["row"] for row in mark["rows"]] == ["argument", "evidence", "critical thinking"]
    assert "Top band" in stored["findings"]
    assert "sustains an original thesis. Met." in stored["findings"]
    assert "specific gathered sources. Met." in stored["findings"]
    assert "judges the alternatives. Met." in stored["findings"]
    assert "lists nearby topics" not in stored["findings"]
    assert "exact margins" not in stored["findings"]
    assert "exact citation lines" not in stored["findings"]
    assert "Not met." not in stored["findings"]
    assert submit_pass_unlocked(seq)["unlocked"] is True

    _docx(path, [TOP + " (Smith, 2020). Revised."])
    stale = submit_pass_unlocked(seq)
    assert stale["unlocked"] is False
    assert stale["reason"] == "stale"

    def _boom(*_args, **_kwargs):
        raise AssertionError("top band was marked again")

    real_mark = mark_top_band_rows
    monkeypatch.setattr("essay_writer.specialists.eqr.mark_top_band_rows", _boom)
    assert submit_pass_unlocked(seq)["reason"] == "stale"
    stop = front_office_stage9(seq)
    assert stop["stopped"] is True
    assert stop["remarked"] is False
    assert stop["reason"] == "stale"
    monkeypatch.setattr("essay_writer.specialists.eqr.mark_top_band_rows", real_mark)

    _docx(path, [TOP + " (Smith, 2020)."])
    stored_again = essay_review(seq, "9", "PASS", "draft", constitution=CONSTITUTION)
    assert stored_again["ok"] is True, stored_again
    saved = essay_review(seq, "9", "PASS", "confirm", constitution=CONSTITUTION)
    assert saved["stored"] is True, saved
    fresh = submit_pass_unlocked(seq)
    assert fresh["unlocked"] is True
    assert fresh["reason"] == "pass"
    written = essay_pack_render_word(seq, word_pack, "confirm", stage="9")
    assert written["wrote"] is True, written

    state = load_state(seq)
    state["eqr"]["9"]["submit_sha256"] = ""
    state["eqr"]["9"]["word_opened"] = False
    save_state(seq, state)
    monkeypatch.setattr("essay_writer.specialists.eqr.mark_top_band_rows", _boom)
    false_pass = submit_pass_unlocked(seq)
    assert false_pass["unlocked"] is False
    assert false_pass["reason"] == "false"
    assert "mark_top_band_rows" not in inspect.getsource(submit_pass_unlocked)
    assert "mark_top_band_rows" not in inspect.getsource(front_office_stage9)


def test_stage6_answers_the_question_and_does_not_mark_rows(workspace):
    """AC3. Stage 6 stays on the assignment question. The file is not rewritten."""
    seq = _ready(workspace)
    assert stage6_scope() == {
        "judges": "answers-the-question",
        "format": False,
        "freeflow": False,
        "gap_fill": False,
    }
    assert "format" not in inspect.getsource(answers_assignment_question).casefold()
    assert "mark_top_band_rows" not in inspect.getsource(answers_assignment_question)
    for row in ("argument", "evidence", "critical thinking"):
        assert row not in HIGHEST_BAND.casefold()
    assert "Stage 6 answers only whether the draft answers the assignment question." in REVIEW_PROMPT
    assert "Stage 6 does not mark those rows." in REVIEW_PROMPT
    assert student_surface_hits(REVIEW_PROMPT) == []

    path = _submit(seq)
    _docx(path, [QUESTION + " " + LOWER])
    before = path.read_bytes()
    drafted = essay_review(seq, "6", "PASS", "draft", constitution=CONSTITUTION)
    assert drafted["ok"] is True, drafted
    assert "top_band" not in drafted
    stored = essay_review(seq, "6", "PASS", "confirm", constitution=CONSTITUTION)
    assert stored["stored"] is True, stored
    assert "top_band" not in stored
    assert "top_band" not in load_state(seq)["eqr"]["6"]
    assert "Top band" not in stored["findings"]
    assert path.read_bytes() == before
    assert submit_pass_unlocked(seq)["unlocked"] is False


def test_writer_and_front_office_do_not_mark(workspace, monkeypatch):
    """AC4. The writer cannot clear a mark, and stage 9 does not mark again."""
    assert writer_clears_left() == 0
    seq = _ready(workspace)
    path = _submit(seq)
    _docx(path, [TOP + " (Smith, 2020)."])
    before = json.dumps(load_state(seq).get("eqr"))
    refused = essay_review(seq, "9", "PASS", "confirm", seat="writer", constitution=CONSTITUTION)
    assert refused["ok"] is False
    assert refused["refused"] == "seat"
    assert PERSON_BLOCK in refused["reason"]
    assert "top_band" not in refused
    assert json.dumps(load_state(seq).get("eqr")) == before

    drafted = essay_review(seq, "9", "PASS", "draft", constitution=CONSTITUTION)
    assert drafted["ok"] is True, drafted
    essay_review(seq, "9", "PASS", "confirm", constitution=CONSTITUTION)
    state = load_state(seq)
    state["eqr"]["9"]["submit_sha256"] = "0" * 64
    save_state(seq, state)
    seen = json.dumps(load_state(seq).get("eqr"), sort_keys=True)

    def _boom(*_args, **_kwargs):
        raise AssertionError("top band was marked again")

    monkeypatch.setattr("essay_writer.specialists.eqr.mark_top_band_rows", _boom)
    monkeypatch.setattr("essay_writer.review.essay_review", _boom)
    stop = front_office_stage9(seq)
    assert stop["remarked"] is False
    assert stop["reason"] == "stale"
    assert json.dumps(load_state(seq).get("eqr"), sort_keys=True) == seen


def test_cursor_and_grok_build_share_the_top_band_mark(workspace):
    """AC5. Build covered. One mark function, and the same review sentence."""
    seq = _ready(workspace)
    text = TOP
    assert cursor_mark(seq, text) == build_mark(seq, text) == mark_top_band_rows(seq, text)
    assert "mark_top_band_rows" in cursor_mark.__code__.co_names
    assert "mark_top_band_rows" in build_mark.__code__.co_names
    cursor = cursor_stage_launch("eqr")
    build = stage_launch("eqr")
    assert cursor["settings"]["prompt_overlay"] == build["settings"]["prompt_overlay"]
    assert cursor["settings"]["rules"] == build["settings"]["rules"]
    assert ROW_SENTENCE in cursor["settings"]["rules"]
    assert "mark_top_band_rows" in inspect.getsource(essay_review)
    review_source = inspect.getsource(essay_review)
    assert review_source.index('if verdict == "PASS" and stage == "9":') < review_source.index(
        'if verdict == "PASS" and stage == "6":'
    )
    top_band_block = review_source.split("top_band = mark_top_band_rows", 1)[0]
    assert "if verdict == \"PASS\" and stage == \"9\":" in top_band_block
    stage6 = review_source.split('if verdict == "PASS" and stage == "6":', 1)[1].split(
        "top_band = None", 1
    )[0]
    assert "mark_top_band_rows" in review_source
    assert "mark_top_band_rows" not in stage6
