"""Outline-primary stages 3 to 6. Stable ids: AC1–AC4.

AC1: an outline or base prose the student puts on the sequence is read, and
     the stage reply names it as the plan.
AC2: the student's headings keep their order in the Word pack. A section the
     outline does not name is reported, not dropped in silence.
AC3: no section is lifted from the brief and the body is not stretched from
     gathered files while the student outline is primary.
AC4: only short claim-fit cites are woven in, and a sequence with no student
     outline keeps the earlier path.
"""

from __future__ import annotations

from helpers import open_sequence, picked

from essay_writer.outline_primary import (
    apply_outline_primary,
    outline_primary,
    outline_speech,
    read_outline,
)
from essay_writer.paths import module_code, work_dir
from essay_writer.shells import front_office_call
from essay_writer.stage_track import essay_stage
from essay_writer.state import load_state, save_state
from essay_writer.writing_basics import STAGE_ORDER

STUDENT = "Privacy risk reduces willingness to disclose personal data."
TOPIC_ONLY = "Surveys of privacy and personal data on government websites discuss trust."
FITS = (
    "Privacy risk reduces willingness to disclose personal data when people use a public site."
)
OUTLINE = (
    "# Introduction\n"
    "Public forms ask for more data than the visitor expects.\n"
    "\n"
    "# What the form collects\n"
    "Base prose the student already wrote about the form.\n"
    "\n"
    "# Where willingness breaks\n"
    "# Conclusion\n"
)

BRIEF = (
    "Genre: report\n"
    "Assignment title: Individual report\n"
    "Question: Which public website asks for the most data?\n"
    "\n"
    "Drivers 30%\n"
    "Risks 30%\n"
    "Recommendations 40%\n"
)


def _source(seq: str, ident: str, author: str, year: str, quote: str) -> dict:
    module = module_code(seq)
    return {
        "id": ident,
        "author": author,
        "year": year,
        "title": author.split(",")[0],
        "locator": f"uploads/{module}/{ident}.md",
        "quote": quote,
        "origin": "upload",
    }


def _plant(seq: str) -> None:
    state = load_state(seq)
    state["research"] = {
        "summary": {
            "sources": [
                _source(seq, "beldad", "Beldad, A.", "2019", FITS),
                _source(seq, "peng", "Peng, W.", "2018", TOPIC_ONLY),
            ]
        },
        "full": None,
    }
    save_state(seq, state)


def _plant_brief(seq: str) -> None:
    from essay_writer.paths import essay_dir

    path = essay_dir(seq) / "brief.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(BRIEF, encoding="utf-8")


def _plant_outline(seq: str, text: str = OUTLINE) -> None:
    folder = work_dir(seq) / "student-outline"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "outline.md").write_text(text, encoding="utf-8")


def _write_paper(seq: str, source: dict) -> None:
    from pathlib import Path

    from essay_writer.paths import workspace_root

    path = workspace_root() / Path(source["locator"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{source['author']} ({source['year']}) {source['title']}.\n{source['quote']}\n",
        encoding="utf-8",
    )


def _walk(seq: str, stop: str, *, stage3: str) -> None:
    for stage in STAGE_ORDER:
        if stage == stop:
            return
        look = stage3 if stage == "3" else "Saved from the brief."
        draft = essay_stage(seq, stage, "draft", look)
        assert draft["ok"] is True, (stage, draft)
        if stage == "5":
            assert draft["stored"] is True, draft
            continue
        saved = essay_stage(seq, stage, "confirm", look, **picked(draft))
        assert saved["stored"] is True, (stage, saved)


def _cited(name: str, year: str) -> str:
    return f"{STUDENT.rstrip('.')} ({name}, {year})."


def _review(seq: str, body: dict) -> dict:
    from essay_writer.word import word_manifest

    _pack, report = word_manifest(seq, body)
    return report


def test_ac1_a_student_outline_is_read_as_the_plan(workspace):
    """AC1. The headings are read once, and the stage reply names them."""
    seq = open_sequence()
    assert outline_primary(seq) is False
    assert read_outline(seq) is None

    _plant_outline(seq)
    assert outline_primary(seq) is True
    outline = read_outline(seq)
    assert outline["headings"] == [
        "Introduction",
        "What the form collects",
        "Where willingness breaks",
        "Conclusion",
    ]
    assert "Base prose the student already wrote" in outline["prose"]
    assert outline["files"] == ["outline.md"]
    assert "Your outline is the plan" in (outline_speech(seq) or "")

    _plant(seq)
    _walk(seq, "3", stage3=f"Use Beldad. {STUDENT}")
    draft = essay_stage(seq, "3", "draft", f"Use Beldad. {STUDENT}")
    assert draft["ok"] is True, draft
    assert draft["student_outline"]["headings"][0] == "Introduction"
    assert "Your outline is the plan" in draft["student_outline_line"]
    # Nothing invented: the outline is read, never rewritten.
    assert "Your outline is the plan" in draft["next"]


def test_ac2_the_student_heading_order_is_kept_in_the_pack(workspace):
    """AC2. The outline order wins, and an extra section is reported."""
    seq = open_sequence()
    _plant(seq)
    _plant_outline(seq)
    pack = {
        "essay_id": seq,
        "title": "Individual report",
        "assessment": "Individual report",
        "referencing": "harvard",
        "conclusion": "noted",
        "sections": [
            {"heading": "Conclusion", "body": "The form asks too much."},
            {"heading": "Where willingness breaks", "body": _cited("Beldad", "2019")},
            {"heading": "Something gathered", "body": "A paragraph from the papers."},
            {"heading": "Introduction", "body": "Forms ask for data."},
            {"heading": "What the form collects", "body": "The form asks for four fields."},
        ],
        "sources": [_source(seq, "beldad", "Beldad, A.", "2019", FITS)],
    }
    pinned = apply_outline_primary(seq, pack)
    assert pinned["applied"] is True
    headings = [section["heading"] for section in pinned["pack"]["sections"]]
    assert headings[:4] == [
        "Introduction",
        "What the form collects",
        "Where willingness breaks",
        "Conclusion",
    ]
    assert "Something gathered" in headings
    assert pinned["off_outline"] == ["Something gathered"]
    assert pinned["used"][0] == "Introduction"


def test_ac3_no_lifted_section_and_no_stretched_body_on_an_outline(workspace):
    """AC3. The brief weights a section the draft lacks. Nothing is lifted for it."""
    seq = open_sequence()
    _plant(seq)
    _plant_outline(seq)
    _plant_brief(seq)
    for ident, author, year, quote in (
        ("beldad", "Beldad, A.", "2019", FITS),
        ("peng", "Peng, W.", "2018", TOPIC_ONLY),
    ):
        _write_paper(seq, _source(seq, ident, author, year, quote))
    pack = {
        "essay_id": seq,
        "title": "Individual report",
        "assessment": "Individual report",
        "referencing": "harvard",
        "conclusion": "noted",
        "sections": [
            {"heading": "Introduction", "body": "Forms ask for data."},
            {"heading": "Conclusion", "body": "The form asks too much."},
        ],
        "sources": [_source(seq, "beldad", "Beldad, A.", "2019", FITS)],
    }
    report = _review(seq, pack)
    headings = [section["heading"] for section in report["sections"]]
    assert "Recommendations" not in headings
    assert "Drivers" not in headings
    assert report["student_outline"]["invented_lift"] is False
    assert report["student_outline"]["headings"][0] == "Introduction"
    # The outline headings stay in the student's order.
    assert headings[0] == "Introduction"


def test_ac4_only_short_claim_fit_cites_and_no_outline_keeps_the_old_path(workspace):
    """AC4. A long cited stretch is cut on an outline, and a plain sequence is untouched."""
    seq = open_sequence()
    _plant(seq)
    _walk(seq, "5", stage3=f"Use Beldad. {STUDENT}")
    landed = essay_stage(seq, "5", "draft", _cited("Beldad", "2019"))
    assert landed["stored"] is True, landed
    mini_review = (
        f"{_cited('Beldad', '2019')} "
        "Privacy risk also reduces willingness to disclose personal data on a public site "
        "(Beldad, 2019). "
        "Willingness to disclose personal data falls when privacy risk is high (Beldad, 2019)."
    )

    # No student outline yet: the earlier path, and no cite length is forced.
    kept = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "6",
            "confirmPhase": "draft",
            "look": mini_review,
        },
    )
    assert kept["ok"] is True, kept
    assert "cite_short" not in kept
    assert "student_outline" not in kept

    # The student drops the outline on the same sequence.
    _plant_outline(seq)
    draft = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "6",
            "confirmPhase": "draft",
            "look": mini_review,
        },
    )
    assert draft["ok"] is True, draft
    assert draft["cite_short"]["limit"] == 2
    assert draft["cite_short"]["cut"] >= 1
    assert draft["student_outline"]["headings"][0] == "Introduction"
