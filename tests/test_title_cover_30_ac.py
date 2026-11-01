"""Bug #30. The shared Word cover prints a required registration number.

AC1: the stage 10 Word title page includes the registration number when the brief asks.
AC2: that title page omits the student name.
AC5: page numbers stay lower right when the brief asks.
Build covered: Cursor and Grok Build share the stage door and write_docx.
"""

import inspect
import zipfile
from pathlib import Path

from helpers import mac_handoff_sequence_dir, with_word_references

from essay_writer.brief_contract import (
    pack_with_registration,
    remember_registration,
    word_contract_refusal,
)
from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch, stage_host_launch
from essay_writer.diary import diary_cover_lines, title_page_spec
from essay_writer.late_chain import write_stage10
from essay_writer.paths import essay_dir, work_dir
from essay_writer.setup import SHELL_CURSOR, SHELL_GROK_BUILD
from essay_writer.shells import cursor_shell, front_office, front_office_call
from essay_writer.stage_llm import stage_settings
from essay_writer.stage_track import essay_stage
from essay_writer.state import load_state, save_state
from essay_writer.word import cover_lines, write_docx

NUMBER = "445566"
NAME = "Ada Example"
MODULE = "RPT5001AA"
BRIEF = """
Assignment title: Individual reflective diary

Module title: Practice module
Module code: RPT5001AA

Aim: Understand the practice by reflecting on your own decisions.

Assignment task: Write four entries. Each entry names one decision and critically analyses it with theory and evidence.

Title page: module title, module code, assignment title, and the word count.
Include your student ID.
The name stays off the title page and the file.

Pages: Arial, size 12. 2.5 cm margins on all sides. Page numbers in the lower right.
"""
HEADING = """
Title page
- module title
- module code
- assignment title
- student ID
- word count
"""


def _brief(module: str) -> None:
    folder = essay_dir(module)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(BRIEF, encoding="utf-8")


def _kick(module: str) -> dict:
    args = {"module": module, "confirmPhase": "draft"}
    draft = front_office_call("essay.sequence.new", args)
    assert draft["ok"] is True, draft
    assert "card" not in draft
    args["confirmPhase"] = "confirm"
    opened = front_office_call("essay.sequence.new", args)
    assert opened["ok"] is True, opened
    return opened


def _title_and_document(path: Path) -> tuple[str, str]:
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    return xml.split('w:type="page"', 1)[0], xml


def _footer(path: Path) -> str:
    return zipfile.ZipFile(path).read("word/footer1.xml").decode("utf-8")


def test_ac1_ac2_ac5_registration_on_the_title_page_without_the_name(workspace, monkeypatch, tmp_path):
    """AC1, AC2, AC5. Student ID is a registration ask. The name stays off. The page number stays right."""
    asked = title_page_spec(BRIEF)
    assert asked["registration"] is True
    assert "registration" in asked["fields"]
    assert asked["name"] == "forbidden"
    headed = title_page_spec(HEADING)
    assert headed["registration"] is True
    assert "registration" in headed["fields"]
    refused = title_page_spec("Title page: module title.\nDo not include your student ID.")
    assert refused["registration"] is False

    documents = tmp_path / "Documents"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    _brief(MODULE)
    opened = _kick(MODULE)
    seq = opened["sequence_id"]
    assert remember_registration(seq, NUMBER) == NUMBER
    pack = {
        "essay_id": seq,
        "title": "Individual reflective diary",
        "referencing": "harvard",
        "assessment": "Individual reflective diary",
        "module_title": "Practice module",
        "conclusion": "noted",
        "student_name": NAME,
        "sections": [
            {
                "heading": "One decision",
                "body": "A decision, with theory, on the practice the brief names.",
            }
        ],
    }
    report = {
        "title": "Individual reflective diary",
        "word_count": {"counted": 40, "stated": 2000},
        "sections": pack["sections"],
        "figures": [],
        "tables": [],
        "sources": [],
    }
    stage6 = work_dir(seq) / "output" / f"{seq}.docx"
    write_docx(seq, pack, report, stage6)
    state = load_state(seq)
    bare = dict(pack)
    assert "registration_number" not in bare
    state["saved_pack"] = with_word_references(bare)
    save_state(seq, state)
    final = write_stage10(seq)
    assert final["copied"] is True, final
    final_path = mac_handoff_sequence_dir(documents, seq) / f"{MODULE}-final.docx"
    assert final_path.is_file()
    for path in (stage6, final_path):
        title, document = _title_and_document(path)
        assert "Practice module" in title
        assert MODULE in title
        assert "Individual reflective diary" in title
        assert f"Registration number: {NUMBER}" in title
        assert "Counted words:" in title
        assert "Teaching partner" not in title
        assert NAME not in title
        assert NAME not in document
        footer = _footer(path)
        assert "PAGE" in footer
        assert "instrText" in footer
        assert 'w:val="right"' in footer


def test_build_covered_cursor_and_grok_build_share_the_cover(monkeypatch):
    """Build covered. Cursor and Grok Build share title_page_spec, the cover write, and word_contract."""
    assert cursor_shell()["handlers"]["essay.stage"] is front_office()["handlers"]["essay.stage"]
    assert "write_docx(" in inspect.getsource(write_stage10)
    assert "word_contract_refusal(" in inspect.getsource(write_stage10)
    assert "cover_lines(" in inspect.getsource(write_docx)
    assert "cover_field_rows(" in inspect.getsource(cover_lines)
    assert "cover_lines_from_field_rows(" in inspect.getsource(cover_lines)
    assert "cover_field_rows(" in inspect.getsource(diary_cover_lines)
    assert "cover_lines_from_field_rows(" in inspect.getsource(diary_cover_lines)
    assert "def title_page_spec" not in inspect.getsource(stage_launch)
    assert "def title_page_spec" not in inspect.getsource(cursor_stage_launch)
    assert "def word_contract_refusal" not in inspect.getsource(stage_launch)
    assert "def cover_lines" not in inspect.getsource(cursor_stage_launch)
    assert "return _commit_with_next_card(" in inspect.getsource(essay_stage)
    assert "_commit_with_next_card" not in inspect.getsource(stage_launch)
    assert "_commit_with_next_card" not in inspect.getsource(cursor_stage_launch)
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_CURSOR)
    cursor = stage_host_launch("10")
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_GROK_BUILD)
    grok = stage_host_launch("10")
    assert cursor["settings"]["rules"] == grok["settings"]["rules"] == stage_settings("10")["rules"]


_DIARY_BODY = """
Assignment title: Individual reflective diary

Module title: Practice module
Module code: {module}

Aim: Understand the practice by reflecting on your own decisions.

Assignment task: Write four entries. Each entry names one decision and critically analyses it with theory and evidence.
"""


def _diary(module: str, title_page: str, extra: str = "") -> str:
    return (
        _DIARY_BODY.format(module=module)
        + "\n"
        + title_page.strip()
        + "\n"
        + extra
    )


def _write(module: str, text: str) -> None:
    folder = essay_dir(module)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(text, encoding="utf-8")


def _pack(seq: str) -> dict:
    return {
        "essay_id": seq,
        "title": "Individual reflective diary",
        "referencing": "harvard",
        "assessment": "Individual reflective diary",
        "module_title": "Practice module",
        "conclusion": "noted",
        "sections": [
            {
                "heading": "One decision",
                "body": "A decision, with theory, on the practice the brief names.",
            }
        ],
    }


def _report(pack: dict) -> dict:
    return {
        "title": "Individual reflective diary",
        "word_count": {"counted": 40, "stated": 2000},
        "sections": pack["sections"],
        "figures": [],
        "tables": [],
        "sources": [],
    }


def _paragraphs(path: Path) -> list[str]:
    from docx import Document

    return [paragraph.text for paragraph in Document(str(path)).paragraphs]


def test_ac1_do_not_include_your_name_is_forbidden(workspace, monkeypatch, tmp_path):
    """AC1. 'DO NOT include your name' forbids the name. A stored registration is enough."""
    one_line = (
        "Title page: module title, registration number. DO NOT include your name."
    )
    asked = title_page_spec(one_line)
    assert asked["name"] == "forbidden"
    assert asked["name"] != "required"
    assert asked["registration"] is True
    assert "name" not in asked["fields"]

    headed = title_page_spec(
        "Title page\n- module title\n- registration number\n- DO NOT include your name\n"
    )
    assert headed["name"] == "forbidden"
    assert "name" not in headed["fields"]
    assert headed["registration"] is True

    for phrase in (
        "Do not include your name.",
        "Please do not put your name on the cover.",
        "Your name must not appear.",
    ):
        spec = title_page_spec(f"Title page: registration number. {phrase}")
        assert spec["name"] == "forbidden", phrase
        assert spec["registration"] is True

    only_registration = title_page_spec(
        "Title page: registration number.\nDO NOT include your name.\n"
    )
    assert only_registration["fields"] == ["registration"]
    assert only_registration["labels"] == []
    positive = title_page_spec("Title page: your name and registration number.")
    assert positive["name"] == "required"
    assert positive["registration"] is True

    documents = tmp_path / "Documents"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    brief = _diary(
        MODULE,
        "Title page: module title, module code, assignment title, registration number, "
        "and the word count. DO NOT include your name.",
    )
    _write(MODULE, brief)
    opened = _kick(MODULE)
    seq = opened["sequence_id"]
    assert remember_registration(seq, NUMBER) == NUMBER
    pack = _pack(seq)
    assert "student_name" not in pack
    filled = pack_with_registration(seq, pack)
    blocked = word_contract_refusal(seq, filled)
    assert blocked is None, blocked
    state = load_state(seq)
    state["saved_pack"] = with_word_references(dict(pack))
    save_state(seq, state)
    final = write_stage10(seq)
    assert final.get("refused") != "title-page"
    assert "name" not in (final.get("missing_fields") or [])
    assert final["copied"] is True, final

    _write(
        MODULE,
        _diary(MODULE, "Title page: registration number.\nDO NOT include your name."),
    )
    only_lines = diary_cover_lines(seq, filled, _report(pack))
    assert only_lines == [f"Registration number: {NUMBER}", seq]
    assert "Practice module" not in only_lines
    assert "Module title:" not in only_lines
    assert "Counted words:" not in only_lines


def test_ac2_asked_address_is_a_blank_label(workspace, monkeypatch, tmp_path):
    """AC2. An asked address is labeled. The value is not invented."""
    line = title_page_spec(
        "Title page: module title, registration number, and student address.\n"
        "DO NOT include your name.\n"
    )
    assert line["labels"] == ["Student address"]
    assert line["name"] == "forbidden"
    assert "registration" in line["fields"]

    table = _diary(
        MODULE,
        "Title page: module title, module code, assignment title, registration number, "
        "and the word count.\n"
        "DO NOT include your name.",
        """
# Marking criteria/feedback form

| Criterion | 0-39 | 70+ |
| --- | --- | --- |
| Title page | thin | student address |
""",
    )
    assert "student address" not in table.split("# Marking", 1)[0].casefold()
    table_spec = title_page_spec(table)
    assert table_spec["labels"] == ["Student address"]
    assert table_spec["name"] == "forbidden"

    both = title_page_spec(
        "Title page: student address.\n"
        "# Marking criteria\n\n"
        "| Criterion | 0-39 | 70+ |\n"
        "| --- | --- | --- |\n"
        "| Title page | thin | student address |\n"
    )
    assert both["labels"] == ["Student address"]

    documents = tmp_path / "Documents"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    brief = _diary(
        MODULE,
        "Title page: module title, module code, assignment title, registration number, "
        "word count, and student address.\n"
        "DO NOT include your name.",
    )
    _write(MODULE, brief)
    opened = _kick(MODULE)
    seq = opened["sequence_id"]
    assert remember_registration(seq, NUMBER) == NUMBER
    pack = _pack(seq)
    report = _report(pack)
    path = work_dir(seq) / "output" / f"{seq}.docx"
    write_docx(seq, pack, report, path)
    paragraphs = _paragraphs(path)
    assert "Student address:" in paragraphs
    assert all(
        item == "Student address:"
        for item in paragraphs
        if item.startswith("Student address:")
    )
    assert NUMBER not in "\n".join(
        item for item in paragraphs if item.startswith("Student address:")
    )
    assert NAME not in "\n".join(paragraphs)

    _write(MODULE, table)
    table_lines = diary_cover_lines(seq, pack_with_registration(seq, pack), report)
    assert "Student address:" in table_lines
    assert all(
        item == "Student address:"
        for item in table_lines
        if item.startswith("Student address:")
    )


def test_ac3_unasked_address_is_absent(workspace, monkeypatch, tmp_path):
    """AC3. A brief that does not ask for an address does not print one."""
    assert title_page_spec(BRIEF)["labels"] == []
    documents = tmp_path / "Documents"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    _brief(MODULE)
    opened = _kick(MODULE)
    seq = opened["sequence_id"]
    assert remember_registration(seq, NUMBER) == NUMBER
    pack = _pack(seq)
    path = work_dir(seq) / "output" / f"{seq}.docx"
    write_docx(seq, pack, _report(pack), path)
    paragraphs = _paragraphs(path)
    assert not any("address" in item.casefold() for item in paragraphs)
    assert "Student address:" not in paragraphs


def test_ac4_pbs_title_page_accepts_without_a_name(workspace, monkeypatch, tmp_path):
    """AC4. Module, code, assignment, registration, and word count. No name refusal."""
    brief = _diary(
        MODULE,
        "Title page\n"
        "- module title\n"
        "- module code\n"
        "- assignment title\n"
        "- registration number\n"
        "- word count\n"
        "DO NOT include your name\n",
    )
    spec = title_page_spec(brief)
    assert spec["name"] == "forbidden"
    assert spec["registration"] is True
    for key in ("module_title", "module_code", "assignment_title", "registration", "word_count"):
        assert key in spec["fields"]
    assert "name" not in spec["fields"]

    documents = tmp_path / "Documents"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    _write(MODULE, brief)
    opened = _kick(MODULE)
    seq = opened["sequence_id"]
    assert remember_registration(seq, NUMBER) == NUMBER
    pack = _pack(seq)
    report = _report(pack)
    path = work_dir(seq) / "output" / f"{seq}.docx"
    write_docx(seq, pack, report, path)
    paragraphs = _paragraphs(path)
    assert "Practice module" in paragraphs
    assert MODULE in paragraphs
    assert "Individual reflective diary" in paragraphs
    assert f"Registration number: {NUMBER}" in paragraphs
    assert any(item.startswith("Counted words:") for item in paragraphs)
    assert NAME not in paragraphs
    assert not any(item.casefold().startswith("name:") for item in paragraphs)
    state = load_state(seq)
    state["saved_pack"] = with_word_references(dict(pack))
    save_state(seq, state)
    final = write_stage10(seq)
    assert final.get("refused") != "title-page", final
    assert "missing the name" not in (final.get("reason") or "").casefold()
    assert final["copied"] is True, final
    final_path = mac_handoff_sequence_dir(documents, seq) / f"{MODULE}-final.docx"
    final_paragraphs = _paragraphs(final_path)
    assert f"Registration number: {NUMBER}" in final_paragraphs
    assert NAME not in final_paragraphs
