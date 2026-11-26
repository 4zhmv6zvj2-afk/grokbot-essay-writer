"""A stage draft can store a format or a question beside the brief.

The brief file is not rewritten. An empty look stores the answer and does
not advance. A sentence of the student's own still drafts the stage.

Ids are seated once, in the test docstring that proves that case.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import pytest
from docx import Document
from helpers import open_sequence, picked

from essay_writer.assignment_gate import (
    FORMAT_NAMED_ONE,
    PERCENTAGE_WEIGHTS,
    QUESTION_NAMED_ONE,
    assignment_requirements,
    percentage_weights_only,
    read_assignment,
)
from essay_writer.build_office import assignment_requirements as build_record
from essay_writer.cursor_office import assignment_requirements as cursor_record
from essay_writer.doors import DOORS
from essay_writer.fo_chat_locks import FO_STAGES_ROLL_FORWARD
from essay_writer.mark_fit import mark_fit_notes
from essay_writer.paths import essay_dir, work_dir
from essay_writer.projects import essay_project_delete
from essay_writer.server import HANDLERS, INSTRUCTIONS
from essay_writer.specialists.grok_bot import basics_pass_lines
from essay_writer.stage_context import StageArgs
from essay_writer.stage_llm import stage_tool_description
from essay_writer.stage_next import ANSWER_NEXT, CLEARED_NEXT, IGNORED_NEXT
from essay_writer.stage_state import load_pointer
from essay_writer.stage_track import essay_stage
from essay_writer.textutil import module_brief_text

REPO = Path(__file__).resolve().parents[1]
QUESTION = "Evaluate how Northwind Components could close the material loop."
OTHER_QUESTION = "How do chokepoints constrain the corridor?"
SILENT = "Module code: ASK1001AA\nStudents meet on Tuesdays in the seminar room.\n"
CHANGED = "Module code: ASK1001AA\nStudents meet on Wednesdays in the seminar room.\n"
LOOK = "The corridor is the case here."
STORED_NEXT = (
    "I have stored that answer beside the brief. This stage still needs one sentence of your own."
)
HOST_ASK = (
    "When the student answers a format or question gap, call the current stage draft "
    "with formatAnswer or questionAnswer and omit look. That call stores the answer, "
    "returns no card, and does not advance. Do not send confirm for that reply."
)
CLAUSE = " formatAnswer or questionAnswer stores the answer and does not advance."
SECTIONS = [
    {
        "heading": "Literature review",
        "body": "The corridor is discussed in general terms.",
    }
]
WEIGHTS = "Section weights:\nIntroduction 40%\nAnalysis 60%\n"
REPORT_SECTIONS = (
    "Required sections:\n"
    "- Introduction\n"
    "- Analysis\n"
    "Students meet on Tuesdays in the seminar room.\n"
)


def _plant(module: str, brief: str) -> str:
    folder = essay_dir(module)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(brief, encoding="utf-8")
    return open_sequence(module)


def _meta(module: str) -> Path:
    return essay_dir(module) / "brief-meta.json"


def _digest(seq: str) -> str:
    return hashlib.sha256(module_brief_text(seq).strip().encode("utf-8")).hexdigest()


def _load(module: str) -> dict:
    return json.loads(_meta(module).read_text(encoding="utf-8"))


@pytest.mark.parametrize("case_id", [pytest.param("essay-ask-a1", id="essay-ask-a1")])
def test_a_draft_stores_the_format_and_question(case_id, workspace):
    """essay-ask-a1: A stage draft stores the format and question the brief left empty."""
    assert case_id == "essay-ask-a1"
    folder = essay_dir("ASK1001AA")
    folder.mkdir(parents=True, exist_ok=True)
    brief = folder / "brief.md"
    brief.write_text(SILENT, encoding="utf-8")
    text = folder / "brief.txt"
    text.write_text(SILENT, encoding="utf-8")
    word = folder / "brief.docx"
    document = Document()
    document.add_paragraph(SILENT.strip())
    document.save(str(word))
    before = {path.name: path.read_bytes() for path in (brief, text, word)}
    seq = open_sequence("ASK1001AA")
    assert read_assignment(seq)["format"] is None
    assert read_assignment(seq)["question"] is None

    reply = essay_stage(
        seq,
        "1",
        "draft",
        formatAnswer="report",
        questionAnswer=QUESTION,
    )
    assert reply["ok"] is True, reply
    seen = read_assignment(seq)
    assert seen["format"] == "report"
    assert seen["question"] == QUESTION
    assert seen["highest_band"] is None
    assert seen["mark_scheme"] is False
    for path in (brief, text, word):
        assert path.read_bytes() == before[path.name]
    stored = _load("ASK1001AA")
    assert list(stored) == ["brief_sha256", "format", "question"]
    assert stored["brief_sha256"] == _digest(seq)
    assert stored["format"] == "report"
    assert stored["question"] == QUESTION
    assert "highest_band" not in stored
    assert "named_entries" not in stored
    assert "mark_scheme" not in stored
    found = [path.relative_to(folder).as_posix() for path in folder.rglob("brief-meta.json")]
    assert found == ["brief-meta.json"]

    later = open_sequence("ASK1001AA")
    assert later != seq
    assert read_assignment(later)["format"] == "report"
    assert read_assignment(later)["question"] == QUESTION

    cold = (REPO / "tests" / "test_cold_e2e.py").read_text(encoding="utf-8")
    assert "The brief file is not rewritten" in cold
    assert "path.read_bytes() == before" in cold
    assert '"Question:" not in path.read_text' in cold


@pytest.mark.parametrize("case_id", [pytest.param("essay-ask-a2", id="essay-ask-a2")])
def test_labels_scheme_lines_and_cues_win(case_id, workspace):
    """essay-ask-a2: A labelled line, a scheme line, or a cue wins over a stored answer."""
    assert case_id == "essay-ask-a2"
    labelled = _plant("ASK2001AA", "Genre: essay\nStudents meet on Tuesdays in the seminar room.\n")
    essay_stage(labelled, "1", "draft", formatAnswer="report", questionAnswer=QUESTION)
    assert read_assignment(labelled)["format"] == "essay"

    cue = _plant("ASK2002AA", "Assessment: Individual report\nStudents meet on Tuesdays.\n")
    essay_stage(cue, "1", "draft", formatAnswer="essay")
    assert read_assignment(cue)["format"] == "report"

    asked = _plant("ASK2003AA", f"Question: {OTHER_QUESTION}\nStudents meet on Tuesdays.\n")
    essay_stage(asked, "1", "draft", questionAnswer=QUESTION)
    assert read_assignment(asked)["question"] == OTHER_QUESTION

    scheme = _plant("ASK2004AA", SILENT)
    (essay_dir("ASK2004AA") / "mark-scheme.md").write_text("Format: essay\n", encoding="utf-8")
    essay_stage(scheme, "1", "draft", formatAnswer="report")
    assert read_assignment(scheme)["format"] == "essay"

    task = _plant("ASK2005AA", "Evaluate how a named firm should publish the figure.\n")
    essay_stage(task, "1", "draft", formatAnswer="report", questionAnswer=QUESTION)
    seen = read_assignment(task)
    assert seen["question"] == "Evaluate how a named firm should publish the figure."
    assert seen["format"] == "report"


@pytest.mark.parametrize("case_id", [pytest.param("essay-ask-a3", id="essay-ask-a3")])
def test_a_matching_file_fills_an_empty_field(case_id, workspace):
    """essay-ask-a3: A matching file fills an empty field, and a bad value is ignored."""
    assert case_id == "essay-ask-a3"
    for module, answer in (
        ("ASK3101AA", "essay"),
        ("ASK3102AA", "report"),
        ("ASK3103AA", "reflective diary"),
    ):
        seq = _plant(module, SILENT)
        essay_stage(seq, "1", "draft", formatAnswer=answer, questionAnswer=QUESTION)
        seen = read_assignment(seq)
        assert seen["format"] == answer, module
        assert seen["question"] == QUESTION

    titled = _plant("ASK3201AA", SILENT)
    essay_stage(titled, "1", "draft", formatAnswer="Report")
    assert read_assignment(titled)["format"] == "report"

    ignored = _plant("ASK3202AA", SILENT)
    essay_stage(ignored, "1", "draft", formatAnswer="novel", questionAnswer=QUESTION)
    seen = read_assignment(ignored)
    assert seen["format"] is None
    assert seen["question"] == QUESTION
    assert _load("ASK3202AA")["question"] == QUESTION
    assert "format" not in _load("ASK3202AA")

    planted = _plant("ASK3203AA", SILENT)
    _meta("ASK3203AA").write_text(
        json.dumps(
            {
                "brief_sha256": _digest(planted),
                "format": "playlist",
                "question": QUESTION,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    seen = read_assignment(planted)
    assert seen["format"] is None
    assert seen["question"] == QUESTION
    assert _meta("ASK3203AA").is_file()

    stale = _plant("ASK3204AA", SILENT)
    essay_stage(stale, "1", "draft", formatAnswer="report", questionAnswer=QUESTION)
    brief = essay_dir("ASK3204AA") / "brief.md"
    brief.write_text(CHANGED, encoding="utf-8")
    assert read_assignment(stale)["format"] is None
    assert read_assignment(stale)["question"] is None
    assert _meta("ASK3204AA").is_file()
    assert _load("ASK3204AA")["brief_sha256"] != _digest(stale)
    essay_stage(stale, "1", "draft", formatAnswer="essay")
    assert read_assignment(stale)["format"] == "essay"
    assert _load("ASK3204AA")["brief_sha256"] == _digest(stale)


@pytest.mark.parametrize("case_id", [pytest.param("essay-ask-a4", id="essay-ask-a4")])
def test_an_empty_answer_clears_that_field(case_id, workspace):
    """essay-ask-a4: An empty answer clears that field, and two empty answers delete the file."""
    assert case_id == "essay-ask-a4"
    seq = _plant("ASK4001AA", SILENT)
    essay_stage(seq, "1", "draft", formatAnswer="report", questionAnswer=QUESTION)
    essay_stage(seq, "1", "draft", formatAnswer="")
    kept = _load("ASK4001AA")
    assert "format" not in kept
    assert kept["question"] == QUESTION
    assert read_assignment(seq)["format"] is None
    assert read_assignment(seq)["question"] == QUESTION

    essay_stage(seq, "1", "draft", questionAnswer="")
    assert not _meta("ASK4001AA").exists()
    assert read_assignment(seq)["question"] is None

    again = _plant("ASK4002AA", SILENT)
    essay_stage(again, "1", "draft", formatAnswer="essay", questionAnswer=QUESTION)
    cleared = essay_stage(again, "1", "draft", formatAnswer="", questionAnswer="")
    assert cleared["ok"] is True, cleared
    assert cleared.get("refused") != "guidance-only"
    assert not _meta("ASK4002AA").exists()

    empty = _plant("ASK4003AA", SILENT)
    reply = essay_stage(empty, "1", "draft", formatAnswer="")
    assert reply["ok"] is True, reply
    assert reply.get("refused") != "guidance-only"
    assert not _meta("ASK4003AA").exists()


@pytest.mark.parametrize("case_id", [pytest.param("essay-ask-a5", id="essay-ask-a5")])
def test_deleting_the_module_removes_the_stored_answer(case_id, workspace):
    """essay-ask-a5: Deleting the module removes the stored answer. One sequence does not."""
    assert case_id == "essay-ask-a5"
    module = "ASK5001AA"
    first = _plant(module, SILENT)
    second = open_sequence(module)
    essay_stage(first, "1", "draft", formatAnswer="report", questionAnswer=QUESTION)
    assert _meta(module).is_file()
    draft = essay_project_delete(module, "draft", sequence=second)
    assert draft["ok"] is True, draft
    deleted = essay_project_delete(module, "confirm", sequence=second, **picked(draft))
    assert deleted["ok"] is True, deleted
    assert not (work_dir(second)).exists()
    assert (essay_dir(module) / "brief.md").is_file()
    assert _meta(module).is_file()
    assert read_assignment(first)["format"] == "report"

    module_draft = essay_project_delete(module, "draft")
    removed = essay_project_delete(module, "confirm", **picked(module_draft))
    assert removed["ok"] is True, removed
    assert not essay_dir(module).exists()
    assert not _meta(module).exists()


@pytest.mark.parametrize("case_id", [pytest.param("essay-ask-a6", id="essay-ask-a6")])
def test_no_brief_and_no_scheme_stores_nothing(case_id, workspace, monkeypatch):
    """essay-ask-a6: With no brief and no scheme, the draft stores nothing."""
    assert case_id == "essay-ask-a6"
    seq = open_sequence("ASK6001AA")
    folder = essay_dir("ASK6001AA")
    leftover = _meta("ASK6001AA")
    leftover.write_text('{"brief_sha256": "leftover", "format": "report"}\n', encoding="utf-8")
    before = leftover.read_bytes()

    from essay_writer import assignment_gate as gate

    def denied(*_args, **_kwargs):
        raise AssertionError("the side file was read")

    original = gate._read_brief_meta
    monkeypatch.setattr(gate, "_read_brief_meta", denied)
    reply = essay_stage(seq, "1", "draft", formatAnswer="report", questionAnswer=QUESTION)
    assert reply["ok"] is False, reply
    assert reply["refused"] == "no-brief"
    assert reply["refused"] != "guidance-only"
    assert leftover.read_bytes() == before
    written = [path.name for path in folder.rglob("brief-meta.json")]
    assert written == ["brief-meta.json"]
    monkeypatch.setattr(gate, "_read_brief_meta", original)
    scheme = open_sequence("ASK6002AA")
    (essay_dir("ASK6002AA") / "mark-scheme.md").write_text(
        "Presentation 20%\nAnalysis 80%\n",
        encoding="utf-8",
    )
    allowed = essay_stage(scheme, "1", "draft", formatAnswer="report", questionAnswer=QUESTION)
    assert allowed["ok"] is True, allowed
    assert allowed.get("refused") != "no-brief"
    assert _meta("ASK6002AA").is_file()
    assert read_assignment(scheme)["format"] == "report"
    assert read_assignment(scheme)["question"] == QUESTION


@pytest.mark.parametrize("case_id", [pytest.param("essay-ask-a7", id="essay-ask-a7")])
def test_an_empty_look_stores_the_answer_and_does_not_advance(case_id, workspace):
    """essay-ask-a7: An empty look stores the answer and leaves the stage where it is."""
    assert case_id == "essay-ask-a7"
    assert STORED_NEXT == ANSWER_NEXT
    seq = _plant("ASK7001AA", SILENT)
    pointer = work_dir(seq) / "tracking" / "stage.json"
    before = pointer.read_bytes() if pointer.is_file() else None
    reply = essay_stage(seq, "1", "draft", formatAnswer="report", questionAnswer=QUESTION)
    assert reply["ok"] is True, reply
    assert reply["stored"] is False
    assert reply["next"] == STORED_NEXT
    for key in ("card", "cardAction", "cardDigest", "refused"):
        assert key not in reply
    assert "guidance-only" not in reply.values()
    assert (pointer.read_bytes() if pointer.is_file() else None) == before
    assert not (work_dir(seq) / "tracking" / "1.md").exists()
    saved = load_pointer(seq)
    assert saved["current"] == "1"
    assert saved["saved"] == []
    assert saved["waiting_stage"] is None
    assert saved["waiting_digest"] is None
    assert _load("ASK7001AA")["format"] == "report"

    meta_before = _meta("ASK7001AA").read_bytes()
    refused = essay_stage(seq, "1", "draft")
    assert refused["ok"] is False
    assert refused["refused"] == "guidance-only"
    assert _meta("ASK7001AA").read_bytes() == meta_before
    assert (pointer.read_bytes() if pointer.is_file() else None) == before


@pytest.mark.parametrize("case_id", [pytest.param("essay-ask-a8", id="essay-ask-a8")])
def test_a_confirmable_look_stores_the_answer_and_drafts(case_id, workspace, monkeypatch):
    """essay-ask-a8: A confirmable look stores the answer first, then drafts the stage."""
    assert case_id == "essay-ask-a8"
    seq = _plant("ASK8001AA", SILENT)
    brief = essay_dir("ASK8001AA") / "brief.md"
    before = brief.read_bytes()
    from essay_writer.stage_track import _draft_reply

    def stopped(*_args, **_kwargs):
        raise RuntimeError("draft stopped")

    monkeypatch.setattr("essay_writer.stage_track._draft_reply", stopped)
    with pytest.raises(RuntimeError, match="draft stopped"):
        essay_stage(
            seq,
            "1",
            "draft",
            LOOK,
            formatAnswer="report",
            questionAnswer=QUESTION,
        )
    assert _load("ASK8001AA")["format"] == "report"
    assert brief.read_bytes() == before
    assert load_pointer(seq)["waiting_stage"] is None

    monkeypatch.setattr("essay_writer.stage_track._draft_reply", _draft_reply)
    reply = essay_stage(
        seq,
        "1",
        "draft",
        LOOK,
        formatAnswer="report",
        questionAnswer=QUESTION,
    )
    assert reply["ok"] is True, reply
    assert reply["stored"] is False
    assert reply["card"]["kind"] == "confirm"
    assert brief.read_bytes() == before
    assert read_assignment(seq)["question"] == QUESTION

    quiet = open_sequence("ASK8002AA")
    (essay_dir("ASK8002AA") / "brief.md").write_text(SILENT, encoding="utf-8")
    confirm = essay_stage(
        quiet,
        "1",
        "confirm",
        formatAnswer="report",
        questionAnswer=QUESTION,
    )
    assert confirm.get("refused") != "no-brief"
    assert not _meta("ASK8002AA").exists()
    omitted = essay_stage(seq, "1", "draft", formatAnswer="essay")
    assert omitted["ok"] is True, omitted
    assert "card" not in omitted
    assert _load("ASK8001AA")["format"] == "essay"


@pytest.mark.parametrize("case_id", [pytest.param("essay-ask-a9", id="essay-ask-a9")])
def test_the_reply_names_stored_cleared_or_ignored(case_id, workspace):
    """essay-ask-a9: The next line says stored, cleared, or ignored, and a confirm does not skip the gate."""
    assert case_id == "essay-ask-a9"
    fresh = _plant("ASK9101AA", SILENT)
    empty = essay_stage(fresh, "1", "draft", formatAnswer="")
    assert empty["ok"] is True, empty
    assert empty["next"] == IGNORED_NEXT
    assert empty["stored"] is False
    assert not _meta("ASK9101AA").exists()

    unused = _plant("ASK9102AA", SILENT)
    novel = essay_stage(unused, "1", "draft", formatAnswer="novel")
    assert novel["ok"] is True, novel
    assert novel["next"] == IGNORED_NEXT
    assert read_assignment(unused)["format"] is None
    assert not _meta("ASK9102AA").exists()

    seq = _plant("ASK9103AA", SILENT)
    stored = essay_stage(seq, "1", "draft", formatAnswer="report", questionAnswer=QUESTION)
    assert stored["ok"] is True, stored
    assert stored["next"] == ANSWER_NEXT
    assert _load("ASK9103AA")["format"] == "report"
    cleared = essay_stage(seq, "1", "draft", formatAnswer="", questionAnswer="")
    assert cleared["ok"] is True, cleared
    assert cleared["next"] == CLEARED_NEXT
    assert not _meta("ASK9103AA").exists()

    mixed = _plant("ASK9105AA", SILENT)
    essay_stage(mixed, "1", "draft", formatAnswer="report", questionAnswer=QUESTION)
    one_each = essay_stage(mixed, "1", "draft", formatAnswer="essay", questionAnswer="")
    assert one_each["ok"] is True, one_each
    assert one_each["next"] == (
        "I have stored the format and cleared the question beside the brief. "
        "This stage still needs one sentence of your own."
    )
    assert one_each["stored"] is False
    kept = _load("ASK9105AA")
    assert kept["format"] == "essay"
    assert "question" not in kept
    other_way = essay_stage(mixed, "1", "draft", formatAnswer="", questionAnswer=QUESTION)
    assert other_way["next"] == (
        "I have stored the question and cleared the format beside the brief. "
        "This stage still needs one sentence of your own."
    )
    swapped = _load("ASK9105AA")
    assert "format" not in swapped
    assert swapped["question"] == QUESTION

    unused_format = _plant("ASK9106AA", SILENT)
    novel_and_question = essay_stage(
        unused_format, "1", "draft", formatAnswer="novel", questionAnswer=QUESTION
    )
    assert novel_and_question["ok"] is True, novel_and_question
    assert novel_and_question["next"] == (
        "I have stored the question beside the brief. I have not stored the format. "
        "This stage still needs one sentence of your own."
    )
    question_only = _load("ASK9106AA")
    assert "format" not in question_only
    assert question_only["question"] == QUESTION
    cleared_unused = essay_stage(
        unused_format, "1", "draft", formatAnswer="novel", questionAnswer=""
    )
    assert cleared_unused["ok"] is True, cleared_unused
    assert cleared_unused["next"] == (
        "I have cleared the question beside the brief. I have not stored the format. "
        "This stage still needs one sentence of your own."
    )
    assert not _meta("ASK9106AA").exists()

    format_only = _plant("ASK9107AA", SILENT)
    only_format = essay_stage(format_only, "1", "draft", formatAnswer="report")
    assert only_format["ok"] is True, only_format
    assert only_format["next"] == ANSWER_NEXT
    assert _load("ASK9107AA")["format"] == "report"
    assert "question" not in _load("ASK9107AA")
    question_only_call = _plant("ASK9108AA", SILENT)
    only_question = essay_stage(question_only_call, "1", "draft", questionAnswer=QUESTION)
    assert only_question["ok"] is True, only_question
    assert only_question["next"] == ANSWER_NEXT
    assert _load("ASK9108AA")["question"] == QUESTION
    assert "format" not in _load("ASK9108AA")

    waiting = _plant("ASK9104AA", SILENT)
    draft = essay_stage(waiting, "1", "draft", LOOK)
    assert draft["ok"] is True, draft
    look = "\n".join(basics_pass_lines(waiting))
    blocked = essay_stage(waiting, "1", "confirm", look, formatAnswer="report", **picked(draft))
    assert blocked["ok"] is False, blocked
    assert blocked["refused"] == "guidance-only"
    assert blocked.get("stored") is not True
    assert not _meta("ASK9104AA").exists()
    assert load_pointer(waiting)["saved"] == []
    saved = essay_stage(waiting, "1", "confirm", LOOK, formatAnswer="report", **picked(draft))
    assert saved["ok"] is True, saved
    assert saved["stored"] is True
    assert not _meta("ASK9104AA").exists()


@pytest.mark.parametrize("case_id", [pytest.param("essay-ask-b1", id="essay-ask-b1")])
def test_the_stage_description_names_the_stored_answer(case_id):
    """essay-ask-b1: The stage description says an answer is stored and does not advance."""
    assert case_id == "essay-ask-b1"
    assert len(CLAUSE) == 71
    description = next(door["description"] for door in DOORS if door["tool"] == "essay.stage")
    assert CLAUSE in description
    assert "The reply started.stage is 6, with master_ask." not in description
    assert "A drop leaves the list only." not in description
    assert "The file stays." in description
    assert "A kept paper with a critical note is not gathered again." in description
    assert "from the stage rules" in description
    assert "A changed look needs a fresh draft." in description
    assert FO_STAGES_ROLL_FORWARD in description
    assert len(description) < 1200
    assert stage_tool_description() == description
    cap = (REPO / "tests" / "test_door_contract.py").read_text(encoding="utf-8")
    assert "MAX_DOOR_CHARS = 1_200" in cap
    snapshot = json.loads((REPO / "tests" / "snapshots" / "prompts.json").read_text())
    assert snapshot["doors"]["essay.stage"] == description
    assert len(DOORS) == len(HANDLERS) == 24
    assert {door["tool"] for door in DOORS} == set(HANDLERS)
    fields = StageArgs.__dataclass_fields__
    assert fields["formatAnswer"].default is None
    assert fields["questionAnswer"].default is None

    import asyncio

    from essay_writer.server import build_server

    tools = {tool.name: tool for tool in asyncio.run(build_server().list_tools())}
    assert len(tools) == 24
    schema = tools["essay.stage"].input_schema
    assert {"formatAnswer", "questionAnswer"} <= set(schema["properties"])
    assert "formatAnswer" not in set(schema.get("required") or [])
    assert "questionAnswer" not in set(schema.get("required") or [])


@pytest.mark.parametrize("case_id", [pytest.param("essay-ask-b2", id="essay-ask-b2")])
def test_the_host_instruction_sits_with_the_stage_paragraph(case_id):
    """essay-ask-b2: The longer instruction sits with the stage paragraph."""
    assert case_id == "essay-ask-b2"
    briefing = (
        REPO / "src" / "essay_writer" / "prompts" / "front_office" / "briefing.md"
    ).read_text(encoding="utf-8")
    assert HOST_ASK in briefing
    assert HOST_ASK in INSTRUCTIONS
    paragraph = next(
        line for line in briefing.splitlines() if "essay.stage and essay.project.delete" in line
    )
    assert HOST_ASK in paragraph
    tools = (REPO / "src" / "essay_writer" / "prompts" / "front_office" / "tools.json").read_text(
        encoding="utf-8"
    )
    assert "omit look" not in tools


@pytest.mark.parametrize("case_id", [pytest.param("essay-ask-b3", id="essay-ask-b3")])
def test_the_student_readme_says_the_answer_is_stored_beside_the_brief(case_id):
    """essay-ask-b3: The student readme says the answer is stored beside the brief."""
    assert case_id == "essay-ask-b3"
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    student = readme.split("## Using Essay Bot (students)", 1)[1].split("## ", 1)[0]
    flat = " ".join(student.split())
    assert "A pasted brief is read as you wrote it." in flat
    assert "Genre: and Question: lines are still understood." in flat
    assert "The chat asks when it cannot tell the format or the question" in flat
    assert "the answer is stored beside the brief rather than written into it." in flat


@pytest.mark.parametrize("case_id", [pytest.param("essay-ask-b4", id="essay-ask-b4")])
def test_weight_notes_use_the_stored_format(case_id, workspace):
    """essay-ask-b4: Weight notes follow the stored format. The file does not set a band."""
    assert case_id == "essay-ask-b4"
    source = (REPO / "src" / "essay_writer" / "mark_fit.py").read_text(encoding="utf-8")
    assert "genre_from_brief_text" not in source
    notes = inspect.getsource(mark_fit_notes)
    assert "read_assignment" in notes
    assert "brief.casefold()" not in notes

    diary = _plant("ASK9001AA", WEIGHTS)
    assert mark_fit_notes(diary, SECTIONS, [])
    essay_stage(diary, "1", "draft", formatAnswer="reflective diary")
    assert read_assignment(diary)["format"] == "reflective diary"
    assert mark_fit_notes(diary, SECTIONS, []) == []

    report = _plant("ASK9002AA", WEIGHTS)
    essay_stage(report, "1", "draft", formatAnswer="report")
    assert mark_fit_notes(report, SECTIONS, [])

    seq = _plant("ASK9003AA", REPORT_SECTIONS)
    before = read_assignment(seq)
    assert before["format"] is None
    assert before["lock"] is None
    essay_stage(seq, "1", "draft", formatAnswer="report", questionAnswer=QUESTION)
    seen = read_assignment(seq)
    assert seen["format"] == "report"
    assert seen["writing_type"] == "report"
    assert seen["lock"] == "purpose_and_scope"
    assert seen["highest_band"] is None
    assert seen["mark_scheme"] is False
    raw = _meta("ASK9003AA").read_text(encoding="utf-8")
    assert "highest_band" not in raw
    assert "named_entries" not in raw
    assert "mark_scheme" not in raw
    shared = assignment_requirements(seq)
    assert shared == build_record(seq) == cursor_record(seq)
    assert shared["format"] == "report"
    assert shared["question"] == QUESTION
    _scores, format_line, question_line = basics_pass_lines(seq)
    assert format_line == "Format: report."
    assert question_line == f"Question: {QUESTION}"


@pytest.mark.parametrize("case_id", [pytest.param("essay-ask-c1", id="essay-ask-c1")])
def test_gap_lines_and_cues_hold_without_a_usable_answer(case_id, workspace):
    """essay-ask-c1: Gap lines and cues hold when no usable answer is stored."""
    assert case_id == "essay-ask-c1"
    cue = _plant(
        "ASK1101AA",
        "Assessment: Individual report\n"
        "Evaluate how a named supply chain should integrate sustainability.\n",
    )
    folder = essay_dir("ASK1101AA")
    before = (folder / "brief.md").read_bytes()
    assert not _meta("ASK1101AA").exists()
    seen = read_assignment(cue)
    assert seen["format"] == "report"
    assert seen["question"] == (
        "Evaluate how a named supply chain should integrate sustainability."
    )
    assert basics_pass_lines(cue)[1] == "Format: report."
    assert (folder / "brief.md").read_bytes() == before

    stale = _plant("ASK1102AA", SILENT)
    _meta("ASK1102AA").write_text(
        json.dumps({"brief_sha256": "0" * 64, "format": "report", "question": QUESTION}) + "\n",
        encoding="utf-8",
    )
    brief = essay_dir("ASK1102AA") / "brief.md"
    unchanged = brief.read_bytes()
    seen = read_assignment(stale)
    assert seen["format"] is None
    assert seen["question"] is None
    assert basics_pass_lines(stale)[1] == FORMAT_NAMED_ONE
    assert basics_pass_lines(stale)[2] == QUESTION_NAMED_ONE
    assert _meta("ASK1102AA").is_file()
    assert brief.read_bytes() == unchanged

    odd = _plant("ASK1103AA", SILENT)
    _meta("ASK1103AA").write_text(
        json.dumps({"brief_sha256": _digest(odd), "format": "playlist"}) + "\n",
        encoding="utf-8",
    )
    assert read_assignment(odd)["format"] is None
    assert basics_pass_lines(odd)[1] == FORMAT_NAMED_ONE
    assert _meta("ASK1103AA").is_file()

    labelled = _plant("ASK1104AA", "Genre: essay\nStudents meet on Tuesdays in the seminar room.\n")
    _meta("ASK1104AA").write_text(
        json.dumps({"brief_sha256": _digest(labelled), "format": "report"}) + "\n",
        encoding="utf-8",
    )
    assert read_assignment(labelled)["format"] == "essay"
    assert (
        (essay_dir("ASK1104AA") / "brief.md").read_text(encoding="utf-8").startswith("Genre: essay")
    )


@pytest.mark.parametrize("case_id", [pytest.param("essay-ask-c2", id="essay-ask-c2")])
def test_earlier_brief_cases_still_hold(case_id, workspace):
    """essay-ask-c2: The earlier brief and cue cases still hold."""
    assert case_id == "essay-ask-c2"
    cues = (REPO / "tests" / "test_obvious_cues.py").read_text(encoding="utf-8")
    gaps = (REPO / "tests" / "test_brief_gap_lines.py").read_text(encoding="utf-8")
    for name in (
        "essay-cues-a1",
        "essay-cues-a2",
        "essay-cues-a3",
        "essay-cues-a4",
        "essay-cues-a5",
        "essay-cues-a6",
        "essay-cues-a7",
        "essay-cues-a8",
        "essay-cues-b1",
        "essay-cues-b2",
        "essay-cues-b3",
        "essay-cues-b4",
        "essay-cues-c1",
        "essay-cues-c2",
        "essay-cues-d1",
    ):
        assert cues.count(name) >= 1
    for name in (
        "essay-brief-a1",
        "essay-brief-a2",
        "essay-brief-a3",
        "essay-brief-a4",
        "essay-brief-b1",
        "essay-brief-b2",
        "essay-brief-b3",
        "essay-brief-b4",
        "essay-brief-b5",
        "essay-brief-b6",
        "essay-brief-b7",
        "essay-brief-c1",
        "essay-brief-c2",
        "essay-brief-c3",
        "essay-brief-d1",
    ):
        assert gaps.count(name) >= 1

    table = _plant(
        "ASK1201AA",
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
    folder = essay_dir("ASK1201AA")
    before = (folder / "brief.md").read_bytes()
    assert percentage_weights_only(table) is True
    assert basics_pass_lines(table)[0] == PERCENTAGE_WEIGHTS
    reply = essay_stage(table, "1", "draft", LOOK)
    assert reply["ok"] is True, reply
    assert (folder / "brief.md").read_bytes() == before
    assert not _meta("ASK1201AA").exists()


@pytest.mark.parametrize("case_id", [pytest.param("essay-ask-d1", id="essay-ask-d1")])
def test_a_failed_write_leaves_the_brief_and_invents_no_band(case_id, workspace, monkeypatch):
    """essay-ask-d1: A failed write leaves the brief, advances nothing, and invents no band."""
    assert case_id == "essay-ask-d1"
    seq = _plant("ASK1301AA", SILENT)
    brief = essay_dir("ASK1301AA") / "brief.md"
    before = brief.read_bytes()
    pointer = work_dir(seq) / "tracking" / "stage.json"
    pointer_before = pointer.read_bytes() if pointer.is_file() else None

    def blocked(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("essay_writer.durable.os.replace", blocked)
    reply = essay_stage(
        seq,
        "1",
        "draft",
        LOOK,
        formatAnswer="report",
        questionAnswer=QUESTION,
    )
    assert reply["ok"] is False, reply
    assert reply.get("refused") != "guidance-only"
    assert "card" not in reply
    assert "cardAction" not in reply
    assert "cardDigest" not in reply
    assert brief.read_bytes() == before
    assert (pointer.read_bytes() if pointer.is_file() else None) == pointer_before
    assert load_pointer(seq)["saved"] == []
    assert load_pointer(seq)["waiting_stage"] is None
    assert not _meta("ASK1301AA").exists()
    seen = read_assignment(seq)
    assert seen["format"] is None
    assert seen["highest_band"] is None
    assert "Distinction" not in json.dumps(seen)

    torn = essay_dir("ASK1301AA") / "brief-meta.json"
    torn.write_text('{"brief_sha256": "abc", "format": "rep', encoding="utf-8")
    seen = read_assignment(seq)
    assert seen["format"] is None
    assert seen["highest_band"] is None
    assert torn.is_file()
    assert brief.read_bytes() == before

    torn.write_text(
        json.dumps(
            {
                "brief_sha256": _digest(seq),
                "format": 1,
                "highest_band": "Distinction",
                "named_entries": ["Introduction"],
                "mark_scheme": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    seen = read_assignment(seq)
    assert seen["format"] is None
    assert seen["question"] is None
    assert seen["highest_band"] is None
    assert seen["mark_scheme"] is False
    assert seen["named_entries"] == []
    assert torn.is_file()
    assert brief.read_bytes() == before


@pytest.mark.parametrize("case_id", [pytest.param("essay-ask-d2", id="essay-ask-d2")])
def test_a_linked_answer_file_is_not_followed(case_id, workspace, tmp_path):
    """essay-ask-d2: A symlink beside the brief is not read or written through."""
    assert case_id == "essay-ask-d2"
    seq = _plant("ASK1401AA", SILENT)
    outside = tmp_path / "outside.json"
    payload = '{"format": "report", "question": "outside"}\n'
    outside.write_text(payload, encoding="utf-8")
    link = _meta("ASK1401AA")
    link.symlink_to(outside)
    before = outside.read_bytes()
    seen = read_assignment(seq)
    assert seen["format"] is None
    assert seen["question"] is None
    reply = essay_stage(seq, "1", "draft", formatAnswer="essay", questionAnswer=QUESTION)
    assert reply["ok"] is False, reply
    assert reply["refused"] == "answer"
    assert reply["next"] != ANSWER_NEXT
    assert link.is_symlink()
    assert outside.read_bytes() == before
    assert read_assignment(seq)["format"] is None

    linked = _plant("ASK1402AA", SILENT)
    folder = essay_dir("ASK1402AA")
    held = tmp_path / "linked-module"
    held.mkdir()
    for child in list(folder.iterdir()):
        child.rename(held / child.name)
    folder.rmdir()
    folder.symlink_to(held, target_is_directory=True)
    sentinel = held / "brief-meta.json"
    sentinel.write_text('{"format": "report", "question": "outside"}\n', encoding="utf-8")
    sentinel_before = sentinel.read_bytes()
    brief_before = (held / "brief.md").read_bytes()
    seen = read_assignment(linked)
    assert seen["format"] is None
    assert seen["question"] is None
    through = essay_stage(linked, "1", "draft", formatAnswer="essay", questionAnswer=QUESTION)
    assert through["ok"] is False, through
    assert through["refused"] == "answer"
    assert through["next"] != ANSWER_NEXT
    assert folder.is_symlink()
    assert sentinel.is_file()
    assert not sentinel.is_symlink()
    assert sentinel.read_bytes() == sentinel_before
    assert (held / "brief.md").read_bytes() == brief_before
    assert read_assignment(linked)["format"] is None
