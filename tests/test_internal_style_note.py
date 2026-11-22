"""Plymouth Cite Them Right is Harvard referencing, said in the internal note only.

The reading miss this covers is an agent or checker one, not a gap in the essay.
The note the MCP-running agent reads says the two names are one style, so a
later check does not treat a missing Plymouth switch as a product gap. Nothing
here reaches the student: no chat copy, no screen copy, and no method
announcement in the Word file.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from helpers import (
    TOPIC,
    card_digest_for,
    open_sequence,
    pack,
    source,
    with_word_references,
    write_upload,
)

from essay_writer.health import essay_health
from essay_writer.paths import work_dir
from essay_writer.prompt_loader import text
from essay_writer.research import essay_research_summary
from essay_writer.seats import seat_reading
from essay_writer.server import INSTRUCTIONS, house_instructions
from essay_writer.shells import cursor_shell, front_office
from essay_writer.student_turns import FIRST_TURN_CARD
from essay_writer.validate import essay_pack_validate
from essay_writer.word import word_manifest, write_docx

REPO = Path(__file__).resolve().parents[1]
HANDBOOK = REPO / "docs" / "referencing-harvard.md"
SEAT = REPO / "src" / "essay_writer" / "prompts" / "seats" / "write.md"
SECTION = "## Plymouth Cite Them Right"
IS_ONE_STYLE = "Plymouth Cite Them Right **is** Harvard referencing."


def _section(note: str) -> str:
    return note.split(SECTION, 1)[1].split("\n## ", 1)[0]


@pytest.mark.parametrize("case_id", [pytest.param("ctr-note-a1", id="ctr-note-a1")])
def test_the_internal_note_names_the_style_as_one(case_id: str) -> None:
    """AC-ctr-1: the note the MCP-running agent reads makes Plymouth Cite Them Right Harvard."""
    assert case_id == "ctr-note-a1"
    note = _section(HANDBOOK.read_text(encoding="utf-8"))
    assert IS_ONE_STYLE in note
    assert "not a second style" in note
    assert "Harvard" in note
    seat = seat_reading("write")
    assert IS_ONE_STYLE in seat
    assert SECTION in seat
    assert "EndNote style to select: **Harvard**" in seat
    assert IS_ONE_STYLE in INSTRUCTIONS
    assert IS_ONE_STYLE in house_instructions()


@pytest.mark.parametrize("case_id", [pytest.param("ctr-note-a2", id="ctr-note-a2")])
def test_the_internal_note_says_no_switch_is_missing(case_id: str) -> None:
    """AC-ctr-2: the note says the absent Plymouth switch is not a product gap."""
    assert case_id == "ctr-note-a2"
    note = _section(HANDBOOK.read_text(encoding="utf-8"))
    assert "no separate Plymouth style to switch on" in note
    assert "not a missing feature" in note
    assert "Nothing about the referencing changes" in note
    assert "internal guidance for the agent" in note
    lines = [line for line in note.splitlines() if line.strip()]
    assert len(lines) <= 6, "the note stays short and is not a lecture"
    assert all(len(line) <= 260 for line in lines)


@pytest.mark.parametrize("case_id", [pytest.param("ctr-note-a3", id="ctr-note-a3")])
def test_the_helper_note_says_no_switch_is_a_gap(case_id: str) -> None:
    """AC-ctr-2: the tester note says a missing Plymouth switch is not a product gap."""
    assert case_id == "ctr-note-a3"
    testing = (REPO / "docs" / "testing.md").read_text(encoding="utf-8")
    assert "## Plymouth Cite Them Right" in testing
    raw = testing.split("## Plymouth Cite Them Right", 1)[1].split("\n## ", 1)[0]
    note = " ".join(raw.split())
    assert "Plymouth Cite Them Right is the Harvard style" in note
    assert "not a product gap" in note
    assert "does not print it" in note
    assert "tests/test_internal_style_note.py" in note


@pytest.mark.parametrize("case_id", [pytest.param("ctr-note-a4", id="ctr-note-a4")])
def test_the_note_stays_internal_and_is_not_student_documentation(case_id: str) -> None:
    """AC-ctr-2: the note is internal, not student documentation."""
    assert case_id == "ctr-note-a4"
    note = _section(HANDBOOK.read_text(encoding="utf-8"))
    assert "The Word file does not print it" in note
    glossary = (REPO / "docs" / "GLOSSARY.md").read_text(encoding="utf-8")
    student_terms = glossary.split("## Student-facing terms", 1)[1]
    assert "Cite Them Right" not in student_terms
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "Cite Them Right" not in readme


def _student_visible_strings() -> dict[str, str]:
    """Every student-facing line the product speaks or prints before a Word file."""
    names = (
        "opening_new",
        "opening_continue",
        "opening_roll",
        "stage5_save_line",
        "redirect_whole",
        "redirect_order",
        "redirect_voice",
        "redirect_close",
        "stage6_lead_in",
        "stage7_line",
        "stage9_own_words",
    )
    found = {name: text("front_office/chat.md", name) for name in names}
    found["first_turn_card"] = FIRST_TURN_CARD
    found["health_first_turn_card"] = str(essay_health()["first_turn_card"])
    return found


def _no_note_copy(value: str) -> bool:
    folded = value.casefold()
    return "plymouth" not in folded and "cite them right" not in folded


@pytest.mark.parametrize("case_id", [pytest.param("ctr-note-b1", id="ctr-note-b1")])
def test_no_new_student_chat_or_screen_copy_is_added(case_id: str, workspace) -> None:
    """AC-ctr-3: no student-visible chat or screen copy names the style."""
    assert case_id == "ctr-note-b1"
    for name, line in _student_visible_strings().items():
        assert _no_note_copy(line), name
    assert _no_note_copy(FIRST_TURN_CARD)
    assert _no_note_copy(" ".join(essay_health().get("opening", [])))


@pytest.mark.parametrize("case_id", [pytest.param("ctr-note-b2", id="ctr-note-b2")])
def test_the_word_file_does_not_announce_the_method(case_id: str, workspace) -> None:
    """AC-ctr-3: the exported Word file carries citations, not a method announcement."""
    assert case_id == "ctr-note-b2"
    write_upload(workspace)
    seq = open_sequence()
    essay_research_summary(seq, TOPIC, "draft", [source()])
    stored = essay_research_summary(
        seq,
        TOPIC,
        "confirm",
        [source()],
        cardDigest=card_digest_for(seq, "essay.research.summary"),
    )
    assert stored["stored"] is True
    body = pack()
    assert essay_pack_validate(seq, body, "draft").get("ok") is True
    assert essay_pack_validate(seq, body, "confirm").get("stored") is True
    prepared, report = word_manifest(seq, with_word_references(body), product_log=False)
    target = work_dir(seq) / "output" / f"{seq}.docx"
    target.parent.mkdir(parents=True, exist_ok=True)
    write_docx(seq, prepared, report, target)
    assert target.is_file()
    xml = zipfile.ZipFile(target).read("word/document.xml").decode("utf-8")
    folded = xml.casefold()
    for phrase in ("plymouth", "cite them right", "harvard", "referencing method"):
        assert phrase not in folded, phrase
    assert "References" in xml
    assert "(Smith, 2020)" in xml


@pytest.mark.parametrize("case_id", [pytest.param("ctr-note-c1", id="ctr-note-c1")])
def test_both_shells_read_the_same_internal_note(case_id: str) -> None:
    """AC-ctr-4: Cursor and Grok Bot run one command, so both read this note."""
    assert case_id == "ctr-note-c1"
    grok = front_office()
    cursor = cursor_shell()
    assert grok["entry"] == cursor["entry"]
    assert grok["entry"]["command"] == "essay-writer"
    assert grok["handlers"] is cursor["handlers"]
    assert IS_ONE_STYLE in grok["briefing"]
    assert IS_ONE_STYLE in house_instructions()
    assert SEAT.is_file()
