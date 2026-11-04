"""Cut 1 leftovers. Shared requirement list, cover fields, and no study-table fill.

AC1: asked custom title-page field on essay Word cover (Word bytes).
AC2: empty asked field blocks Word confirm (door).
AC3: brief-named section appears; not invented (door).
AC4: silent MAR brief names gaps on stage doors; no study-table section fill (door).
AC5: Cursor and Grok Build share assignment_requirements (shared function).
"""

import zipfile

from helpers import open_sequence, pack, picked, write_upload

from essay_writer.assignment_gate import (
    assignment_requirements,
    assignment_silence_gaps,
    study_defaults_allowed,
)
from essay_writer.build_office import assignment_requirements as build_requirements
from essay_writer.cursor_office import assignment_requirements as cursor_requirements
from essay_writer.diary import section_plan_for, title_page_spec
from essay_writer.paths import essay_dir, work_dir
from essay_writer.specialists.grok_bot import basics_pass_lines
from essay_writer.stage_llm import brief_genre
from essay_writer.stage_track import essay_stage
from essay_writer.textutil import (
    BRIEF_GENRE,
    BRIEF_WORD_RULES,
    genre_for,
    word_rules_for,
)
from essay_writer.word import essay_pack_render_word

ESSAY_BRIEF = (
    "Genre: essay\n"
    "Question: How do chokepoints constrain the corridor?\n"
    "Title page: student number and student address.\n"
)
MAR_MODULES = ("MOD1011AA", "MOD1008AA", "MOD1004AA")
FORMAT_GAP = "Format: the brief does not name one."
QUESTION_GAP = "Question: the brief does not name one."
WORD_BAND_GAP = "Word band: the brief does not name one."
NUMBER = "556677"
ADDRESS = "9 Harbour Road"


def _brief(module: str, text: str) -> None:
    folder = essay_dir(module)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(text, encoding="utf-8")


def _silent_brief(module: str) -> str:
    return f"Module code: {module}\n"


def _stage_look(seq: str) -> str:
    return "\n".join(basics_pass_lines(seq)) + "\nInitial notes on the task."


def _advance_to_stage_three(seq: str, look: str) -> None:
    saved_one = essay_stage(seq, "1", "draft", look)
    assert saved_one["ok"] is True, saved_one
    essay_stage(seq, "1", "confirm", look, **picked(saved_one))
    saved_two = essay_stage(
        seq,
        "2",
        "draft",
        look + "\nPurpose and scope stay with what the brief will name later.",
    )
    assert saved_two["ok"] is True, saved_two
    essay_stage(
        seq,
        "2",
        "confirm",
        look + "\nPurpose and scope stay with what the brief will name later.",
        **picked(saved_two),
    )


def test_ac1_essay_cover_prints_custom_field_in_word_bytes(workspace):
    """AC1. Essay cover walks the field list and prints a brief-named label."""
    module = "ESS9001HK"
    _brief(module, ESSAY_BRIEF)
    seq = open_sequence(module)
    body = pack(module)
    body["essay_id"] = seq
    body["student_number"] = NUMBER
    body["title_page_fields"] = {"Student address": ADDRESS}
    body["sections"][0]["body"] = "This is an essay. How do chokepoints constrain the corridor?"
    report = {
        "title": body["title"],
        "word_count": {"counted": 12},
        "sections": body["sections"],
        "figures": [],
        "tables": [],
        "sources": [],
    }
    from essay_writer.word import cover_lines, write_docx

    joined = "\n".join(cover_lines(seq, body, report))
    assert "Teaching partner" in joined
    assert "PROG01" in joined
    assert ADDRESS in joined
    assert f"Registration number: {NUMBER}" in joined
    path = work_dir(seq) / "output" / f"{seq}.docx"
    write_docx(seq, body, report, path)
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    assert "Teaching partner" in xml
    assert ADDRESS in xml


def test_ac2_empty_asked_field_blocks_word_confirm(workspace):
    """AC2. A blank custom label blocks confirm Word until the value is supplied."""
    module = "ESS9002HK"
    _brief(module, ESSAY_BRIEF)
    seq = open_sequence(module)
    body = pack(module)
    body["essay_id"] = seq
    body["student_number"] = NUMBER
    body["sections"][0]["body"] = "This is an essay. How do chokepoints constrain the corridor?"
    held = essay_pack_render_word(seq, body, "confirm", stage="6")
    assert held["ok"] is False
    assert held["refused"] == "title-page"
    assert "student address" in held["reason"]
    body["title_page_fields"] = {"Student address": ADDRESS}
    preview = essay_pack_render_word(seq, body, "draft", stage="6")
    assert preview.get("refused") != "title-page"


def test_ac3_brief_named_section_on_pack_not_invented(workspace):
    """AC3. Section headings follow the brief section plan on the pack."""
    write_upload(workspace)
    seq = open_sequence()
    plan = ["Introduction", "Harbour chokepoint", "Conclusion"]
    payload = pack(
        section_plan=plan,
        sections=[
            {"heading": "Introduction", "body": "Scope (Smith, 2020)."},
            {"heading": "Harbour chokepoint", "body": "Detail (Smith, 2020)."},
            {"heading": "Conclusion", "body": "The Strait handles flows (Smith, 2020)."},
        ],
    )
    from essay_writer.validate import essay_pack_validate

    ok = essay_pack_validate(seq, payload, "draft")
    assert not any(item.get("code") == "genre" for item in ok.get("blockers") or [])


def test_ac4_silent_mar_names_gaps_on_stage_doors_not_study_table(workspace):
    """AC4. Stage doors name silence gaps; MAR study-table shape stays off when the brief is silent."""
    for module in MAR_MODULES:
        _brief(module, _silent_brief(module))
        seq = open_sequence(module)
        record = assignment_requirements(seq)
        assert record["active"] is True
        assert record["format"] is None
        assert record["question"] is None
        assert study_defaults_allowed(seq) is False
        assert brief_genre(seq) is None
        assert genre_for(seq, {}) == {}
        assert word_rules_for(seq, {}) == {}
        assert section_plan_for(seq)["sections"] == []
        assert module in BRIEF_GENRE
        assert BRIEF_GENRE[module].get("genre")
        if module in BRIEF_WORD_RULES:
            assert BRIEF_WORD_RULES[module].get("limit")
        studied_sections = BRIEF_GENRE[module].get("default_section_headings") or []
        assert genre_for(seq, {}).get("section_plan") is None
        assert genre_for(seq, {}).get("genre") is None
        assert studied_sections or module == "MOD1011AA"

        gaps = assignment_silence_gaps(seq)
        assert gaps == [FORMAT_GAP, QUESTION_GAP, WORD_BAND_GAP]

        look = _stage_look(seq)
        stage_one = essay_stage(seq, "1", "draft", look)
        assert stage_one["ok"] is True, stage_one
        assert FORMAT_GAP in stage_one["basics_pass"]
        assert QUESTION_GAP in stage_one["basics_pass"]
        assert stage_one["assignment_gaps"] == gaps
        assert WORD_BAND_GAP in stage_one["assignment_gaps"]
        assert "Establish a thesis" in stage_one["confirm_line"]
        assert "Establish purpose and scope" in stage_one["confirm_line"]

        _advance_to_stage_three(seq, look)
        stage_three = essay_stage(seq, "3", "draft", look + "\nPlan follows the brief when it names sections.")
        assert stage_three["ok"] is True, stage_three
        assert FORMAT_GAP in stage_three["basics_pass"]
        assert QUESTION_GAP in stage_three["basics_pass"]
        assert stage_three["assignment_gaps"] == gaps
        assert WORD_BAND_GAP in stage_three["assignment_gaps"]
        title = stage_three["stage_title"]
        assert "Essay:" in title and "Report:" in title
        assert "Write an essay plan" in title
        assert "Write a report plan" in title


def test_ac5_build_covered_shared_requirement_record(workspace):
    """AC5. Cursor and Grok Build call the same assignment_requirements record."""
    _brief("ESS9003HK", ESSAY_BRIEF)
    seq = open_sequence("ESS9003HK")
    shared = assignment_requirements(seq)
    assert shared == build_requirements(seq)
    assert shared == cursor_requirements(seq)
    assert title_page_spec(ESSAY_BRIEF)["labels"] == ["Student address"]
