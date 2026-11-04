"""House cover title fallback when the saved pack is body-only.

AC1: brief Title line prints on the house cover when pack title is Draft and assessment is empty.
AC2: sequence id and Counted words still print (no regression from module-seq E2E #2).
"""

from helpers import ESSAY, pack

from essay_writer.diary import (
    assignment_on_cover,
    cover_field_rows,
    cover_lines_from_field_rows,
)

MODULE = ESSAY
SEQ = f"{MODULE}-1"
TOPIC = "How should the firm manage corridor risk?"
BRIEF_TITLE = "How can a mid-size retailer manage supply risk?"
REPORT_BRIEF = (
    "Genre: report\n"
    f"Question: {TOPIC}\n"
    f"Title: {BRIEF_TITLE}\n"
)


def _body_only_pack() -> dict:
    return {
        "essay_id": SEQ,
        "title": "Draft",
        "referencing": "harvard",
        "conclusion": "noted",
        "sections": pack(SEQ)["sections"],
    }


def _report(counted: int = 120) -> dict:
    return {"title": "Draft", "word_count": {"counted": counted}}


def _gate_record() -> dict:
    return {
        "active": True,
        "mapped": True,
        "lock": "purpose_and_scope",
        "title_page": {"fields": [], "labels": []},
    }


def test_ac1_house_cover_uses_brief_title_when_pack_is_body_only(
    workspace, monkeypatch
):
    """AC1. Body-only saved_pack still prints the brief Title line on the house cover."""
    saved = _body_only_pack()
    report = _report()
    assert assignment_on_cover(saved, report, REPORT_BRIEF) == BRIEF_TITLE

    monkeypatch.setattr(
        "essay_writer.assignment_gate.read_assignment",
        lambda _essay_id: _gate_record(),
    )
    monkeypatch.setattr(
        "essay_writer.textutil.module_brief_text",
        lambda _essay_id: REPORT_BRIEF,
    )
    rows = cover_field_rows(SEQ, saved, report, essay=True)
    lines = cover_lines_from_field_rows(SEQ, saved, rows)
    assert BRIEF_TITLE in lines


def test_ac2_house_cover_keeps_sequence_id_and_counted_words_with_body_only_pack(
    workspace, monkeypatch
):
    """AC2. Body-only recovery still prints sequence id and Counted words on the cover."""
    saved = _body_only_pack()
    report = _report(88)
    monkeypatch.setattr(
        "essay_writer.assignment_gate.read_assignment",
        lambda _essay_id: _gate_record(),
    )
    monkeypatch.setattr(
        "essay_writer.textutil.module_brief_text",
        lambda _essay_id: REPORT_BRIEF,
    )
    rows = cover_field_rows(SEQ, saved, report, essay=True)
    lines = cover_lines_from_field_rows(SEQ, saved, rows)
    assert SEQ in lines
    assert "Counted words: 88" in lines
    assert BRIEF_TITLE in lines
