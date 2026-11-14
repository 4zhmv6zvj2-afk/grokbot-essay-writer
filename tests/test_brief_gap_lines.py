"""Honest gap lines in the spoken Basics pass.

The brief says what it says. When the reader cannot find a format or a
question that its prose still shows, the spoken line says the read failed
rather than that the brief is silent. A mark scheme that lists percentage
weights without a band says so and names no band.

Ids: essay-brief-a1, essay-brief-a2, essay-brief-a3, essay-brief-a4,
essay-brief-b1, essay-brief-b2, essay-brief-b3, essay-brief-c3,
essay-brief-d1.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document
from helpers import open_sequence

from essay_writer.assignment_gate import (
    FORMAT_NAMED_ONE,
    FORMAT_UNREAD,
    NO_MARK_SCHEME,
    PERCENTAGE_WEIGHTS,
    QUESTION_NAMED_ONE,
    QUESTION_UNREAD,
    assignment_requirements,
    assignment_silence_gaps,
    percentage_weights_only,
    read_assignment,
)
from essay_writer.build_office import assignment_requirements as build_record
from essay_writer.cursor_office import assignment_requirements as cursor_record
from essay_writer.paths import essay_dir
from essay_writer.specialists import grok_bot
from essay_writer.specialists.grok_bot import basics_pass_lines
from essay_writer.stage_llm import brief_genre, stage_title
from essay_writer.stage_track import essay_stage

WALK = (
    "Module: International Supply Chain Management\n"
    "Module code: MOD1004AA\n"
    "Assessment: Individual report\n"
    "Word count: 2,000 words, plus or minus 10%.\n"
    "\n"
    "Evaluate how a named supply chain should integrate sustainability "
    "for competitive advantage.\n"
    "\n"
    "Referencing: Harvard.\n"
    "\n"
    "Mark scheme\n"
    "Research and evidence 30%\n"
    "Analysis and judgement 40%\n"
    "Presentation and referencing 30%\n"
)
MODULE_ONLY = "Module code: MOD3001AA\n"
LABELLED = "Genre: report\nQuestion: How do chokepoints constrain the corridor?\n"
LABELLED_PROSE = "Genre: report\nThis individual report asks you to evaluate the corridor.\n"
BANDED = (
    "Genre: report\n"
    "Question: How do chokepoints constrain the corridor?\n"
    "\n"
    "Mark scheme\n"
    "Distinction 70% and above for analysis and judgement.\n"
)
RANGED = (
    "Genre: report\n"
    "Question: How do chokepoints constrain the corridor?\n"
    "\n"
    "Mark scheme\n"
    "Analysis and judgement carries 60-70 of the mark.\n"
)
PLAIN = "Genre: report\nQuestion: How do chokepoints constrain the corridor?\n"


def _plant(module: str, brief: str) -> str:
    """Write the brief, open one sequence, and return its id."""
    folder = essay_dir(module)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(brief, encoding="utf-8")
    return open_sequence(module)


@pytest.mark.parametrize("case_id", [pytest.param("essay-brief-a1", id="essay-brief-a1")])
def test_essay_brief_a1_prose_brief_says_the_read_failed(case_id, workspace):
    """a1: A prose brief with a format word, a task verb, and a question mark.

    The walk names a module, an individual report, 2,000 words, Evaluate how,
    and Harvard. Neither line says the brief does not name one.
    """
    assert case_id == "essay-brief-a1"
    seq = _plant("MOD1004AA", WALK)
    _scores, format_line, question_line = basics_pass_lines(seq)
    assert format_line == FORMAT_UNREAD
    assert question_line == QUESTION_UNREAD
    assert format_line != FORMAT_NAMED_ONE
    assert question_line != QUESTION_NAMED_ONE
    record = read_assignment(seq)
    assert record["format"] is None
    assert record["question"] is None
    gaps = assignment_silence_gaps(seq)
    assert FORMAT_UNREAD in gaps
    assert QUESTION_UNREAD in gaps

    reply = essay_stage(seq, "1", "draft", "The corridor is the case here.")
    assert reply["ok"] is True, reply
    assert reply["basics_pass"] == [PERCENTAGE_WEIGHTS, FORMAT_UNREAD, QUESTION_UNREAD]
    assert reply["assignment_gaps"] == [FORMAT_UNREAD, QUESTION_UNREAD]
    assert FORMAT_NAMED_ONE not in reply["basics_pass"]
    assert QUESTION_NAMED_ONE not in reply["basics_pass"]


@pytest.mark.parametrize("case_id", [pytest.param("essay-brief-a2", id="essay-brief-a2")])
def test_essay_brief_a2_module_code_only_keeps_the_silent_sentence(case_id, workspace):
    """a2: A brief that is only a module code has none of those signals."""
    assert case_id == "essay-brief-a2"
    seq = _plant("MOD3001AA", MODULE_ONLY)
    _scores, format_line, question_line = basics_pass_lines(seq)
    assert format_line == FORMAT_NAMED_ONE
    assert question_line == QUESTION_NAMED_ONE
    gaps = assignment_silence_gaps(seq)
    assert gaps == [FORMAT_NAMED_ONE, QUESTION_NAMED_ONE, "Word band: the brief does not name one."]


@pytest.mark.parametrize("case_id", [pytest.param("essay-brief-a3", id="essay-brief-a3")])
def test_essay_brief_a3_labelled_fields_keep_their_reading(case_id, workspace):
    """a3: Genre, Format, Question, Task, assignment ask, and Title keep their values."""
    assert case_id == "essay-brief-a3"
    fixtures = {
        "MOD4001AA": (LABELLED, "report", "How do chokepoints constrain the corridor?"),
        "MOD4002AA": (LABELLED_PROSE, "report", None),
    }
    for module, (brief, format_value, question) in fixtures.items():
        seq = _plant(module, brief)
        _scores, format_line, question_line = basics_pass_lines(seq)
        assert format_line == f"Format: {format_value}."
        if question is None:
            assert question_line == QUESTION_UNREAD
        else:
            assert question_line == f"Question: {question}"
        assert format_line != FORMAT_UNREAD

    label_only = {
        "MOD4003AA": "Format: essay\nTask: Evaluate the firm's actions.\n",
        "MOD4004AA": "Title: Weekly notes\n",
        "MOD4005AA": "Assignment ask: Should the council publish the recycling figure?\n",
    }
    expected = {
        "MOD4003AA": ("Format: essay.", "Question: Evaluate the firm's actions."),
        "MOD4004AA": (FORMAT_NAMED_ONE, "Question: Weekly notes"),
        "MOD4005AA": (
            FORMAT_NAMED_ONE,
            "Question: Should the council publish the recycling figure?",
        ),
    }
    for module, brief in label_only.items():
        seq = _plant(module, brief)
        _scores, format_line, question_line = basics_pass_lines(seq)
        assert (format_line, question_line) == expected[module], module


@pytest.mark.parametrize("case_id", [pytest.param("essay-brief-a4", id="essay-brief-a4")])
def test_essay_brief_a4_a_labelled_format_keeps_the_read_format(case_id, workspace):
    """a4: A format set from a label is not called unread. The question line is independent."""
    assert case_id == "essay-brief-a4"
    seq = _plant("MOD5001AA", LABELLED_PROSE)
    record = read_assignment(seq)
    assert record["format"] == "report"
    assert record["question"] is None
    _scores, format_line, question_line = basics_pass_lines(seq)
    assert format_line == "Format: report."
    assert format_line != FORMAT_UNREAD
    assert question_line == QUESTION_UNREAD


@pytest.mark.parametrize("case_id", [pytest.param("essay-brief-b1", id="essay-brief-b1")])
def test_essay_brief_b1_percentage_weights_name_no_band(case_id, workspace):
    """b1: A Mark scheme block of percentages says so and invents no band."""
    assert case_id == "essay-brief-b1"
    seq = _plant("MOD1004AA", WALK)
    assert percentage_weights_only(seq) is True
    scores, _format_line, _question_line = basics_pass_lines(seq)
    assert scores == PERCENTAGE_WEIGHTS
    assert scores != NO_MARK_SCHEME
    record = read_assignment(seq)
    assert record["highest_band"] is None
    assert record["mark_scheme"] is False

    reply = essay_stage(seq, "1", "draft", "The corridor is the case here.")
    assert reply["basics_pass"][0] == PERCENTAGE_WEIGHTS
    assert NO_MARK_SCHEME not in "\n".join(reply["basics_pass"])
    folder = essay_dir("MOD1004AA")
    written = sorted(path.name for path in folder.rglob("*") if path.is_file())
    assert "brief-meta.json" not in written
    assert not any(name.endswith(".docx") for name in written)


@pytest.mark.parametrize("case_id", [pytest.param("essay-brief-b2", id="essay-brief-b2")])
def test_essay_brief_b2_a_brief_with_no_scheme_keeps_the_no_scheme_line(case_id, workspace):
    """b2: With no mark scheme at all, the no-scheme sentence stays."""
    assert case_id == "essay-brief-b2"
    seq = _plant("MOD6001AA", PLAIN)
    assert percentage_weights_only(seq) is False
    scores, format_line, question_line = basics_pass_lines(seq)
    assert scores == NO_MARK_SCHEME
    assert format_line == "Format: report."
    assert question_line == "Question: How do chokepoints constrain the corridor?"


@pytest.mark.parametrize("case_id", [pytest.param("essay-brief-b3", id="essay-brief-b3")])
def test_essay_brief_b3_a_named_band_or_range_keeps_todays_reading(case_id, workspace):
    """b3: A named band or a numeric range keeps today's scores line."""
    assert case_id == "essay-brief-b3"
    cases = {
        "MOD7001AA": (BANDED, "Distinction"),
        "MOD7002AA": (RANGED, "60-70"),
    }
    for module, (brief, band) in cases.items():
        seq = _plant(module, brief)
        record = read_assignment(seq)
        assert record["highest_band"] == band, module
        assert record["mark_scheme"] is True
        assert percentage_weights_only(seq) is False
        scores = basics_pass_lines(seq)[0]
        assert scores.startswith("The mark scheme scores ")
        assert PERCENTAGE_WEIGHTS not in scores


@pytest.mark.parametrize("case_id", [pytest.param("essay-brief-c3", id="essay-brief-c3")])
def test_essay_brief_c3_the_chat_may_ask_and_claims_no_memory(case_id, workspace):
    """c3: The chat may ask. It does not claim the answer will be remembered."""
    assert case_id == "essay-brief-c3"
    seq = _plant("MOD1004AA", WALK)
    lines = list(basics_pass_lines(seq))
    ask = "Which format does the brief want: an essay or a report?"
    reply = essay_stage(seq, "1", "draft", "\n".join(lines) + "\n" + ask)
    assert reply["ok"] is True, reply
    assert reply["stored"] is False
    spoken = "\n".join(str(value) for value in reply.values() if isinstance(value, str))
    spoken += "\n".join(lines) + "\n" + ask
    folded = spoken.casefold()
    for claim in (
        "will be remembered",
        "remember this",
        "remembers your answer",
        "keep this answer",
        "stored answer",
        "saved answer",
    ):
        assert claim not in folded, claim
    assert ask in spoken


@pytest.mark.parametrize("case_id", [pytest.param("essay-brief-c1", id="essay-brief-c1")])
def test_essay_brief_c1_genre_selection_is_unchanged(case_id, workspace):
    """c1: Genre selection stays. The walk keeps no brief genre and today's stage 2 title."""
    assert case_id == "essay-brief-c1"
    seq = _plant("MOD1004AA", WALK)
    assert brief_genre(seq) is None
    assert stage_title("2", brief_genre(seq)) == (
        "Essay: Establish a thesis. Report: Establish purpose and scope"
    )
    folder = essay_dir("MOD1004AA")
    assert not (folder / "brief-meta.json").exists()
    for name in folder.rglob("*"):
        assert name.name not in {"formatAnswer", "questionAnswer"}
    shared = assignment_requirements(seq)
    assert shared == build_record(seq)
    assert shared == cursor_record(seq)
    assert basics_pass_lines(seq) == (
        PERCENTAGE_WEIGHTS,
        FORMAT_UNREAD,
        QUESTION_UNREAD,
    )


@pytest.mark.parametrize("case_id", [pytest.param("essay-brief-c2", id="essay-brief-c2")])
def test_essay_brief_c2_brief_bytes_are_not_rewritten(case_id, workspace):
    """c2: brief.md, brief.txt, and brief.docx bytes stay, and the cold case still says so."""
    assert case_id == "essay-brief-c2"
    folder = essay_dir("MOD9001AA")
    folder.mkdir(parents=True, exist_ok=True)
    before: dict[str, bytes] = {}
    for name, brief in (("brief.md", WALK), ("brief.txt", WALK)):
        path = folder / name
        path.write_text(brief, encoding="utf-8")
        before[name] = path.read_bytes()
    word = folder / "brief.docx"
    document = Document()
    document.add_paragraph(WALK)
    document.save(str(word))
    before["brief.docx"] = word.read_bytes()

    seq = open_sequence("MOD9001AA")
    reply = essay_stage(seq, "1", "draft", "The corridor is the case here.")
    assert reply["ok"] is True, reply
    for name, value in before.items():
        assert (folder / name).read_bytes() == value, name
    paragraphs = "\n".join(item.text for item in Document(str(word)).paragraphs)
    assert "Genre:" not in paragraphs
    assert "Question:" not in paragraphs
    for name in ("brief.md", "brief.txt"):
        text = (folder / name).read_text(encoding="utf-8")
        assert "Genre:" not in text
        assert "Question:" not in text
        assert "Question: I could not read" not in text

    cold = Path(__file__).with_name("test_cold_e2e.py").read_text(encoding="utf-8")
    assert "The brief file is not rewritten" in cold
    assert "path.read_bytes() == before" in cold
    assert '"Question:" not in path.read_text' in cold


@pytest.mark.parametrize("case_id", [pytest.param("essay-brief-d1", id="essay-brief-d1")])
def test_essay_brief_d1_a_failed_update_leaves_the_brief_bytes(case_id, workspace, monkeypatch):
    """d1: Spoken lines that cannot be shown do not guess a format, question, or band."""
    assert case_id == "essay-brief-d1"
    seq = _plant("MOD8001AA", WALK)
    folder = essay_dir("MOD8001AA")
    brief = folder / "brief.md"
    before = brief.read_bytes()
    written_before = sorted(str(path.relative_to(folder)) for path in folder.rglob("*"))

    def unavailable(_essay_id: str):
        raise OSError("the spoken lines are unavailable")

    monkeypatch.setattr(grok_bot, "basics_pass_lines", unavailable)
    with pytest.raises(OSError, match="spoken lines are unavailable"):
        essay_stage(seq, "1", "draft", "The corridor is the case here.")
    monkeypatch.undo()

    assert brief.read_bytes() == before
    assert brief.read_text(encoding="utf-8") == WALK
    record = read_assignment(seq)
    assert record["format"] is None
    assert record["question"] is None
    assert record["highest_band"] is None
    written_after = sorted(str(path.relative_to(folder)) for path in folder.rglob("*"))
    assert written_after == written_before
    assert not (folder / "brief-meta.json").exists()
    for path in folder.rglob("*.json"):
        assert "the brief lists percentage weights" not in path.read_text(encoding="utf-8")

    torn = _plant("MOD8002AA", WALK)
    other = essay_dir("MOD8002AA")
    other_brief = other / "brief.md"
    other_before = other_brief.read_bytes()
    lines = list(basics_pass_lines(torn))
    assert lines[0] == PERCENTAGE_WEIGHTS
    assert lines[1] == FORMAT_UNREAD
    assert lines[2] == QUESTION_UNREAD
    from essay_writer import stage_state

    shared = assignment_requirements(seq)
    assert shared == build_record(seq)
    assert shared == cursor_record(seq)
    real = stage_state._atomic

    def tearing(path, value):
        if Path(path).name == "stage.json":
            raise RuntimeError("torn before pointer")
        real(path, value)

    monkeypatch.setattr(stage_state, "_atomic", tearing)
    with pytest.raises(RuntimeError, match="torn before pointer"):
        essay_stage(
            torn,
            "1",
            "draft",
            "\n".join(lines) + "\nThe corridor is the case.",
        )
    monkeypatch.setattr(stage_state, "_atomic", real)

    assert other_brief.read_bytes() == other_before
    assert other_brief.read_text(encoding="utf-8") == WALK
    partial = read_assignment(torn)
    assert partial["format"] is None
    assert partial["question"] is None
    assert partial["highest_band"] is None
    assert not (other / "brief-meta.json").exists()
    for path in other.rglob("*.json"):
        assert "70-80" not in path.read_text(encoding="utf-8")
