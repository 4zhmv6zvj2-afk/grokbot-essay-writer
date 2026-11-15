"""Word cover: programme rows, conclusion, and a stored title.

Programme rows print only when the brief asks. The conclusion stays on the
pack and is said in chat when Word is written. A real stored title is the
first visible cover line.

Ids are seated once. The id is the docstring and the pytest id.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from docx import Document
from helpers import (
    card_digest_for,
    open_sequence,
    pack,
    picked,
    plant_gathered_source,
    source,
    write_upload,
)

from essay_writer.diary import cover_field_rows, cover_lines_from_field_rows, title_page_spec
from essay_writer.health import essay_health
from essay_writer.late_chain import _hydrate_pack_from_docx_cover, _say_written_conclusion
from essay_writer.paths import essay_dir, work_dir
from essay_writer.programme import PROGRAMME
from essay_writer.research import essay_research_summary
from essay_writer.specialists.grok_bot import STAGE5_SAVE_LINE, confirm_line, saved_next
from essay_writer.spine import advances_without_confirm, stage_uses_confirm_card
from essay_writer.stage_llm import stage_title
from essay_writer.stage_track import essay_stage
from essay_writer.state import load_state, save_state
from essay_writer.validate import essay_pack_validate
from essay_writer.word import cover_lines, essay_pack_render_word, write_docx
from essay_writer.writing_basics import STAGE_ORDER

REPO = Path(__file__).resolve().parents[1]
QUESTION = "How do chokepoints constrain the corridor?"
TITLE = "Named chains through the corridor"
NOTED = "The conclusion is noted."
OPEN = "The conclusion is open, not a settled finding."
COVER_NOTED = "Conclusion: noted"
COVER_OPEN = "Conclusion: open — not a settled finding"
NAME = "Ada Example"
NUMBER = "445566"
PROGRAMME_LINES = (
    "Teaching partner",
    "Awarding university",
    "Undergraduate programme",
    "PROG01",
)
ASK_IDS = (
    "essay-ask-a1",
    "essay-ask-a2",
    "essay-ask-a3",
    "essay-ask-a4",
    "essay-ask-a5",
    "essay-ask-a6",
    "essay-ask-a7",
    "essay-ask-a8",
    "essay-ask-a9",
    "essay-ask-b1",
    "essay-ask-b2",
    "essay-ask-b3",
    "essay-ask-b4",
    "essay-ask-c1",
    "essay-ask-c2",
    "essay-ask-d1",
    "essay-ask-d2",
)
PROMISE_IDS = (
    "essay-promise-a1",
    "essay-promise-a2",
    "essay-promise-a3",
    "essay-promise-a4",
    "essay-promise-b1",
    "essay-promise-b2",
    "essay-promise-b3",
    "essay-promise-c1",
    "essay-promise-c2",
    "essay-promise-d1",
)


def _plant(module: str, brief: str) -> str:
    folder = essay_dir(module)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(brief, encoding="utf-8")
    return open_sequence(module)


def _essay_brief(*, programme: bool = False, registration: bool = False) -> str:
    lines = [
        "Genre: essay",
        f"Question: {QUESTION}",
    ]
    if programme:
        lines.append("Title page: programme name and partner institution.")
    if registration:
        lines.append("Title page: registration number.")
        lines.append("The name stays off the title page and the file.")
    return "\n".join(lines) + "\n"


def _report(title: str, sections: list[dict[str, str]] | None = None) -> dict:
    body = sections or [
        {"heading": "Introduction", "body": "The corridor depends on a narrow strait."},
        {"heading": "Conclusion", "body": "The strait still carries the chain."},
    ]
    return {
        "title": title,
        "word_count": {"counted": 12, "stated": 800},
        "sections": body,
        "figures": [],
        "tables": [],
        "sources": [],
    }


def _visible(path: Path) -> tuple[list[str], list[str]]:
    document = Document(str(path))
    cover: list[str] = []
    headings: list[str] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        style = paragraph.style.name if paragraph.style is not None else ""
        if style.startswith("Heading"):
            if text:
                headings.append(text)
            continue
        if headings:
            continue
        if text:
            cover.append(text)
    return cover, headings


def _save_through(seq: str, stop: str) -> None:
    for stage in STAGE_ORDER:
        look = (
            f"This essay answers {QUESTION} "
            f"Saved from the brief. This sentence belongs to stage {stage}."
        )
        draft = essay_stage(seq, stage, "draft", look)
        assert draft["ok"] is True, (stage, draft)
        if stage == "4a":
            plant_gathered_source(seq)
        if stage == "5":
            assert draft["stored"] is True, draft
            if stage == stop:
                return
            continue
        saved = essay_stage(seq, stage, "confirm", look, **picked(draft))
        assert saved["stored"] is True, saved
        if stage == stop:
            return


@pytest.mark.parametrize("case_id", [pytest.param("essay-cover-a1", id="essay-cover-a1")])
def test_programme_rows_print_only_when_the_brief_asks(case_id, workspace):
    """essay-cover-a1: Print a programme row only when the brief asks for that fact."""
    assert case_id == "essay-cover-a1"
    silent = _plant("CVR1001AA", _essay_brief())
    body = pack(silent)
    body["title"] = TITLE
    report = _report(TITLE, body["sections"])
    silent_lines = cover_lines(silent, body, report)
    for line in PROGRAMME_LINES:
        assert line not in silent_lines
    assert title_page_spec(_essay_brief())["programme"] is False

    asked = _plant("CVR1002AA", _essay_brief(programme=True))
    programme_spec = title_page_spec(_essay_brief(programme=True))
    assert programme_spec["programme"] is True
    assert programme_spec["name"] == "silent"
    assert "name" not in programme_spec["fields"]
    asked_body = pack(asked)
    asked_body["title"] = TITLE
    asked_body["student_name"] = NAME
    asked_lines = cover_lines(asked, asked_body, _report(TITLE, asked_body["sections"]))
    for line in PROGRAMME_LINES:
        assert line in asked_lines
    assert "Name:" not in asked_lines
    assert NAME not in asked_lines
    for phrase in (
        "Title page: name of the programme and partner institution.",
        "Title page: name of programme.",
        "Title page: programme's name and partner institution.",
        "Title page: programme\u2019s name.",
    ):
        spec = title_page_spec(f"Genre: essay\nQuestion: {QUESTION}\n{phrase}\n")
        assert spec["programme"] is True, phrase
        assert spec["name"] == "silent", phrase
        assert "name" not in spec["fields"], phrase
    of_the = _plant(
        "CVR1006AA",
        "Genre: essay\n"
        f"Question: {QUESTION}\n"
        "Title page: name of the programme and partner institution.\n",
    )
    of_the_body = pack(of_the)
    of_the_body["title"] = TITLE
    of_the_body["student_name"] = NAME
    of_the_lines = cover_lines(of_the, of_the_body, _report(TITLE, of_the_body["sections"]))
    for line in PROGRAMME_LINES:
        assert line in of_the_lines
    assert "Name:" not in of_the_lines
    assert NAME not in of_the_lines
    possessive = _plant(
        "CVR1007AA",
        "Genre: essay\n"
        f"Question: {QUESTION}\n"
        "Title page: programme's name and partner institution.\n",
    )
    possessive_body = pack(possessive)
    possessive_body["title"] = TITLE
    possessive_body["student_name"] = NAME
    possessive_lines = cover_lines(
        possessive, possessive_body, _report(TITLE, possessive_body["sections"])
    )
    for line in PROGRAMME_LINES:
        assert line in possessive_lines
    assert "Name:" not in possessive_lines
    student = title_page_spec("Title page: student name and the name of the programme.")
    assert student["name"] == "required"
    assert student["programme"] is True
    assert "name" in student["fields"]

    diary = _plant(
        "CVR1003AA",
        "Assignment title: Individual reflective diary\n"
        "Aim: Understand the practice by reflecting on your own decisions.\n"
        "Assignment task: Write two entries. Each entry names one decision and "
        "analyses it with theory.\n",
    )
    diary_body = {
        "essay_id": diary,
        "title": "Individual reflective diary",
        "assessment": "Individual reflective diary",
        "sections": [{"heading": "North occasion", "body": "One decision, with theory."}],
    }
    diary_report = _report("Individual reflective diary", diary_body["sections"])
    diary_lines = cover_lines(diary, diary_body, diary_report)
    for line in PROGRAMME_LINES:
        assert line not in diary_lines


@pytest.mark.parametrize("case_id", [pytest.param("essay-cover-a2", id="essay-cover-a2")])
def test_programme_values_are_not_filler(case_id, workspace):
    """essay-cover-a2: Do not print programme values as filler. The constant stays an example with no student identity."""
    assert case_id == "essay-cover-a2"
    brief = (
        "Genre: essay\n"
        f"Question: {QUESTION}\n"
        "Students follow a programme of study in the seminar.\n"
    )
    seq = _plant("CVR1004AA", brief)
    assert title_page_spec(brief)["programme"] is False
    body = pack(seq)
    body["title"] = TITLE
    lines = cover_lines(seq, body, _report(TITLE, body["sections"]))
    for line in PROGRAMME_LINES:
        assert line not in lines
    rows = cover_field_rows(seq, body, _report(TITLE, body["sections"]), essay=True)
    printed = cover_lines_from_field_rows(seq, body, rows)
    for line in PROGRAMME_LINES:
        assert line not in printed
    health = essay_health()
    assert health["programme"] == PROGRAMME
    assert health["programme"]["code"] == "PROG01"
    assert "student" not in json.dumps(health["programme"]).casefold()


@pytest.mark.parametrize("case_id", [pytest.param("essay-cover-a3", id="essay-cover-a3")])
def test_an_unmapped_brief_keeps_the_rows_it_asks_for(case_id, workspace):
    """essay-cover-a3: An unmapped brief still prints the programme and title-page rows it asks for."""
    assert case_id == "essay-cover-a3"
    from essay_writer.assignment_gate import read_assignment

    brief = (
        "Genre: fieldnote\n"
        f"Question: {QUESTION}\n"
        "Title page: programme name and partner institution.\n"
        "Title page: module title and registration number.\n"
    )
    seq = _plant("CVR1005AA", brief)
    record = read_assignment(seq)
    assert record["active"] is True
    assert record["mapped"] is False
    spec = title_page_spec(brief)
    assert spec["programme"] is True
    assert spec["name"] == "silent"
    body = pack(seq)
    body["title"] = TITLE
    body["student_name"] = NAME
    body["registration_number"] = NUMBER
    lines = cover_lines(seq, body, _report(TITLE, body["sections"]))
    assert lines[0] == TITLE
    assert lines != [TITLE]
    for line in PROGRAMME_LINES:
        assert line in lines
    assert f"Registration number: {NUMBER}" in lines
    assert "Name:" not in lines
    assert NAME not in lines


@pytest.mark.parametrize("case_id", [pytest.param("essay-cover-b1", id="essay-cover-b1")])
def test_the_conclusion_stays_on_the_pack_and_in_chat(case_id, workspace):
    """essay-cover-b1: Keep the conclusion on the pack. Say it in chat when Word is written. Do not print it on the cover."""
    assert case_id == "essay-cover-b1"
    write_upload(workspace)
    seq = open_sequence()
    essay_research_summary(seq, QUESTION, "draft", [source()])
    essay_research_summary(
        seq,
        QUESTION,
        "confirm",
        [source()],
        cardDigest=card_digest_for(seq, "essay.research.summary"),
    )
    noted = pack()
    essay_pack_validate(seq, noted, "draft")
    essay_pack_validate(seq, noted, "confirm")
    preview = essay_pack_render_word(seq, noted, "draft")
    assert preview["wrote"] is False
    assert COVER_NOTED not in preview["cover"]
    assert COVER_OPEN not in preview["cover"]
    written = essay_pack_render_word(seq, noted, "confirm")
    assert written["wrote"] is True
    assert noted["conclusion"] == "noted"
    assert COVER_NOTED not in written["cover"]
    assert COVER_OPEN not in written["cover"]
    assert written.get("conclusion_line") == NOTED
    assert NOTED in written["next"]
    assert NOTED in written["chat"]
    target = workspace / "Essay-writer" / "MOD1004AA" / "sequences" / "1" / "output" / f"{seq}.docx"
    xml = zipfile.ZipFile(target).read("word/document.xml").decode("utf-8")
    assert COVER_NOTED not in xml
    assert COVER_OPEN not in xml

    opened = pack(conclusion="open")
    essay_pack_validate(seq, opened, "draft")
    essay_pack_validate(seq, opened, "confirm")
    open_preview = essay_pack_render_word(seq, opened, "draft")
    assert open_preview["wrote"] is False
    assert COVER_OPEN not in open_preview["cover"]
    open_written = essay_pack_render_word(seq, opened, "confirm")
    assert open_written["wrote"] is True, open_written
    assert opened["conclusion"] == "open"
    assert COVER_OPEN not in open_written["cover"]
    assert COVER_NOTED not in open_written["cover"]
    assert open_written.get("conclusion_line") == OPEN
    assert OPEN in open_written["next"]
    fresh = zipfile.ZipFile(target).read("word/document.xml").decode("utf-8")
    assert COVER_OPEN not in fresh
    assert COVER_NOTED not in fresh


@pytest.mark.parametrize("case_id", [pytest.param("essay-cover-b2", id="essay-cover-b2")])
def test_hydration_reads_the_pack_field(case_id, workspace):
    """essay-cover-b2: The conclusion round-trip uses the pack field. The cover sentence is not required."""
    assert case_id == "essay-cover-b2"
    seq = _plant("CVR1005AA", _essay_brief())
    body = pack(seq)
    body["title"] = TITLE
    body["conclusion"] = "open"
    lines = cover_lines(seq, body, _report(TITLE, body["sections"]))
    assert COVER_NOTED not in lines
    assert COVER_OPEN not in lines
    kept = _hydrate_pack_from_docx_cover(seq, lines, body)
    assert kept["conclusion"] == "open"
    noted = dict(body)
    noted["conclusion"] = "noted"
    old_cover = [COVER_OPEN, TITLE]
    assert _hydrate_pack_from_docx_cover(seq, old_cover, noted)["conclusion"] == "noted"
    empty = {"title": "Draft", "essay_id": seq}
    assert _hydrate_pack_from_docx_cover(seq, [COVER_OPEN], empty)["conclusion"] == "open"
    path = work_dir(seq) / "output" / f"{seq}.docx"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"PK")
    state = load_state(seq)
    state["saved_pack"] = {"essay_id": seq, "conclusion": "open", "title": TITLE}
    save_state(seq, state)
    reply = {"next": "Open the folder and keep a copy. This tool does not submit."}
    _say_written_conclusion(reply, seq)
    assert reply["conclusion_line"] == OPEN
    assert OPEN in reply["next"]
    assert COVER_OPEN not in reply["next"]
    assert COVER_NOTED not in reply["next"]


@pytest.mark.parametrize("case_id", [pytest.param("essay-cover-c1", id="essay-cover-c1")])
def test_a_real_stored_title_is_the_first_cover_line(case_id, workspace):
    """essay-cover-c1: A real stored title is the first visible cover line even when the brief has no Title line."""
    assert case_id == "essay-cover-c1"
    brief = _essay_brief()
    assert "Title:" not in brief
    assert "Assignment title:" not in brief
    seq = _plant("CVR1006AA", brief)
    body = pack(seq)
    body["title"] = TITLE
    body["assessment"] = "Individual report"
    report = _report(TITLE, body["sections"])
    lines = cover_lines(seq, body, report)
    assert lines[0] == TITLE
    assert lines.count(TITLE) == 1
    assert QUESTION not in lines
    path = work_dir(seq) / "output" / f"{seq}.docx"
    write_docx(seq, body, report, path)
    cover, headings = _visible(path)
    assert cover[0] == TITLE
    assert headings[0] == "Introduction"
    assert "References" in headings
    document = Document(str(path))
    assert document.core_properties.title == TITLE
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    assert xml.index(TITLE) < xml.index("Introduction")

    report_only = pack(seq)
    report_only["title"] = "Draft"
    report_only["assessment"] = "Individual report"
    stored = "A title kept on the report"
    only = cover_lines(seq, report_only, _report(stored, report_only["sections"]))
    assert only[0] == stored
    assert "Draft" not in only


@pytest.mark.parametrize("case_id", [pytest.param("essay-cover-c2", id="essay-cover-c2")])
def test_a_placeholder_title_stays_off_the_cover(case_id, workspace):
    """essay-cover-c2: A placeholder title stays off the cover. The question is not turned into a title."""
    assert case_id == "essay-cover-c2"
    seq = _plant("CVR1007AA", _essay_brief())
    body = pack(seq)
    body["title"] = "Draft"
    body["assessment"] = "Draft"
    sections = [
        {"heading": "Introduction", "body": "The corridor depends on a narrow strait."},
        {"heading": "Supply chain context", "body": "One named chain is in scope."},
        {"heading": "Conclusion", "body": "The strait still carries the chain."},
    ]
    body["sections"] = sections
    report = _report("Draft", sections)
    lines = cover_lines(seq, body, report)
    assert "Draft" not in lines
    assert QUESTION not in lines
    assert all(not line.startswith("Conclusion:") for line in lines)
    path = work_dir(seq) / "output" / f"{seq}.docx"
    write_docx(seq, body, report, path)
    cover, headings = _visible(path)
    assert QUESTION not in cover
    assert "Draft" not in cover
    document = Document(str(path))
    assert document.core_properties.title != "Draft"
    assert document.core_properties.title == seq
    assert headings[:3] == ["Introduction", "Supply chain context", "Conclusion"]
    assert headings[-1] == "References"


@pytest.mark.parametrize("case_id", [pytest.param("essay-cover-c3", id="essay-cover-c3")])
def test_identity_stays_with_the_brief(case_id, workspace):
    """essay-cover-c3: No student name unless the brief asks, and registration only when the brief asks."""
    assert case_id == "essay-cover-c3"
    seq = _plant("CVR1008AA", _essay_brief())
    body = pack(seq)
    body["title"] = TITLE
    body["student_name"] = NAME
    body["student_number"] = NUMBER
    report = _report(TITLE, body["sections"])
    lines = cover_lines(seq, body, report)
    assert NAME not in lines
    assert NUMBER not in lines
    assert lines[0] == TITLE
    path = work_dir(seq) / "output" / f"{seq}.docx"
    write_docx(seq, body, report, path)
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    assert NAME not in xml
    assert NUMBER not in xml

    asked = _plant("CVR1009AA", _essay_brief(registration=True))
    asked_body = pack(asked)
    asked_body["title"] = TITLE
    asked_body["student_name"] = NAME
    asked_body["registration_number"] = NUMBER
    asked_lines = cover_lines(asked, asked_body, _report(TITLE, asked_body["sections"]))
    assert f"Registration number: {NUMBER}" in asked_lines
    assert NAME not in asked_lines
    assert asked_lines[0] == TITLE


@pytest.mark.parametrize("case_id", [pytest.param("essay-cover-d1", id="essay-cover-d1")])
def test_parent_packs_still_hold(case_id, workspace):
    """essay-cover-d1: The promise cases and the stored-answer cases still hold. The brief file stays."""
    assert case_id == "essay-cover-d1"
    promise = (REPO / "tests" / "test_essay_promise.py").read_text(encoding="utf-8")
    answers = (REPO / "tests" / "test_stored_brief_answer.py").read_text(encoding="utf-8")
    for name in PROMISE_IDS:
        assert promise.count(f'id="{name}"') == 1
        assert promise.count(f'"""{name}:') == 1
    for name in ASK_IDS:
        assert answers.count(f'id="{name}"') == 1
        assert answers.count(f'"""{name}:') == 1
    assert stage_title("2", None) == "Establish the focus"
    assert stage_title("3", None) == "Write the plan"
    assert stage_title("10") == "Finish the Word file"
    assert "does not submit" in confirm_line("10", None)
    assert stage_uses_confirm_card("5") is False
    assert advances_without_confirm("5") == "6"
    assert STAGE5_SAVE_LINE in saved_next("5", stage_title("5"))
    assert 'version = "0.9.3"' in (REPO / "pyproject.toml").read_text(encoding="utf-8")

    seq = _plant("CVR1010AA", "Module code: CVR1010AA\nStudents meet on Tuesdays.\n")
    folder = essay_dir("CVR1010AA")
    brief = folder / "brief.md"
    before = brief.read_bytes()
    reply = essay_stage(
        seq,
        "1",
        "draft",
        "A sentence of my own for this stage.",
        formatAnswer="report",
        questionAnswer="Evaluate how Northwind Components could close the material loop.",
    )
    assert reply["ok"] is True, reply
    assert reply.get("refused") != "guidance-only"
    assert brief.read_bytes() == before
    from essay_writer.assignment_gate import read_assignment

    seen = read_assignment(seq)
    assert seen["format"] == "report"
    assert seen["question"] == "Evaluate how Northwind Components could close the material loop."
    assert stage_title("2", None) == "Establish the focus"


@pytest.mark.parametrize("case_id", [pytest.param("essay-cover-e1", id="essay-cover-e1")])
def test_a_failed_cover_write_keeps_the_rules(case_id, workspace, monkeypatch):
    """essay-cover-e1: A failed cover write leaves no filler, no cover conclusion, and no invented title."""
    assert case_id == "essay-cover-e1"
    seq = _plant("CVR1011AA", _essay_brief())
    write_upload(workspace, essay_id="CVR1011AA")
    folder = essay_dir("CVR1011AA")
    brief = folder / "brief.md"
    before = brief.read_bytes()
    meta = folder / "brief-meta.json"
    _save_through(seq, "5")
    assert advances_without_confirm("5") == "6"
    assert stage_uses_confirm_card("5") is False
    assert brief.read_bytes() == before
    assert not meta.exists()

    body = pack(seq)
    body["title"] = TITLE
    body["conclusion"] = "open"
    body["student_name"] = NAME
    body["student_number"] = NUMBER
    report = _report(TITLE, body["sections"])
    lines = cover_lines(seq, body, report)
    assert lines[0] == TITLE
    assert QUESTION not in lines
    for line in PROGRAMME_LINES:
        assert line not in lines
    assert COVER_NOTED not in lines
    assert COVER_OPEN not in lines
    assert NAME not in lines
    assert NUMBER not in lines

    def fail_save(self, *args, **kwargs):
        raise OSError("disk full")

    from docx.document import Document as DocxDocument

    monkeypatch.setattr(DocxDocument, "save", fail_save)
    path = work_dir(seq) / "output" / f"{seq}.docx"
    with pytest.raises(OSError, match="disk full"):
        write_docx(seq, body, report, path)
    assert not path.is_file()
    assert not path.with_suffix(".docx.tmp").exists()
    assert not any(item.name == path.name for item in path.parent.glob("*.docx"))
    assert brief.read_bytes() == before
    assert not meta.exists()
    assert cover_lines(seq, body, report)[0] == TITLE
    assert advances_without_confirm("5") == "6"
    assert stage_uses_confirm_card("5") is False
