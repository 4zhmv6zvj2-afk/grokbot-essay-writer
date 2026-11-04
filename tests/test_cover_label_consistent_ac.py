"""Cover-label crumbs: mark-scheme band words are not title-page fields.

AC1: Consistent and clear / exact / sound-class crumbs are not kept cover labels.
AC2: PBS-style diary with polluted stored labels does not miss consistent when
registration is set.
AC3: A real brief field (Student address) stays required when empty.

Build covered: assignment_requirements and cover_label_kept are shared; Cursor and
Grok Build delegate to assignment_gate.assignment_requirements.
"""


from helpers import open_sequence

from essay_writer.assignment_gate import read_assignment
from essay_writer.brief_contract import (
    missing_title_fields,
    pack_with_registration,
    remember_registration,
)
from essay_writer.build_office import assignment_requirements as build_requirements
from essay_writer.cursor_office import assignment_requirements as cursor_requirements
from essay_writer.diary import (
    cover_label_kept,
    scrub_title_page_labels,
    title_page_spec,
)
from essay_writer.paths import essay_dir
from essay_writer.word import cover_lines

MODULE = "RPT5001AA"
NUMBER = "445566"
ASSIGNMENT = "Individual reflective diary on sustainability in business practice"
MODULE_TITLE = "The Challenge Module"

BRIEF = f"""
Assignment title: {ASSIGNMENT}

Module title: {MODULE_TITLE}
Module code: {MODULE}

Assignment task: Write four entries.

Title page
It should specify the module title, the module code, the assignment title, student registration numbers, the word count, and the student address.
DO NOT include your name.
Consistent

# Marking criteria/feedback form

| Criterion | 0-39 | 70+ |
| --- | --- | --- |
| Title page | thin | Consistent |
| Structure | clear | sound |
"""


def _write(text: str) -> None:
    folder = essay_dir(MODULE)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(text, encoding="utf-8")


def _pack(seq: str) -> dict:
    return {
        "essay_id": seq,
        "title": "Individual reflective diary",
        "referencing": "harvard",
        "assessment": "Individual reflective diary",
        "module_title": MODULE_TITLE,
        "sections": [{"heading": "One decision", "body": "A decision with theory."}],
    }


def _report(pack: dict) -> dict:
    return {
        "title": pack.get("title"),
        "word_count": {"counted": 120},
        "sections": pack.get("sections") or [],
    }


def test_ac1_cover_prints_asked_custom_label_not_band_crumbs(workspace):
    """AC1. Student address is an empty asked row; Consistent band crumbs stay off the cover."""
    _write(BRIEF)
    seq = open_sequence(MODULE)
    pack = pack_with_registration(seq, _pack(seq))
    lines = cover_lines(seq, pack, _report(pack))
    assert "Student address:" in lines
    assert all("consistent" not in line.casefold() for line in lines)


def test_ac1_band_crumbs_are_not_kept_cover_labels():
    """AC1. Mark-scheme band words are crumbs, not cover fields."""
    for crumb in ("Consistent", "clear", "exact", "sound"):
        assert cover_label_kept(crumb) is False
    assert cover_label_kept("Student address") is True
    assert title_page_spec(BRIEF)["labels"] == ["Student address"]


def test_ac2_polluted_assignment_labels_scrub_on_read(workspace, monkeypatch):
    """AC2. Stored Consistent crumb does not block when registration is set."""
    _write(BRIEF)
    seq = open_sequence(MODULE)
    assert remember_registration(seq, NUMBER) == NUMBER
    record = read_assignment(seq)
    page = dict(record["title_page"])
    page["labels"] = list(page.get("labels") or []) + [
        "Consistent",
        "clear",
        "exact",
        "sound",
    ]
    dirty = dict(record)
    dirty["title_page"] = page
    monkeypatch.setattr(
        "essay_writer.assignment_gate.read_assignment",
        lambda _essay_id: dirty,
    )
    scrubbed = scrub_title_page_labels(page, BRIEF)
    assert "Consistent" not in scrubbed["labels"]
    assert scrubbed["labels"] == ["Student address"]
    pack = pack_with_registration(seq, _pack(seq))
    missing = missing_title_fields(seq, pack, _report(pack))
    lowered = [item.casefold() for item in missing]
    assert "consistent" not in lowered
    assert "clear" not in lowered
    assert "exact" not in lowered
    assert "sound" not in lowered
    assert "student address" in lowered


def test_ac3_real_cover_field_still_required_when_empty(workspace):
    """AC3. Student address stays missing until a value is stored."""
    _write(BRIEF)
    seq = open_sequence(MODULE)
    assert remember_registration(seq, NUMBER) == NUMBER
    pack = pack_with_registration(seq, _pack(seq))
    missing = missing_title_fields(seq, pack, _report(pack))
    assert "student address" in [item.casefold() for item in missing]
    filled = dict(pack)
    filled["title_page_fields"] = {"Student address": "12 Quay Road"}
    assert "student address" not in [
        item.casefold() for item in missing_title_fields(seq, filled, _report(filled))
    ]


def test_build_and_cursor_share_scrubbed_assignment_requirements(workspace):
    """Build covered: both shells read the same scrubbed assignment record."""
    _write(BRIEF)
    seq = open_sequence(MODULE)
    shared = read_assignment(seq)
    assert shared["title_page"]["labels"] == ["Student address"]
    assert build_requirements(seq)["title_page"] == shared["title_page"]
    assert cursor_requirements(seq)["title_page"] == shared["title_page"]
