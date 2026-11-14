"""Obvious cues fill an empty format or question.

A label still wins. A cue fills only a field the brief left empty. The brief
file is not rewritten, and the combined stage title stays when no Genre or
Format label is set.

Ids: essay-cues-a1, essay-cues-a2, essay-cues-a3, essay-cues-a4, essay-cues-a5,
essay-cues-a6, essay-cues-b1, essay-cues-b2, essay-cues-b3, essay-cues-b4,
essay-cues-c1, essay-cues-c2, essay-cues-d1.
"""

from __future__ import annotations

import ast
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
    percentage_weights_only,
    read_assignment,
)
from essay_writer.build_office import assignment_requirements as build_record
from essay_writer.cursor_office import assignment_requirements as cursor_record
from essay_writer.paths import essay_dir
from essay_writer.specialists import grok_bot
from essay_writer.specialists.grok_bot import basics_pass_lines
from essay_writer.specialists.writer import document_word_band
from essay_writer.stage_llm import brief_genre, stage_title
from essay_writer.stage_track import essay_stage
from essay_writer.textutil import word_band_from_brief_text

EVALUATE = (
    "Evaluate how a named supply chain should integrate sustainability for competitive advantage."
)
WALK = (
    "Module: International Supply Chain Management\n"
    "Module code: MOD1004AA\n"
    "Assessment: Individual report\n"
    "Word count: 2,000 words, plus or minus 10%.\n"
    "\n"
    f"{EVALUATE}\n"
    "\n"
    "Referencing: Harvard.\n"
    "\n"
    "Mark scheme\n"
    "Research and evidence 30%\n"
    "Analysis and judgement 40%\n"
    "Presentation and referencing 30%\n"
)
COMBINED_STAGE_TWO = "Essay: Establish a thesis. Report: Establish purpose and scope"
COMBINED_STAGE_THREE = "Essay: Write an essay plan. Report: Write a report plan"
MEMORY_CLAIMS = (
    "will be remembered",
    "remember this",
    "remembers your answer",
    "keep this answer",
    "stored answer",
    "saved answer",
)


def _plant(module: str, brief: str) -> str:
    """Write the brief, open one sequence, and return its id."""
    folder = essay_dir(module)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(brief, encoding="utf-8")
    return open_sequence(module)


def _lines(seq: str) -> tuple[str, str, str]:
    return basics_pass_lines(seq)


@pytest.mark.parametrize("case_id", [pytest.param("essay-cues-a1", id="essay-cues-a1")])
def test_essay_cues_a1_obvious_cues_fill_empty_fields(case_id, workspace):
    """a1: Individual report, reflective diary, essay, a task sentence, and a question."""
    assert case_id == "essay-cues-a1"
    seq = _plant("CUE1001AA", WALK)
    record = read_assignment(seq)
    assert record["format"] == "report"
    assert record["question"] == EVALUATE
    assert EVALUATE in record["question"]
    scores, format_line, question_line = _lines(seq)
    assert scores == PERCENTAGE_WEIGHTS
    assert format_line == "Format: report."
    assert question_line == f"Question: {EVALUATE}"

    diary = _plant(
        "CUE1002AA",
        "Assessment: reflective diary\nWhat changed in your own week on the ward?\n",
    )
    diary_record = read_assignment(diary)
    assert diary_record["format"] == "reflective diary"
    assert diary_record["question"] == "What changed in your own week on the ward?"

    essay = _plant(
        "CUE1003AA",
        "Write an essay on the corridor chokepoints.\nHow do chokepoints constrain the corridor?\n",
    )
    essay_record = read_assignment(essay)
    assert essay_record["format"] == "essay"
    assert essay_record["question"] == "How do chokepoints constrain the corridor?"

    task = _plant(
        "CUE1004AA",
        "Module code: CUE1004AA\nEvaluate how the firm should publish the figure.\n",
    )
    task_record = read_assignment(task)
    assert task_record["format"] is None
    assert task_record["question"] == "Evaluate how the firm should publish the figure."
    assert _lines(task)[1] == FORMAT_UNREAD


@pytest.mark.parametrize("case_id", [pytest.param("essay-cues-a2", id="essay-cues-a2")])
def test_essay_cues_a2_two_assignment_types_stay_unset(case_id, workspace):
    """a2: Two assignment types stay empty. An annual report is the topic, not a type."""
    assert case_id == "essay-cues-a2"
    both = _plant(
        "CUE2001AA",
        "This assignment is an essay or a report.\nStudents should evaluate sources in class.\n",
    )
    assert read_assignment(both)["format"] is None
    assert brief_genre(both) is None

    annual = "Write an essay on the annual report of one named firm.\n"
    mentioned = _plant("CUE2002AA", annual)
    record = read_assignment(mentioned)
    assert record["format"] == "essay"
    assert record["question"] is None
    assert _lines(mentioned)[1] == "Format: essay."
    assert _lines(mentioned)[2] == QUESTION_UNREAD
    assert (essay_dir("CUE2002AA") / "brief.md").read_text(encoding="utf-8") == annual


@pytest.mark.parametrize("case_id", [pytest.param("essay-cues-a6", id="essay-cues-a6")])
def test_essay_cues_a6_a_mention_or_negation_is_not_the_assignment_type(case_id, workspace):
    """a6: A mention or a negation of a phrase is not the type. The Assessment line still is."""
    assert case_id == "essay-cues-a6"
    mention = _plant(
        "CUE2101AA",
        "Write an essay on the individual report of one named firm.\n",
    )
    assert read_assignment(mention)["format"] == "essay"
    assert _lines(mention)[1] == "Format: essay."

    negation = _plant(
        "CUE2102AA",
        "Do not write a reflective diary. Write an essay on the corridor.\n",
    )
    assert read_assignment(negation)["format"] == "essay"
    assert _lines(negation)[1] == "Format: essay."
    assert brief_genre(negation) is None

    for module, line, expected in (
        ("CUE2103AA", "Assessment: Individual report\n", "report"),
        ("CUE2104AA", "Assessment: reflective diary\n", "reflective diary"),
    ):
        seq = _plant(module, line)
        assert read_assignment(seq)["format"] == expected, module
        assert _lines(seq)[1] == f"Format: {expected}."


@pytest.mark.parametrize("case_id", [pytest.param("essay-cues-a3", id="essay-cues-a3")])
def test_essay_cues_a3_labels_and_scheme_lines_still_win(case_id, workspace):
    """a3: Genre, Format, Question, Task, assignment ask, and Title keep their values."""
    assert case_id == "essay-cues-a3"
    labelled = {
        "CUE3001AA": (
            "Genre: report\nQuestion: How do chokepoints constrain the corridor?\n"
            "This assignment is an essay.\n"
            "Evaluate how a rival sentence could be taken.\n",
            "report",
            "How do chokepoints constrain the corridor?",
        ),
        "CUE3002AA": (
            "Format: essay\nTask: Evaluate the firm's actions.\n",
            "essay",
            "Evaluate the firm's actions.",
        ),
        "CUE3003AA": (
            "Title: Weekly notes\nAssessment: Individual report\n",
            "report",
            "Weekly notes",
        ),
        "CUE3004AA": (
            "Assignment ask: Should the council publish the recycling figure?\n"
            "Evaluate how the prose sentence could replace the label.\n",
            None,
            "Should the council publish the recycling figure?",
        ),
    }
    for module, (brief, format_value, question) in labelled.items():
        seq = _plant(module, brief)
        record = read_assignment(seq)
        assert record["question"] == question, module
        if format_value is None:
            assert record["format"] is None, module
            assert _lines(seq)[1] == FORMAT_UNREAD
        else:
            assert record["format"] == format_value, module
            assert _lines(seq)[1] == f"Format: {format_value}."

    folder = essay_dir("CUE3005AA")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(
        "Assessment: Individual report\nQuestion: How do chokepoints constrain the corridor?\n",
        encoding="utf-8",
    )
    (folder / "mark-scheme.md").write_text(
        "Format: essay\nHigh Distinction (80-100): the question is answered.\n",
        encoding="utf-8",
    )
    scheme = _plant("CUE3005AA", (folder / "brief.md").read_text(encoding="utf-8"))
    assert read_assignment(scheme)["format"] == "essay"
    assert read_assignment(scheme)["question"] == "How do chokepoints constrain the corridor?"


@pytest.mark.parametrize("case_id", [pytest.param("essay-cues-a4", id="essay-cues-a4")])
def test_essay_cues_a4_a_mark_scheme_bullet_is_not_the_question(case_id, workspace):
    """a4: The task sentence and the question are not taken from a mark-scheme bullet."""
    assert case_id == "essay-cues-a4"
    bullets = _plant(
        "CUE4001AA",
        "Assessment: Individual report\n"
        "\n"
        "The module office keeps the cover sheet.\n"
        "\n"
        "Mark scheme\n"
        "- Evaluate how marks are awarded for presentation?\n"
        "- Does the essay answer the question?\n",
    )
    record = read_assignment(bullets)
    assert record["format"] == "report"
    assert record["question"] is None
    assert _lines(bullets)[2] == QUESTION_UNREAD

    prose = _plant(
        "CUE4002AA",
        "Assessment: Individual report\n"
        "\n"
        f"{EVALUATE}\n"
        "\n"
        "Mark scheme\n"
        "- Evaluate how marks are awarded for presentation?\n",
    )
    assert read_assignment(prose)["question"] == EVALUATE

    plain_scheme = _plant(
        "CUE4003AA",
        "Module code: CUE4003AA\n\nMark scheme\nEvaluate how the marker scores the work.\n",
    )
    assert read_assignment(plain_scheme)["question"] is None


@pytest.mark.parametrize("case_id", [pytest.param("essay-cues-a5", id="essay-cues-a5")])
def test_essay_cues_a5_a_parsed_word_count_stays(case_id, workspace):
    """a5: A word count that already parses is the same count after the cue is read."""
    assert case_id == "essay-cues-a5"
    seq = _plant("CUE5001AA", WALK)
    band = document_word_band(seq)
    assert band == word_band_from_brief_text(WALK)
    assert band["limit"] == 2000
    assert band["min"] == 1800
    assert band["max"] == 2200
    assert read_assignment(seq)["format"] == "report"
    assert document_word_band(seq) == band

    counted = "Word count: 1,500 words.\nThe handbook mentions an essay in passing.\n"
    other = _plant("CUE5002AA", counted)
    other_band = document_word_band(other)
    assert other_band["limit"] == 1500
    assert other_band["min"] == 1350
    assert other_band["max"] == 1650
    assert read_assignment(other)["format"] is None
    assert document_word_band(other) == other_band
    assert (essay_dir("CUE5002AA") / "brief.md").read_text(encoding="utf-8") == counted


@pytest.mark.parametrize("case_id", [pytest.param("essay-cues-b1", id="essay-cues-b1")])
def test_essay_cues_b1_brief_files_are_not_rewritten(case_id, workspace):
    """b1: brief.md, brief.txt, and brief.docx bytes stay, and the cold case still says so."""
    assert case_id == "essay-cues-b1"
    folder = essay_dir("CUE6001AA")
    folder.mkdir(parents=True, exist_ok=True)
    before: dict[str, bytes] = {}
    for name in ("brief.md", "brief.txt"):
        path = folder / name
        path.write_text(WALK, encoding="utf-8")
        before[name] = path.read_bytes()
    word = folder / "brief.docx"
    document = Document()
    document.add_paragraph(WALK)
    document.save(str(word))
    before["brief.docx"] = word.read_bytes()

    seq = open_sequence("CUE6001AA")
    assert read_assignment(seq)["format"] == "report"
    assert read_assignment(seq)["question"] == EVALUATE
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

    cold = Path(__file__).with_name("test_cold_e2e.py").read_text(encoding="utf-8")
    assert "The brief file is not rewritten" in cold
    assert "path.read_bytes() == before" in cold
    assert '"Question:" not in path.read_text' in cold


@pytest.mark.parametrize("case_id", [pytest.param("essay-cues-b2", id="essay-cues-b2")])
def test_essay_cues_b2_the_chat_may_ask_and_stores_no_answer(case_id, workspace):
    """b2: No remembered answer is stored. The chat may ask, and it does not claim memory."""
    assert case_id == "essay-cues-b2"
    seq = _plant("CUE7001AA", WALK)
    folder = essay_dir("CUE7001AA")
    ask = "Which format does the brief want: an essay or a report?"
    lines = list(basics_pass_lines(seq))
    reply = essay_stage(seq, "1", "draft", "\n".join(lines) + "\n" + ask)
    assert reply["ok"] is True, reply
    assert reply["stored"] is False
    spoken = "\n".join(str(value) for value in reply.values() if isinstance(value, str))
    spoken += "\n".join(lines) + "\n" + ask
    folded = spoken.casefold()
    for claim in MEMORY_CLAIMS:
        assert claim not in folded, claim
    assert ask in spoken
    assert not (folder / "brief-meta.json").exists()
    for name in folder.rglob("*"):
        assert name.name not in {"formatAnswer", "questionAnswer"}
    assert "formatAnswer" not in spoken
    assert "questionAnswer" not in spoken


@pytest.mark.parametrize("case_id", [pytest.param("essay-cues-b3", id="essay-cues-b3")])
def test_essay_cues_b3_an_unset_brief_keeps_the_combined_title(case_id, workspace):
    """b3: Stage titles stay. A brief the cues leave unset keeps the combined title."""
    assert case_id == "essay-cues-b3"
    assert stage_title("2", None) == COMBINED_STAGE_TWO
    assert stage_title("3", None) == COMBINED_STAGE_THREE

    both = _plant(
        "CUE8001AA",
        "This assignment is an essay or a report.\nStudents should evaluate sources in class.\n",
    )
    assert read_assignment(both)["format"] is None
    assert brief_genre(both) is None
    assert stage_title("2", brief_genre(both)) == COMBINED_STAGE_TWO
    assert stage_title("3", brief_genre(both)) == COMBINED_STAGE_THREE

    walk = _plant("CUE8002AA", WALK)
    assert read_assignment(walk)["format"] == "report"
    assert brief_genre(walk) is None
    assert stage_title("2", brief_genre(walk)) == COMBINED_STAGE_TWO


@pytest.mark.parametrize("case_id", [pytest.param("essay-cues-b4", id="essay-cues-b4")])
def test_essay_cues_b4_one_reader_serves_every_seat(case_id, workspace):
    """b4: Cursor and Grok Build read the same record. The gate does not import mark fit."""
    assert case_id == "essay-cues-b4"
    seq = _plant("CUE9001AA", WALK)
    shared = assignment_requirements(seq)
    assert shared == build_record(seq)
    assert shared == cursor_record(seq)
    assert shared["format"] == "report"
    assert shared["question"] == EVALUATE

    source = Path(__file__).resolve().parents[1] / "src" / "essay_writer" / "assignment_gate.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert all("mark_fit" not in name for name in imported)

    labelled = _plant(
        "CUE9002AA",
        "Genre: report\n"
        "Question: How do chokepoints constrain the corridor?\n"
        "Evaluate how a rival sentence could be taken.\n",
    )
    assert read_assignment(labelled)["question"] == "How do chokepoints constrain the corridor?"
    from essay_writer.mark_fit import specialist_lookup_query

    query = specialist_lookup_query(labelled, ["industry source"])
    assert "How do chokepoints constrain the corridor?" in query
    assert "rival sentence" not in query


@pytest.mark.parametrize("case_id", [pytest.param("essay-cues-c1", id="essay-cues-c1")])
def test_essay_cues_c1_a_rejected_signal_keeps_the_unread_line(case_id, workspace):
    """c1: A signal that is not a cue keeps the unread line. Silence keeps the older line."""
    assert case_id == "essay-cues-c1"
    rejected = _plant(
        "CUE1101AA",
        "The handbook mentions an essay in passing.\n"
        "Students should evaluate sources in class.\n"
        "Notes: why now?\n",
    )
    record = read_assignment(rejected)
    assert record["format"] is None
    assert record["question"] is None
    assert _lines(rejected)[1] == FORMAT_UNREAD
    assert _lines(rejected)[2] == QUESTION_UNREAD

    silent = _plant("CUE1102AA", "Module code: CUE1102AA\n")
    assert read_assignment(silent)["format"] is None
    assert read_assignment(silent)["question"] is None
    assert _lines(silent)[1] == FORMAT_NAMED_ONE
    assert _lines(silent)[2] == QUESTION_NAMED_ONE


@pytest.mark.parametrize("case_id", [pytest.param("essay-cues-c2", id="essay-cues-c2")])
def test_essay_cues_c2_parent_weight_cases_still_hold(case_id, workspace):
    """c2: Percentage tables, empty headings, and the official fixture keep their lines."""
    assert case_id == "essay-cues-c2"
    table = _plant(
        "CUE1201AA",
        "Genre: report\n"
        "Question: How do chokepoints constrain the corridor?\n"
        "\n"
        "Section weights:\n"
        "\n"
        "| Section | Weight |\n"
        "| --- | --- |\n"
        "| Analysis | 60% |\n"
        "| Evidence | 40% |\n",
    )
    assert percentage_weights_only(table) is True
    assert _lines(table)[0] == PERCENTAGE_WEIGHTS
    assert _lines(table)[1] == "Format: report."
    assert _lines(table)[2] == "Question: How do chokepoints constrain the corridor?"

    empty_weights = _plant(
        "CUE1202AA",
        "Genre: report\n"
        "Question: How do chokepoints constrain the corridor?\n"
        "\n"
        "Section weights:\n"
        "\n"
        "Word count: 2,000 words, plus or minus 10%.\n",
    )
    assert percentage_weights_only(empty_weights) is False
    assert _lines(empty_weights)[0] == NO_MARK_SCHEME

    for module, heading in (
        ("CUE1203AA", "Mark scheme"),
        ("CUE1204AA", "Marking guidelines"),
        ("CUE1205AA", "Rubric"),
    ):
        planted = _plant(
            module,
            "Genre: report\n"
            "Question: How do chokepoints constrain the corridor?\n"
            "\n"
            f"{heading}\n"
            "\n"
            "Word count: 2,000 words, plus or minus 10%.\n",
        )
        assert percentage_weights_only(planted) is False, module
        assert _lines(planted)[0] == NO_MARK_SCHEME, module

    fixture = Path(__file__).with_name("fixtures") / "synth-mark-brief-v1.md"
    official = _plant("CUE1206AA", fixture.read_text(encoding="utf-8"))
    assert percentage_weights_only(official) is True
    assert _lines(official)[0] == PERCENTAGE_WEIGHTS
    assert read_assignment(official)["highest_band"] is None


@pytest.mark.parametrize("case_id", [pytest.param("essay-cues-d1", id="essay-cues-d1")])
def test_essay_cues_d1_a_failed_update_does_not_guess_into_a_file(case_id, workspace, monkeypatch):
    """d1: A failed show or a failed write leaves the brief bytes and invents no band."""
    assert case_id == "essay-cues-d1"
    seq = _plant("CUE1301AA", WALK)
    folder = essay_dir("CUE1301AA")
    brief = folder / "brief.md"
    before = brief.read_bytes()
    written_before = sorted(str(path.relative_to(folder)) for path in folder.rglob("*"))

    def unavailable(_essay_id: str):
        raise OSError("the spoken lines are unavailable")

    showing = grok_bot.basics_pass_lines
    monkeypatch.setattr(grok_bot, "basics_pass_lines", unavailable)
    with pytest.raises(OSError, match="spoken lines are unavailable"):
        essay_stage(seq, "1", "draft", "The corridor is the case here.")
    monkeypatch.setattr(grok_bot, "basics_pass_lines", showing)

    assert brief.read_bytes() == before
    assert "Genre:" not in brief.read_text(encoding="utf-8")
    assert "Question:" not in brief.read_text(encoding="utf-8")
    record = read_assignment(seq)
    assert record["format"] == "report"
    assert record["question"] == EVALUATE
    assert record["highest_band"] is None
    written_after = sorted(str(path.relative_to(folder)) for path in folder.rglob("*"))
    assert written_after == written_before
    assert not (folder / "brief-meta.json").exists()
    for path in folder.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert "formatAnswer" not in text
            assert "questionAnswer" not in text

    torn = _plant("CUE1302AA", WALK)
    other = essay_dir("CUE1302AA")
    other_brief = other / "brief.md"
    other_before = other_brief.read_bytes()
    from essay_writer import stage_state

    real = stage_state._atomic

    def tearing(path, value):
        if Path(path).name == "stage.json":
            raise RuntimeError("torn before pointer")
        real(path, value)

    monkeypatch.setattr(stage_state, "_atomic", tearing)
    with pytest.raises(RuntimeError, match="torn before pointer"):
        essay_stage(torn, "1", "draft", "The corridor is the case here.")
    monkeypatch.setattr(stage_state, "_atomic", real)

    assert other_brief.read_bytes() == other_before
    assert "Genre:" not in other_brief.read_text(encoding="utf-8")
    assert "Question:" not in other_brief.read_text(encoding="utf-8")
    partial = read_assignment(torn)
    assert partial["format"] == "report"
    assert partial["question"] == EVALUATE
    assert partial["highest_band"] is None
    assert not (other / "brief-meta.json").exists()
    for path in other.rglob("*.json"):
        assert "70-80" not in path.read_text(encoding="utf-8")
